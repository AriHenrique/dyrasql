# -*- coding: utf-8 -*-
"""
Trino Gateway Proxy with DyraSQL Core integration.
Intercepts queries and routes them based on DyraSQL Core routing decisions.
Optimized for high-volume data with streaming responses and optional bypass.
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import json
from urllib.parse import urljoin
from typing import Optional, AsyncGenerator

app = FastAPI(title="Trino Gateway Proxy", version="1.1.0")

# Configure logging with both console and file handlers
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
LOG_FILE = os.path.join(LOG_DIR, 'trino-gateway-proxy.log')

# Create logs directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Create formatter
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create root logger
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)

# Console handler (stdout)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# File handler with rotation (10MB max, keep 5 backups)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

DYRASQL_CORE_URL = os.getenv('DYRASQL_CORE_URL', 'http://dyrasql-core:5000')
TRINO_GATEWAY_URL = os.getenv('TRINO_GATEWAY_URL', 'http://trino-gateway:8080')

# Internal cluster URLs (Docker network)
CLUSTER_URLS = {
    'ecs': os.getenv('TRINO_ECS_URL', 'http://trino-ecs:8080'),
    'emr-standard': os.getenv('TRINO_EMR_STANDARD_URL', 'http://trino-emr-standard:8080'),
    'emr-optimized': os.getenv('TRINO_EMR_OPTIMIZED_URL', 'http://trino-emr-optimized:8080')
}

# External cluster URLs (accessible by clients) - for bypass mode
CLUSTER_EXTERNAL_URLS = {
    'ecs': os.getenv('TRINO_ECS_EXTERNAL_URL', 'http://localhost:8081'),
    'emr-standard': os.getenv('TRINO_EMR_STANDARD_EXTERNAL_URL', 'http://localhost:8082'),
    'emr-optimized': os.getenv('TRINO_EMR_OPTIMIZED_EXTERNAL_URL', 'http://localhost:8083')
}

FALLBACK_CLUSTER = 'ecs'
TIMEOUT = int(os.getenv('ROUTING_TIMEOUT', '5'))
DATA_TIMEOUT = int(os.getenv('DATA_TIMEOUT', '300'))  # Timeout for data fetching

# Bypass mode: if enabled, nextUri points directly to cluster (more efficient)
# If disabled, all traffic goes through proxy (more control)
BYPASS_MODE = os.getenv('BYPASS_MODE', 'true').lower() == 'true'

# Streaming threshold: responses larger than this (bytes) use streaming
STREAMING_THRESHOLD = int(os.getenv('STREAMING_THRESHOLD', '65536'))  # 64KB

# Query ID to cluster mapping for routing subsequent requests
query_cluster_map: dict = {}


@app.get('/health')
async def health():
    """Health check endpoint"""
    return {
        'service': 'trino-gateway-proxy',
        'status': 'healthy',
        'version': '1.1.0',
        'bypass_mode': BYPASS_MODE,
        'streaming_threshold': STREAMING_THRESHOLD,
        'dyrasql_core_url': DYRASQL_CORE_URL,
        'trino_gateway_url': TRINO_GATEWAY_URL
    }


def rewrite_urls_for_bypass(content: str, cluster_name: str) -> str:
    """
    Rewrite internal cluster URLs to external URLs for bypass mode.
    Client will connect directly to the cluster for subsequent requests.
    """
    cluster_url = CLUSTER_URLS.get(cluster_name, CLUSTER_URLS[FALLBACK_CLUSTER])
    external_url = CLUSTER_EXTERNAL_URLS.get(cluster_name, CLUSTER_EXTERNAL_URLS[FALLBACK_CLUSTER])

    # Replace internal URL with external URL
    pattern = re.escape(cluster_url) + r'(/v1/statement/[^\"]+)'
    replacement = external_url + r'\1'
    content = re.sub(pattern, replacement, content)

    # Also handle UI links
    pattern_ui = re.escape(cluster_url) + r'(/ui/[^\"]+)'
    replacement_ui = external_url + r'\1'
    content = re.sub(pattern_ui, replacement_ui, content)

    return content


def rewrite_urls_for_proxy(content: str) -> str:
    """
    Rewrite internal cluster URLs to proxy URL.
    All traffic continues through the proxy.
    """
    for cluster_name, cluster_url in CLUSTER_URLS.items():
        # Rewrite statement URLs
        pattern_next = re.escape(cluster_url) + r'(/v1/statement/[^\"]+)'
        replacement_next = r'http://localhost:8080\1'
        content = re.sub(pattern_next, replacement_next, content)

        # Rewrite UI URLs
        pattern_info = re.escape(cluster_url) + r'(/ui/[^\"]+)'
        replacement_info = r'http://localhost:8080\1'
        content = re.sub(pattern_info, replacement_info, content)

    return content


def extract_query_id_and_map_cluster(content: str, cluster_name: str) -> None:
    """Extract query ID from response and map it to cluster for subsequent requests."""
    try:
        response_json = json.loads(content)
        query_id = response_json.get('id')
        if query_id:
            query_cluster_map[query_id] = cluster_name
            logger.debug("query_mapped query_id=%s cluster=%s", query_id, cluster_name)
    except (json.JSONDecodeError, KeyError):
        pass


@app.post('/v1/statement')
async def route_statement(request: Request):
    """
    Intercepts SQL queries and routes based on DyraSQL Core decision.
    This is the main routing endpoint - always buffered for URL rewriting.
    """
    try:
        query = (await request.body()).decode('utf-8')
        user = request.headers.get('X-Trino-User', 'admin')

        if not query or not query.strip():
            raise HTTPException(status_code=400, detail='SQL query is required')

        query_normalized = query.strip().upper().rstrip(';').strip()
        is_keepalive = query_normalized in ['SELECT 1', 'SELECT 1 AS KEEPALIVE', 'SELECT 1 AS 1']

        if is_keepalive:
            logger.debug("statement_request keepalive user=%s", user)
            cluster_name = FALLBACK_CLUSTER
        else:
            logger.info("statement_request user=%s query_preview=%s", user, query[:80].replace('\n', ' '))
            cluster_name = await get_routing_decision(query)
            if not cluster_name:
                logger.warning("routing_fallback reason=dyrasql_unavailable cluster=%s", FALLBACK_CLUSTER)
                cluster_name = FALLBACK_CLUSTER

        cluster_url = CLUSTER_URLS.get(cluster_name)
        if not cluster_url:
            logger.error("routing_fallback reason=cluster_not_found cluster=%s fallback=%s", cluster_name, FALLBACK_CLUSTER)
            cluster_url = CLUSTER_URLS[FALLBACK_CLUSTER]
            cluster_name = FALLBACK_CLUSTER

        if not is_keepalive:
            logger.info("statement_routing cluster=%s url=%s bypass=%s", cluster_name, cluster_url, BYPASS_MODE)

        target_url = urljoin(cluster_url, '/v1/statement')

        headers = {
            'Content-Type': 'text/plain',
            'X-Trino-User': user,
            'Accept-Encoding': 'identity'
        }

        for header in ['X-Trino-Catalog', 'X-Trino-Schema', 'X-Trino-Source', 'X-Trino-Client-Info']:
            if header in request.headers:
                headers[header] = request.headers[header]

        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.post(target_url, content=query, headers=headers)

            response_content = response.content.decode('utf-8')

            # Map query ID to cluster for subsequent requests
            extract_query_id_and_map_cluster(response_content, cluster_name)

            # Rewrite URLs based on mode
            if BYPASS_MODE:
                response_content = rewrite_urls_for_bypass(response_content, cluster_name)
            else:
                response_content = rewrite_urls_for_proxy(response_content)

            response_headers = {}
            for key, value in response.headers.items():
                if key.lower() not in ['connection', 'transfer-encoding', 'content-encoding', 'content-length']:
                    response_headers[key] = value

            content_type = response.headers.get('Content-Type', 'application/json')
            response_headers['Content-Type'] = content_type

            return Response(
                content=response_content.encode('utf-8'),
                status_code=response.status_code,
                headers=response_headers,
            )

    except httpx.TimeoutException:
        logger.warning("statement_request timeout")
        raise HTTPException(status_code=504, detail='Query execution timeout')
    except Exception as e:
        logger.exception("statement_request error=%s", str(e))
        raise HTTPException(status_code=500, detail='Query routing failed')


async def stream_response(response: httpx.Response, cluster_name: str) -> AsyncGenerator[bytes, None]:
    """
    Stream response chunks from cluster to client.
    Minimal memory footprint for large responses.
    """
    async for chunk in response.aiter_bytes(chunk_size=8192):
        yield chunk


async def stream_response_with_rewrite(response: httpx.Response, cluster_name: str) -> AsyncGenerator[bytes, None]:
    """
    Stream response with URL rewriting for smaller responses.
    For larger responses, streams without modification (acceptable for data chunks).
    """
    # For small responses, buffer and rewrite
    content_length = response.headers.get('content-length')
    if content_length and int(content_length) < STREAMING_THRESHOLD:
        content = b''
        async for chunk in response.aiter_bytes():
            content += chunk

        try:
            text_content = content.decode('utf-8')
            if BYPASS_MODE:
                text_content = rewrite_urls_for_bypass(text_content, cluster_name)
            else:
                text_content = rewrite_urls_for_proxy(text_content)
            yield text_content.encode('utf-8')
        except UnicodeDecodeError:
            yield content
    else:
        # For large responses, stream directly (data chunks don't need URL rewriting)
        async for chunk in response.aiter_bytes(chunk_size=8192):
            yield chunk


@app.get('/v1/info')
async def info():
    """Trino /v1/info endpoint - proxies to default cluster."""
    try:
        async with httpx.AsyncClient(timeout=2, headers={'Accept-Encoding': 'identity'}) as client:
            response = await client.get(f"{CLUSTER_URLS[FALLBACK_CLUSTER]}/v1/info")

            response_headers = {}
            for key, value in response.headers.items():
                if key.lower() not in ['connection', 'transfer-encoding', 'content-encoding']:
                    response_headers[key] = value

            response_content = response.content.decode('utf-8')
            if not BYPASS_MODE:
                response_content = rewrite_urls_for_proxy(response_content)

            return Response(
                content=response_content.encode('utf-8'),
                status_code=response.status_code,
                headers=response_headers,
            )
    except Exception as e:
        logger.warning(f"Erro ao obter info do cluster, retornando fallback: {e}")
        fallback_data = {
            'nodeId': 'proxy',
            'state': 'ACTIVE',
            'environment': 'production'
        }
        return Response(
            content=json.dumps(fallback_data).encode('utf-8'),
            status_code=200,
            headers={'Content-Type': 'application/json'},
        )


@app.post('/loginType')
async def login_type_post():
    """Endpoint de tipo de login - retorna que não há autenticação necessária"""
    return Response(
        content=json.dumps({'supportedTypes': []}).encode('utf-8'),
        status_code=200,
        headers={'Content-Type': 'application/json'},
    )


@app.get('/loginType')
async def login_type_get():
    """Endpoint de tipo de login - retorna que não há autenticação necessária"""
    return Response(
        content=json.dumps({'supportedTypes': []}).encode('utf-8'),
        status_code=200,
        headers={'Content-Type': 'application/json'},
    )


@app.get('/v1/statement')
async def get_statement():
    """GET /v1/statement - some JDBC clients send GET before POST."""
    raise HTTPException(status_code=405, detail='Method not allowed. Use POST /v1/statement to execute queries.')


def get_cluster_for_path(path: str) -> str:
    """Determine which cluster handles this path based on query ID."""
    query_id_match = re.search(r'/(\d{8}_\d{6}_\d{5}_[^/]+)/', path)
    if query_id_match:
        query_id = query_id_match.group(1)
        if query_id in query_cluster_map:
            cluster_name = query_cluster_map[query_id]
            logger.debug("path_cluster_resolved path=%s cluster=%s query_id=%s", path[:60], cluster_name, query_id)
            return cluster_name
        else:
            logger.debug("path_cluster_unknown query_id=%s fallback=%s", query_id, FALLBACK_CLUSTER)
    return FALLBACK_CLUSTER


@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'])
async def proxy_other(path: str, request: Request):
    """
    Proxy for other Trino endpoints (nextUri, keepalive, etc).
    Uses streaming for large responses to minimize memory usage.
    For Trino UI requests, redirects to Trino Gateway.
    """
    logger.debug("proxy_request path=%s method=%s", path[:60], request.method)

    normalized_path = path.strip('/')
    if normalized_path == 'loginType':
        logger.debug("proxy_loginType returning empty supportedTypes")
        return Response(
            content=json.dumps({'supportedTypes': []}).encode('utf-8'),
            status_code=200,
            headers={'Content-Type': 'application/json'},
        )

    # Check if this is a UI request
    is_ui_request = (
        path == '' or
        path == '/' or
        path.startswith('ui/') or
        path.startswith('assets/') or
        path.startswith('vendor/') or
        path.endswith('.html') or
        path.endswith('.css') or
        path.endswith('.js') or
        path.endswith('.ico')
    )

    if is_ui_request and request.method == 'GET':
        gateway_ui_url = f"{TRINO_GATEWAY_URL}/{path}" if path else f"{TRINO_GATEWAY_URL}/"
        logger.debug("proxy_ui_redirect url=%s", gateway_ui_url)

        try:
            async with httpx.AsyncClient(
                timeout=5,
                follow_redirects=True,
                headers={'Accept-Encoding': 'identity'}
            ) as client:
                response = await client.get(gateway_ui_url, params=request.query_params)

                response_headers = {}
                for key, value in response.headers.items():
                    if key.lower() not in ['connection', 'transfer-encoding', 'content-encoding']:
                        response_headers[key] = value

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                )
        except Exception as e:
            logger.warning("proxy_ui_redirect_failed fallback_to_cluster error=%s", str(e))

    # Determine target cluster based on query ID in path
    cluster_name = get_cluster_for_path(path)
    cluster_url = CLUSTER_URLS.get(cluster_name, CLUSTER_URLS[FALLBACK_CLUSTER])

    try:
        if path.startswith('/'):
            target_url = f"{cluster_url}{path}"
        else:
            target_url = f"{cluster_url}/{path}" if path else f"{cluster_url}/"

        headers = {}
        for key, value in request.headers.items():
            if key.lower() not in ['host', 'content-length', 'connection', 'transfer-encoding']:
                headers[key] = value
        headers['Accept-Encoding'] = 'identity'

        body = await request.body() if request.method in ['POST', 'PUT'] else None

        # Use streaming for GET requests (data fetching)
        if request.method == 'GET':
            async with httpx.AsyncClient(timeout=DATA_TIMEOUT) as client:
                async with client.stream('GET', target_url, headers=headers, params=request.query_params) as response:
                    response_headers = {}
                    for key, value in response.headers.items():
                        if key.lower() not in ['connection', 'transfer-encoding', 'content-encoding', 'content-length']:
                            response_headers[key] = value

                    content_type = response.headers.get('Content-Type', 'application/json')
                    response_headers['Content-Type'] = content_type

                    # Check if we need URL rewriting (for JSON responses with nextUri)
                    if 'application/json' in content_type:
                        # Buffer small JSON responses for URL rewriting
                        content_length = response.headers.get('content-length')
                        if content_length and int(content_length) < STREAMING_THRESHOLD:
                            content = b''
                            async for chunk in response.aiter_bytes():
                                content += chunk

                            text_content = content.decode('utf-8')
                            if BYPASS_MODE:
                                text_content = rewrite_urls_for_bypass(text_content, cluster_name)
                            else:
                                text_content = rewrite_urls_for_proxy(text_content)

                            return Response(
                                content=text_content.encode('utf-8'),
                                status_code=response.status_code,
                                headers=response_headers,
                            )

                    # For large responses or non-JSON, stream directly
                    return StreamingResponse(
                        stream_response(response, cluster_name),
                        status_code=response.status_code,
                        headers=response_headers,
                        media_type=content_type
                    )
        else:
            # For non-GET requests, use regular async client
            async with httpx.AsyncClient(timeout=DATA_TIMEOUT, follow_redirects=True) as client:
                if request.method == 'POST':
                    response = await client.post(target_url, content=body, headers=headers)
                elif request.method == 'PUT':
                    response = await client.put(target_url, content=body, headers=headers)
                elif request.method == 'DELETE':
                    response = await client.delete(target_url, headers=headers)
                elif request.method == 'HEAD':
                    response = await client.head(target_url, headers=headers)
                elif request.method == 'OPTIONS':
                    response = await client.options(target_url, headers=headers)
                else:
                    raise HTTPException(status_code=405, detail='Method not allowed')

                response_headers = {}
                for key, value in response.headers.items():
                    if key.lower() not in ['connection', 'transfer-encoding', 'content-encoding']:
                        response_headers[key] = value

                response_content = response.content.decode('utf-8')
                if BYPASS_MODE:
                    response_content = rewrite_urls_for_bypass(response_content, cluster_name)
                else:
                    response_content = rewrite_urls_for_proxy(response_content)

                return Response(
                    content=response_content.encode('utf-8'),
                    status_code=response.status_code,
                    headers=response_headers,
                )

    except httpx.TimeoutException:
        logger.warning("proxy_timeout path=%s", path[:60])
        raise HTTPException(status_code=504, detail='Request timeout')
    except Exception as e:
        logger.exception("proxy_error path=%s error=%s", path[:60], str(e))
        raise HTTPException(status_code=500, detail='Proxy request failed')


async def get_routing_decision(query: str) -> Optional[str]:
    """Calls DyraSQL Core to get routing decision."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{DYRASQL_CORE_URL}/api/v1/route",
                json={'query': query}
            )
            if response.status_code == 200:
                data = response.json()
                cluster = data.get('cluster')
                score = data.get('score', 0)
                cached = data.get('cached', False)
                factors = data.get('factors', {})
                if cached:
                    logger.info("routing_decision cached=true cluster=%s score=%.3f", cluster, score)
                else:
                    logger.info("routing_decision cluster=%s score=%.3f volume=%.2f complexity=%.2f historical=%.2f",
                        cluster, score, factors.get('volume', 0), factors.get('complexity', 0), factors.get('historical', 0))
                return cluster
            else:
                logger.warning("dyrasql_core_error status=%s body=%s", response.status_code, response.text[:200])
                return None
    except httpx.TimeoutException:
        logger.warning("dyrasql_core_timeout")
        return None
    except Exception as e:
        logger.exception("dyrasql_core_error error=%s", str(e))
        return None


@app.on_event("startup")
async def startup_event():
    """Startup event."""
    logger.info("trino_gateway_proxy starting version=1.1.0 bypass_mode=%s streaming_threshold=%s dyrasql_core_url=%s",
                BYPASS_MODE, STREAMING_THRESHOLD, DYRASQL_CORE_URL)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info("trino_gateway_proxy shutting down")


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', '8080'))
    uvicorn.run(app, host='0.0.0.0', port=port)
