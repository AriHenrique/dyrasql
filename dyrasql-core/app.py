#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DyraSQL Core - Dynamic SQL query routing system.
Main API that coordinates the routing decision process.
Optimized for high-volume data with streaming responses and optional bypass.
"""

from fastapi import FastAPI, Request, Response, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, AsyncGenerator

import os
import logging
from logging.handlers import RotatingFileHandler
import httpx
import re
import json

from query_analyzer import QueryAnalyzer
from decision_engine import DecisionEngine
from metadata_connector import MetadataConnector
from history_manager import HistoryManager


# Configure logging with both console and file handlers
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
LOG_FILE = os.path.join(LOG_DIR, 'dyrasql-core.log')

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


app = FastAPI(title="DyraSQL Core", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


query_analyzer = QueryAnalyzer()
decision_engine = DecisionEngine()
metadata_connector = MetadataConnector()
history_manager = HistoryManager()


# Query ID to cluster mapping for routing subsequent requests
query_cluster_map: dict = {}


# Cluster URLs (internal Docker network)
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

# Bypass mode: if enabled, nextUri points directly to cluster (more efficient)
BYPASS_MODE = os.getenv('BYPASS_MODE', 'true').lower() == 'true'

# Streaming threshold: responses larger than this (bytes) use streaming
STREAMING_THRESHOLD = int(os.getenv('STREAMING_THRESHOLD', '65536'))  # 64KB

# Data timeout for large queries
DATA_TIMEOUT = int(os.getenv('DATA_TIMEOUT', '300'))


class RouteRequest(BaseModel):
    query: str


class MetricsRequest(BaseModel):
    fingerprint: str
    metrics: Optional[Dict[str, Any]] = None


def get_cluster_url(cluster_name: str) -> str:
    """Returns the internal cluster URL by name."""
    return CLUSTER_URLS.get(cluster_name, CLUSTER_URLS['ecs'])


def get_cluster_external_url(cluster_name: str) -> str:
    """Returns the external cluster URL by name."""
    return CLUSTER_EXTERNAL_URLS.get(cluster_name, CLUSTER_EXTERNAL_URLS['ecs'])


def rewrite_urls_for_bypass(content: str, cluster_name: str) -> str:
    """
    Rewrite internal cluster URLs to external URLs for bypass mode.
    Client will connect directly to the cluster for subsequent requests.
    """
    cluster_url = get_cluster_url(cluster_name)
    external_url = get_cluster_external_url(cluster_name)

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
    Rewrite internal cluster URLs to proxy URL (localhost:5001).
    All traffic continues through dyrasql-core.
    """
    for cluster_name, cluster_url in CLUSTER_URLS.items():
        pattern_next = re.escape(cluster_url) + r'(/v1/statement/[^\"]+)'
        replacement_next = r'http://localhost:5001\1'
        content = re.sub(pattern_next, replacement_next, content)

        pattern_info = re.escape(cluster_url) + r'(/ui/[^\"]+)'
        replacement_info = r'http://localhost:5001\1'
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


@app.get('/health')
async def health():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'service': 'dyrasql-core',
        'version': '1.1.0',
        'bypass_mode': BYPASS_MODE,
        'streaming_threshold': STREAMING_THRESHOLD
    }


@app.post('/api/v1/route')
async def route_query(request_data: RouteRequest):
    """
    Main routing endpoint. Accepts a SQL query and returns the routing decision.
    """
    try:
        query = request_data.query
        logger.info("route_request query_preview=%s", query[:80].replace('\n', ' '))

        fingerprint = query_analyzer.generate_fingerprint(query)
        logger.debug("route_request fingerprint=%s", fingerprint[:16])

        cached_decision = history_manager.get_cached_decision(fingerprint)
        if cached_decision:
            logger.info("route_response cached=true fingerprint=%s cluster=%s", fingerprint[:16], cached_decision['cluster'])
            return {
                'fingerprint': fingerprint,
                'cluster': cached_decision['cluster'],
                'score': cached_decision.get('score'),
                'factors': cached_decision.get('factors', {}),
                'cached': True,
                'cluster_url': get_cluster_url(cached_decision['cluster']),
                'cluster_external_url': get_cluster_external_url(cached_decision['cluster'])
            }

        if query_analyzer.is_catalog_or_metadata_query(query):
            logger.info("route_response catalog_query=true cluster=ecs fingerprint=%s", fingerprint[:16])
            decision_catalog = {
                'cluster': 'ecs',
                'score': 0.0,
                'factors': {'volume': 0, 'complexity': 0, 'historical': 0}
            }
            history_manager.save_decision(fingerprint, decision_catalog)
            return {
                'fingerprint': fingerprint,
                'cluster': 'ecs',
                'score': decision_catalog['score'],
                'factors': decision_catalog['factors'],
                'cached': False,
                'cluster_url': get_cluster_url('ecs'),
                'cluster_external_url': get_cluster_external_url('ecs')
            }

        logger.info("route_analysis phase=explain_io")
        io_analysis = query_analyzer.analyze_query_io(query)

        metadata = {}
        if io_analysis and io_analysis.get('tables'):
            for table_name, table_io in io_analysis['tables'].items():
                metadata[table_name] = {
                    'total_size_bytes': table_io.get('total_size_bytes', 0),
                    'total_records': table_io.get('total_records', 0),
                    'cpu_cost': table_io.get('cpu_cost', 0),
                    'filters': table_io.get('filters', []),
                    'io_analysis': table_io
                }

        total_size_gb = io_analysis.get('total_size_bytes', 0) / (1024**3) if io_analysis else 0
        logger.info("route_analysis tables=%s size_bytes=%s size_gb=%.2f", len(metadata), io_analysis.get('total_size_bytes', 0) if io_analysis else 0, total_size_gb)

        complexity = query_analyzer.analyze_complexity(query)
        logger.debug("route_analysis complexity=%s", complexity)

        decision = decision_engine.decide(
            query=query,
            fingerprint=fingerprint,
            metadata=metadata,
            complexity=complexity,
            history_manager=history_manager
        )

        logger.info("route_response cluster=%s score=%.3f fingerprint=%s", decision['cluster'], decision['score'], fingerprint[:16])
        history_manager.save_decision(fingerprint, decision)

        return {
            'fingerprint': fingerprint,
            'cluster': decision['cluster'],
            'score': decision['score'],
            'factors': decision.get('factors', {}),
            'cached': False,
            'cluster_url': get_cluster_url(decision['cluster']),
            'cluster_external_url': get_cluster_external_url(decision['cluster'])
        }

    except Exception as e:
        logger.exception("route_request error=%s", str(e))
        raise HTTPException(
            status_code=500,
            detail={'error': 'Internal error processing route request', 'message': str(e)}
        )


@app.post('/api/v1/metrics')
async def save_metrics(request_data: MetricsRequest):
    """Saves post-execution metrics."""
    try:
        data = request_data.dict()
        history_manager.save_metrics(data)
        logger.info("metrics_saved fingerprint=%s", data.get('fingerprint', '')[:16])
        return {'status': 'success', 'message': 'Metrics saved successfully'}
    except Exception as e:
        logger.exception("save_metrics error=%s", str(e))
        raise HTTPException(status_code=500, detail={'error': 'Failed to save metrics', 'message': str(e)})


@app.get('/v1/info')
async def trino_info():
    """Trino /v1/info endpoint (required for JDBC). Proxies to default ECS cluster."""
    try:
        cluster_url = get_cluster_url('ecs')
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{cluster_url}/v1/info",
                headers={'Accept-Encoding': 'identity'}
            )
            response_headers = {}
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection', 'content-length']:
                    response_headers[key] = value
            content_type = response.headers.get('Content-Type', 'application/json')
            response_headers['Content-Type'] = content_type
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type
            )
    except Exception as e:
        logger.warning("trino_info proxy_failed error=%s", str(e))
        return JSONResponse(
            content={
                'nodeId': 'dyrasql-core',
                'state': 'ACTIVE',
                'nodeVersion': {'version': '478'},
                'environment': 'production',
                'coordinator': True
            },
            status_code=200
        )


@app.post('/v1/statement')
async def trino_statement(request: Request):
    """
    Trino /v1/statement endpoint. Executes queries with intelligent routing;
    DyraSQL Core selects the target cluster and proxies the request.
    """
    try:
        body = await request.body()
        query = body.decode('utf-8')
        user = request.headers.get('X-Trino-User', 'admin')
        logger.info("statement_request user=%s query_preview=%s", user, query[:100].replace('\n', ' '))

        if not query or not query.strip():
            logger.warning("statement_request empty_query user=%s", user)
            raise HTTPException(status_code=400, detail={'error': 'SQL query is required'})

        query_normalized = query.strip().upper().rstrip(';').strip()
        is_keepalive = (
            query_normalized in ['SELECT 1', 'SELECT 1 AS KEEPALIVE', 'SELECT 1 AS 1'] or
            query_normalized.startswith("SELECT 'KEEP ALIVE'") or
            query_normalized.startswith("SELECT 'KEEPALIVE'")
        )

        if is_keepalive:
            cluster_name = 'ecs'
            logger.info("statement_routing reason=keepalive cluster=ecs")
        else:
            fingerprint = query_analyzer.generate_fingerprint(query)
            cached_decision = history_manager.get_cached_decision(fingerprint)

            if cached_decision:
                cluster_name = cached_decision['cluster']
                score = cached_decision.get('score', 0.0)
                factors = cached_decision.get('factors', {})
                logger.info("statement_routing cached=true cluster=%s score=%.3f fingerprint=%s volume=%.2f complexity=%.2f historical=%.2f",
                    cluster_name, score, fingerprint[:16], factors.get('volume', 0), factors.get('complexity', 0), factors.get('historical', 0))
            else:
                is_metadata_query = (
                    query_normalized.startswith('SHOW ') or
                    query_normalized.startswith('DESCRIBE ') or
                    query_normalized.startswith('DESC ') or
                    query_normalized.startswith('SELECT VERSION()') or
                    query_normalized.startswith('SELECT CURRENT_')
                )
                is_catalog_query = query_analyzer.is_catalog_or_metadata_query(query)

                if is_metadata_query or is_catalog_query:
                    cluster_name = 'ecs'
                    kind = "catalog" if is_catalog_query else "metadata"
                    logger.info("statement_routing reason=%s cluster=ecs fingerprint=%s", kind, fingerprint[:16])
                    history_manager.save_decision(fingerprint, {
                        'cluster': cluster_name,
                        'score': 0.0,
                        'factors': {'volume': 0, 'complexity': 0, 'historical': 0}
                    })
                else:
                    logger.info("statement_analysis phase=explain_io cluster=ecs")
                    io_analysis = query_analyzer.analyze_query_io(query)
                    metadata = {}
                    if io_analysis and io_analysis.get('tables'):
                        for table_name, table_io in io_analysis['tables'].items():
                            metadata[table_name] = {
                                'total_size_bytes': table_io.get('total_size_bytes', 0),
                                'total_records': table_io.get('total_records', 0),
                                'cpu_cost': table_io.get('cpu_cost', 0),
                                'filters': table_io.get('filters', []),
                                'io_analysis': table_io
                            }
                    complexity = query_analyzer.analyze_complexity(query)
                    decision = decision_engine.decide(
                        query=query,
                        fingerprint=fingerprint,
                        metadata=metadata,
                        complexity=complexity,
                        history_manager=history_manager
                    )
                    cluster_name = decision['cluster']
                    score = decision['score']
                    factors = decision.get('factors', {})
                    logger.info("statement_routing computed cluster=%s score=%.3f fingerprint=%s volume=%.2f complexity=%.2f historical=%.2f",
                        cluster_name, score, fingerprint[:16], factors.get('volume', 0), factors.get('complexity', 0), factors.get('historical', 0))
                    history_manager.save_decision(fingerprint, decision)

        cluster_url = get_cluster_url(cluster_name)
        logger.info("statement_execute cluster=%s url=%s bypass=%s", cluster_name, cluster_url, BYPASS_MODE)

        headers = {
            'Content-Type': 'text/plain',
            'X-Trino-User': user,
            'Accept-Encoding': 'identity'
        }

        for header in ['X-Trino-Catalog', 'X-Trino-Schema', 'X-Trino-Source', 'X-Trino-Client-Info']:
            if header in request.headers:
                headers[header] = request.headers[header]

        timeout = 5 if is_keepalive else DATA_TIMEOUT
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{cluster_url}/v1/statement",
                content=query,
                headers=headers
            )

            logger.info("statement_response cluster=%s status=%s", cluster_name, response.status_code)
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
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection', 'content-length']:
                    response_headers[key] = value

            content_type = response.headers.get('Content-Type', 'application/json')
            response_headers['Content-Type'] = content_type

            return Response(
                content=response_content.encode('utf-8'),
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type
            )

    except httpx.TimeoutException:
        logger.warning("statement_execute timeout")
        raise HTTPException(status_code=504, detail={'error': 'Query execution timeout'})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("statement_execute error=%s", str(e))
        raise HTTPException(status_code=500, detail={'error': 'Query execution failed', 'message': str(e)})


async def stream_response(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    """
    Stream response chunks from cluster to client.
    Minimal memory footprint for large responses.
    """
    async for chunk in response.aiter_bytes(chunk_size=8192):
        yield chunk


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
            logger.debug("path_cluster_unknown query_id=%s fallback=ecs", query_id)
    return 'ecs'


@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'])
async def proxy_other(path: str, request: Request):
    """
    Proxy for other Trino endpoints (nextUri, etc.). Resolves cluster from query ID in path.
    Uses streaming for large responses to minimize memory usage.
    """
    try:
        cluster_name = get_cluster_for_path(path)
        cluster_url = get_cluster_url(cluster_name)
        target_url = f"{cluster_url}/{path}"
        logger.debug("proxy_request method=%s path=%s cluster=%s", request.method, path[:60], cluster_name)

        headers = {}
        for key, value in request.headers.items():
            if key.lower() not in ['host', 'content-length', 'connection']:
                headers[key] = value
        headers['Accept-Encoding'] = 'identity'

        body = await request.body() if request.method in ['POST', 'PUT'] else None

        # Use streaming for GET requests (data fetching)
        if request.method == 'GET':
            async with httpx.AsyncClient(timeout=DATA_TIMEOUT) as client:
                async with client.stream('GET', target_url, headers=headers, params=dict(request.query_params)) as response:
                    response_headers = {}
                    for key, value in response.headers.items():
                        if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection', 'content-length']:
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
                        stream_response(response),
                        status_code=response.status_code,
                        headers=response_headers,
                        media_type=content_type
                    )
        else:
            # For non-GET requests, use regular async client
            async with httpx.AsyncClient(timeout=DATA_TIMEOUT) as client:
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
                    raise HTTPException(status_code=405, detail={'error': 'Method not allowed'})

                response_content = response.content.decode('utf-8')

                if BYPASS_MODE:
                    response_content = rewrite_urls_for_bypass(response_content, cluster_name)
                else:
                    response_content = rewrite_urls_for_proxy(response_content)

                response_headers = {}
                for key, value in response.headers.items():
                    if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection', 'content-length']:
                        response_headers[key] = value

                content_type = response.headers.get('Content-Type', 'application/json')
                response_headers['Content-Type'] = content_type

                return Response(
                    content=response_content.encode('utf-8'),
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=content_type
                )

    except httpx.TimeoutException:
        logger.warning("proxy_timeout path=%s", path[:60])
        raise HTTPException(status_code=504, detail={'error': 'Request timeout'})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("proxy_error path=%s error=%s", path[:60], str(e))
        raise HTTPException(status_code=500, detail={'error': 'Proxy request failed', 'message': str(e)})


@app.on_event("startup")
async def startup_event():
    """Startup event."""
    logger.info("dyrasql_core starting version=1.1.0 bypass_mode=%s streaming_threshold=%s",
                BYPASS_MODE, STREAMING_THRESHOLD)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info("dyrasql_core shutting down")


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 5000))
    uvicorn.run(app, host='0.0.0.0', port=port)
