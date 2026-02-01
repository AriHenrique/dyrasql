#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Query Analyzer - Analyzes SQL queries and extracts I/O and cost information
using Trino EXPLAIN (TYPE IO).
"""


import re

import hashlib

import logging

import json

import os

import requests

from typing import Dict, List, Optional, Any
from datetime import datetime


logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes SQL queries and extracts metadata using Trino EXPLAIN (TYPE IO)."""

    
    def __init__(self):

        """Initializes the analyzer with Trino configuration."""

                                                      
        self.trino_url = os.getenv('TRINO_URL', 'http://trino-ecs:8080')

        self.trino_user = os.getenv('TRINO_USER', 'admin')
        
        # Directory for saving EXPLAIN outputs
        self.save_explains = os.getenv('SAVE_EXPLAINS', 'true').lower() == 'true'
        self.explains_dir = os.getenv('EXPLAINS_DIR', '/app/explains')
        if self.save_explains:
            os.makedirs(self.explains_dir, exist_ok=True)

    
    def is_catalog_or_metadata_query(self, query: str) -> bool:
        """
        Detects catalog/metadata queries (e.g. JDBC IDE catalog discovery).
        Such queries should be routed to ECS. Matches system.jdbc.* and information_schema.
        """
        if not query or not query.strip():
            return False
        q = query.strip().lower()
        return (
            'system.jdbc' in q or
            'information_schema' in q
        )

    
    def generate_fingerprint(self, query):
        """Generates a unique fingerprint for the SQL query (normalized, then hashed)."""

                                                                             
        normalized = re.sub(r'\s+', ' ', query.strip().lower())

        
        normalized = re.sub(r"'[^']*'", "'?'", normalized)

        normalized = re.sub(r'\d+', '?', normalized)

        
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()

        
        return fingerprint

    
    def _normalize_query_with_catalog(self, query: str) -> str:
        """
        Normalizes query by adding catalog 'iceberg' when absent.
        Handles both quoted ("schema"."table") and unquoted (schema.table) identifiers.
        Example: 'select * from schema.table' -> 'select * from iceberg.schema.table'
        Example: 'select * from "schema"."table"' -> 'select * from iceberg."schema"."table"'
        """
        query_normalized = query
        modified = False

        # Pattern for quoted identifiers: "schema"."table" (no catalog)
        # Handles whitespace/newlines between keyword and table reference
        # Captures: keyword, schema (with quotes), table (with quotes)
        # Negative lookbehind ensures we don't match if there's already a catalog prefix
        quoted_pattern = r'\b(from|(?:left|right|full|inner|cross)?\s*(?:outer\s+)?join)\s+("[\w_]+")\.("[\w_]+")'

        def add_catalog_quoted(match):
            nonlocal modified
            full_match = match.group(0)
            keyword = match.group(1)
            schema = match.group(2)  # includes quotes
            table = match.group(3)   # includes quotes

            # Check if there's already a catalog by looking at what comes before schema
            # If schema starts right after the keyword + whitespace, there's no catalog
            # We add iceberg. prefix
            modified = True
            logger.debug("normalize_quoted keyword=%s schema=%s table=%s", keyword.strip(), schema, table)
            return f"{keyword} iceberg.{schema}.{table}"

        query_normalized = re.sub(quoted_pattern, add_catalog_quoted, query_normalized, flags=re.IGNORECASE | re.DOTALL)

        # Pattern for unquoted identifiers: schema.table (no catalog)
        # Must have exactly 2 parts (schema.table), not 3 (catalog.schema.table)
        # Negative lookahead (?!\.) ensures no third part follows
        unquoted_pattern = r'\b(from|(?:left|right|full|inner|cross)?\s*(?:outer\s+)?join)\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)(?!\.)'

        def add_catalog_unquoted(match):
            nonlocal modified
            keyword = match.group(1)
            schema = match.group(2)
            table = match.group(3)

            # Skip if schema looks like a catalog (iceberg, hive, etc)
            if schema.lower() in ['iceberg', 'hive', 'mysql', 'postgresql', 'mongodb', 'system']:
                return match.group(0)

            modified = True
            logger.debug("normalize_unquoted keyword=%s schema=%s table=%s", keyword.strip(), schema, table)
            return f"{keyword} iceberg.{schema}.{table}"

        query_normalized = re.sub(unquoted_pattern, add_catalog_unquoted, query_normalized, flags=re.IGNORECASE | re.DOTALL)

        if modified:
            logger.info("query_normalized_catalog modified=true preview=%s", query_normalized[:150].replace('\n', ' '))

        return query_normalized

    
    def _save_explain(self, query: str, explain_result: Dict[str, Any], parsed_result: Optional[Dict[str, Any]] = None, normalized_query: Optional[str] = None):
        """Saves EXPLAIN result to a JSON file for later analysis."""
        if not self.save_explains:
            return
            
        try:
            fingerprint = self.generate_fingerprint(query)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            
            # Filename: timestamp_fingerprint_short.json
            filename = f"{timestamp}_{fingerprint[:16]}.json"
            filepath = os.path.join(self.explains_dir, filename)
            
            # Full EXPLAIN payload
            explain_data = {
                'timestamp': datetime.now().isoformat(),
                'fingerprint': fingerprint,
                'query': query,
                'normalized_query': normalized_query if normalized_query else query,
                'explain_query': f"EXPLAIN (TYPE IO) {normalized_query if normalized_query else query}",
                'raw_explain': explain_result.get('raw', {}),
                'result_complete': explain_result.get('result_complete'),
                'error': explain_result.get('error'),
                'error_details': explain_result.get('error_details'),
                'explain_json_str': explain_result.get('explain_json_str'),
                'parsed_result': parsed_result,
                'summary': {
                    'total_tables': len(parsed_result.get('tables', {})) if parsed_result else 0,
                    'total_size_bytes': parsed_result.get('total_size_bytes', 0) if parsed_result else 0,
                    'total_size_gb': (parsed_result.get('total_size_bytes', 0) / (1024**3)) if parsed_result else 0,
                    'total_rows': parsed_result.get('total_rows', 0) if parsed_result else 0,
                    'total_cpu_cost': parsed_result.get('total_cpu_cost', 0) if parsed_result else 0,
                },
                'tables': parsed_result.get('tables', {}) if parsed_result else {}
            }
            
            os.makedirs(self.explains_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(explain_data, f, indent=2, ensure_ascii=False)
            
            if parsed_result:
                logger.info("explain_saved path=%s tables=%s size_gb=%.2f rows=%s",
                    filepath, explain_data['summary']['total_tables'], explain_data['summary']['total_size_gb'], explain_data['summary']['total_rows'])
            else:
                logger.info("explain_saved path=%s error=%s", filepath, explain_result.get('error', 'unknown'))
        except Exception as e:
            logger.exception("save_explain error=%s", str(e))

    
    def _execute_trino_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Executes a query against Trino via REST API and returns the full result."""

        try:

                             
            response = requests.post(

                f"{self.trino_url}/v1/statement",

                headers={

                    "Content-Type": "text/plain",

                    "X-Trino-User": self.trino_user

                },

                data=query,

                timeout=60                                                  

            )

            
            if response.status_code != 200:

                error_info = {
                    'status_code': response.status_code,
                    'response_text': response.text,
                    'error': f'HTTP {response.status_code}'
                }
                logger.error("trino_query_failed status=%s body=%s", response.status_code, response.text[:200])

                return error_info

            
            result = response.json()

            
            if 'error' in result:

                error_msg = result['error'].get('message', str(result['error']))
                logger.error("trino_query_error message=%s", error_msg)

                # Retorna o resultado com erro para que possamos salvá-lo
                return {
                    'error': error_msg,
                    'error_details': result.get('error'),
                    'result': result
                }

            
            next_uri = result.get('nextUri')

            all_data = []

            
            if 'data' in result and result['data']:

                all_data.extend(result['data'])

            
            while next_uri:

                next_response = requests.get(

                    next_uri,

                    headers={"X-Trino-User": self.trino_user},

                    timeout=60                                                  

                )

                
                if next_response.status_code != 200:

                    logger.error("trino_next_uri_failed status=%s", next_response.status_code)

                    break

                
                next_result = next_response.json()

                
                if 'data' in next_result:

                    all_data.extend(next_result['data'])

                
                if next_result.get('stats', {}).get('state') == 'FINISHED':

                    break

                
                next_uri = next_result.get('nextUri')

            
            return {

                'columns': result.get('columns', []),

                'data': all_data,

                'stats': result.get('stats', {})

            }

            
        except Exception as e:

            logger.exception("trino_query_exception error=%s", str(e))

            return None

    
    def _parse_explain_io(self, explain_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses EXPLAIN (TYPE IO) result to extract table, filter and cost info.
        Trino JSON structure:
        {
          "inputTableColumnInfos": [{
            "table": {
              "catalog": "iceberg",
              "schemaTable": {
                "schema": "prod_db_transient_ref",
                "table": "transient_caf_executions"
              }
            },
            "constraint": {
              "none": false,
              "columnConstraints": [{
                "columnName": "date",
                "type": "timestamp(6)",
                "domain": {
                  "ranges": [...]
                }
              }]
            },
            "estimate": {
              "outputRowCount": 1150371.0,
              "outputSizeInBytes": 3.3055640450000005E9,
              "cpuCost": 3.3055640450000005E9,
              "maxMemory": 0.0,
              "networkCost": 0.0
            }
          }],
          "estimate": {...}
        }
        """

        tables_info = {}

        total_size_bytes = 0

        total_rows = 0

        total_cpu_cost = 0

        
        input_tables = explain_result.get('inputTableColumnInfos', [])

        for table_info in input_tables:

                                                                                
            table_obj = table_info.get('table', {})

            catalog = table_obj.get('catalog', '')

            
            schema_table = table_obj.get('schemaTable', {})

            schema = schema_table.get('schema', '')

            table = schema_table.get('table', '')

            
            if not catalog:

                catalog = table_info.get('catalog', '')

            if not schema:

                schema = table_info.get('schema', '')

            if not table:

                table = table_info.get('table', '')

            
            if catalog and schema and table:

                full_table_name = f"{catalog}.{schema}.{table}"

                
                estimate = table_info.get('estimate', {})

                
                def safe_float(value):

                    if value == "NaN" or value is None:

                        return 0.0

                    try:

                        return float(value)

                    except (ValueError, TypeError):

                        return 0.0

                
                estimated_size_bytes = safe_float(estimate.get('outputSizeInBytes', 0))

                estimated_rows = safe_float(estimate.get('outputRowCount', 0))

                cpu_cost = safe_float(estimate.get('cpuCost', 0))

                
                constraints = table_info.get('constraint', {})

                column_constraints = constraints.get('columnConstraints', [])

                
                filters = []

                for constraint in column_constraints:

                    column_name = constraint.get('columnName', '')

                    domain = constraint.get('domain', {})

                    ranges = domain.get('ranges', [])

                    
                    for range_obj in ranges:

                        low = range_obj.get('low', {})

                        high = range_obj.get('high', {})

                        
                        filter_info = {

                            'column': column_name,

                            'low_value': low.get('value'),

                            'low_bound': low.get('bound'),

                            'high_value': high.get('value'),

                            'high_bound': high.get('bound')

                        }

                        filters.append(filter_info)

                
                tables_info[full_table_name] = {

                    'catalog': catalog,

                    'schema': schema,

                    'table': table,

                    'estimated_size_bytes': estimated_size_bytes,

                    'estimated_rows': estimated_rows,

                    'cpu_cost': cpu_cost,

                    'filters': filters,

                    'column_constraints': column_constraints

                }

                
                total_size_bytes += estimated_size_bytes

                total_rows += estimated_rows

                total_cpu_cost += cpu_cost

                
                logger.debug("explain_table table=%s size_bytes=%s size_gb=%.2f rows=%s cpu_cost=%s filters=%s",
                    full_table_name, estimated_size_bytes, estimated_size_bytes / (1024**3), estimated_rows, cpu_cost, len(filters))

        
        return {

            'tables': tables_info,

            'total_size_bytes': total_size_bytes,

            'total_rows': total_rows,

            'total_cpu_cost': total_cpu_cost,

            'raw': explain_result

        }

    
    def explain_io(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Runs EXPLAIN (TYPE IO) on the query and returns I/O and cost info.
        Falls back to EXPLAIN (TYPE DISTRIBUTED) if IO returns no data (e.g., for views).
        Normalizes query with iceberg catalog when needed.
        """
        normalized_query = self._normalize_query_with_catalog(query)

        # First attempt: EXPLAIN (TYPE IO)
        result = self._try_explain_io(query, normalized_query)
        if result:
            # Check if this is a view error (don't try distributed - same error)
            if result.get('view_error'):
                logger.info("explain_io view_error_detected skipping_distributed using_syntax_only")
                return result  # Return empty result, will use complexity analysis
            return result

        # Fallback: EXPLAIN (TYPE DISTRIBUTED) for views that exist but have no IO data
        logger.info("explain_io fallback_to_distributed reason=no_io_data")
        result = self._try_explain_distributed(query, normalized_query)
        if result:
            # Check for view error in distributed too
            if result.get('view_error'):
                logger.info("explain_distributed view_error_detected using_syntax_only")
                return result
            return result

        logger.warning("explain_io all_strategies_failed using_syntax_only")
        return None

    def _try_explain_io(self, original_query: str, normalized_query: str) -> Optional[Dict[str, Any]]:
        """Attempts EXPLAIN (TYPE IO) and returns parsed result or None."""
        explain_query = f"EXPLAIN (TYPE IO) {normalized_query}"
        logger.info("explain_io running query_preview=%s", explain_query[:80].replace('\n', ' '))

        result = self._execute_trino_query(explain_query)

        if result and result.get('error'):
            error_msg = result.get('error', '')

            # Check for view-related errors that should trigger syntax-only fallback
            view_errors = [
                'Failed analyzing stored view',
                'Catalog',
                'not found',
                'View',
                'cannot be resolved'
            ]
            is_view_error = any(err.lower() in error_msg.lower() for err in view_errors)

            if is_view_error:
                logger.warning("explain_io view_error detected error=%s", error_msg[:200])
                self._save_explain(original_query, {
                    'raw': result.get('result', {}),
                    'error': error_msg,
                    'error_details': result.get('error_details'),
                    'result_complete': result,
                    'explain_type': 'IO',
                    'view_error': True,
                    'note': 'View references unavailable catalog - using syntax analysis only'
                }, None, normalized_query)
                # Return special marker to skip distributed fallback too
                return {'view_error': True, 'tables': {}, 'total_size_bytes': 0, 'total_rows': 0, 'total_cpu_cost': 0}

            logger.warning("explain_io error=%s", error_msg[:200])
            self._save_explain(original_query, {
                'raw': result.get('result', {}),
                'error': error_msg,
                'error_details': result.get('error_details'),
                'result_complete': result,
                'explain_type': 'IO'
            }, None, normalized_query)
            return None

        if not result or not result.get('data'):
            logger.warning("explain_io no_data_returned")
            self._save_explain(original_query, {
                'raw': result if result else {},
                'error': 'No data returned',
                'result_complete': result,
                'explain_type': 'IO'
            }, None, normalized_query)
            return None

        try:
            explain_json_str = result['data'][0][0] if result['data'] else None

            if explain_json_str:
                explain_json_str = explain_json_str.replace('\\n', ' ').replace('\n', ' ')
                explain_json = json.loads(explain_json_str)

                num_tables = len(explain_json.get('inputTableColumnInfos', []))

                # If no tables found in IO, return None to trigger fallback
                if num_tables == 0:
                    logger.info("explain_io no_tables_found triggering_fallback")
                    self._save_explain(original_query, {
                        'raw': explain_json,
                        'result_complete': result,
                        'explain_json_str': explain_json_str,
                        'explain_type': 'IO',
                        'note': 'No tables found - may be a view'
                    }, None, normalized_query)
                    return None

                logger.debug("explain_io parsed tables=%s", num_tables)
                parsed_result = self._parse_explain_io(explain_json)
                self._save_explain(original_query, {
                    'raw': explain_json,
                    'result_complete': result,
                    'explain_json_str': explain_json_str,
                    'explain_type': 'IO'
                }, parsed_result, normalized_query)

                return parsed_result
            else:
                logger.warning("explain_io empty_json_str")
                self._save_explain(original_query, {
                    'raw': {},
                    'result_complete': result,
                    'error': 'Empty explain_json_str',
                    'explain_type': 'IO'
                }, None, normalized_query)

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error("explain_io parse_error error=%s", str(e))
            self._save_explain(original_query, {
                'raw': {},
                'error': str(e),
                'explain_json_str': explain_json_str[:500] if explain_json_str else None,
                'explain_type': 'IO'
            }, None, normalized_query)

        return None

    def _try_explain_distributed(self, original_query: str, normalized_query: str) -> Optional[Dict[str, Any]]:
        """
        Attempts EXPLAIN (TYPE DISTRIBUTED) to extract table information from views.
        Parses the text output to find TableScan nodes with table references.
        """
        explain_query = f"EXPLAIN (TYPE DISTRIBUTED) {normalized_query}"
        logger.info("explain_distributed running query_preview=%s", explain_query[:80].replace('\n', ' '))

        result = self._execute_trino_query(explain_query)

        if result and result.get('error'):
            error_msg = result.get('error', '')

            # Check for view-related errors
            view_errors = ['Failed analyzing stored view', 'Catalog', 'not found', 'View', 'cannot be resolved']
            is_view_error = any(err.lower() in error_msg.lower() for err in view_errors)

            if is_view_error:
                logger.warning("explain_distributed view_error detected error=%s", error_msg[:200])
                return {'view_error': True, 'tables': {}, 'total_size_bytes': 0, 'total_rows': 0, 'total_cpu_cost': 0}

            logger.warning("explain_distributed error=%s", error_msg[:200])
            return None

        if not result or not result.get('data'):
            logger.warning("explain_distributed no_data_returned")
            return None

        try:
            # EXPLAIN DISTRIBUTED returns text rows, not JSON
            explain_lines = []
            for row in result.get('data', []):
                if row and len(row) > 0:
                    explain_lines.append(str(row[0]))

            explain_text = '\n'.join(explain_lines)

            # Parse TableScan nodes to extract table references
            # Pattern: TableScan[table = catalog.schema.table, ...]
            # Also handles: table:schema.table:* formats
            tables_info = self._parse_distributed_plan(explain_text)

            if not tables_info.get('tables'):
                logger.warning("explain_distributed no_tables_extracted")
                self._save_explain(original_query, {
                    'raw': {'explain_text': explain_text[:2000]},
                    'error': 'No tables extracted from distributed plan',
                    'explain_type': 'DISTRIBUTED'
                }, None, normalized_query)
                return None

            logger.info("explain_distributed extracted tables=%s", len(tables_info['tables']))

            self._save_explain(original_query, {
                'raw': {'explain_text': explain_text[:5000]},
                'explain_type': 'DISTRIBUTED',
                'note': 'Fallback from IO explain (likely view)'
            }, tables_info, normalized_query)

            return tables_info

        except Exception as e:
            logger.error("explain_distributed parse_error error=%s", str(e))
            return None

    def _parse_distributed_plan(self, explain_text: str) -> Dict[str, Any]:
        """
        Parses EXPLAIN (TYPE DISTRIBUTED) output to extract table information.
        Extracts table names from TableScan nodes and estimates from cost info.
        """
        tables_info = {}
        total_size_bytes = 0
        total_rows = 0
        total_cpu_cost = 0

        # Pattern 1: TableScan[table = catalog.schema.table ...]
        pattern1 = r'TableScan\[table\s*=\s*([^\],]+)'

        # Pattern 2: ScanProject[table = catalog.schema.table ...]
        pattern2 = r'ScanProject\[table\s*=\s*([^\],]+)'

        # Pattern 3: table:catalog.schema.table (alternate format)
        pattern3 = r'table:([a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*)'

        # Pattern for cost estimates: est. {rows} rows, {size}
        cost_pattern = r'est\.\s*([\d.]+)\s*rows?,\s*([\d.]+)\s*(\w+)'

        all_patterns = [pattern1, pattern2, pattern3]

        for pattern in all_patterns:
            matches = re.findall(pattern, explain_text, re.IGNORECASE)
            for match in matches:
                table_ref = match.strip()
                # Clean up table reference
                table_ref = re.sub(r'\s+', '', table_ref)

                if table_ref and table_ref not in tables_info:
                    # Parse catalog.schema.table
                    parts = table_ref.split('.')
                    if len(parts) >= 3:
                        catalog = parts[0]
                        schema = parts[1]
                        table = '.'.join(parts[2:])  # Handle table names with dots
                    elif len(parts) == 2:
                        catalog = 'iceberg'
                        schema = parts[0]
                        table = parts[1]
                    else:
                        continue

                    full_table_name = f"{catalog}.{schema}.{table}"

                    tables_info[full_table_name] = {
                        'catalog': catalog,
                        'schema': schema,
                        'table': table,
                        'estimated_size_bytes': 0,  # Not available from distributed plan
                        'estimated_rows': 0,
                        'cpu_cost': 0,
                        'filters': [],
                        'column_constraints': [],
                        'source': 'distributed_plan'
                    }

                    logger.debug("explain_distributed table_found table=%s", full_table_name)

        # Try to extract cost estimates
        cost_matches = re.findall(cost_pattern, explain_text)
        if cost_matches and tables_info:
            # Sum up all cost estimates (rough approximation)
            for rows_str, size_str, unit in cost_matches:
                try:
                    rows = float(rows_str)
                    size = float(size_str)

                    # Convert size to bytes based on unit
                    multipliers = {'b': 1, 'kb': 1024, 'mb': 1024**2, 'gb': 1024**3, 'tb': 1024**4}
                    unit_lower = unit.lower()
                    if unit_lower in multipliers:
                        size_bytes = size * multipliers[unit_lower]
                    else:
                        size_bytes = size

                    total_rows += rows
                    total_size_bytes += size_bytes
                except (ValueError, TypeError):
                    pass

        # Distribute estimates across tables (rough approximation)
        num_tables = len(tables_info)
        if num_tables > 0 and total_size_bytes > 0:
            per_table_size = total_size_bytes / num_tables
            per_table_rows = total_rows / num_tables
            for table_name in tables_info:
                tables_info[table_name]['estimated_size_bytes'] = per_table_size
                tables_info[table_name]['estimated_rows'] = per_table_rows

        return {
            'tables': tables_info,
            'total_size_bytes': total_size_bytes,
            'total_rows': total_rows,
            'total_cpu_cost': total_cpu_cost,
            'raw': {'explain_text_preview': explain_text[:1000]},
            'source': 'distributed_plan'
        }

    
    def analyze_query_io(self, query: str) -> Dict[str, Any]:
        """Analyzes query with EXPLAIN (TYPE IO) and returns I/O and cost details."""
        explain_result = self.explain_io(query)

        if not explain_result:
            logger.warning("analyze_query_io explain_failed using_complexity_only")
            return {
                'tables': {},
                'total_size_bytes': 0,
                'total_rows': 0,
                'total_cpu_cost': 0,
                'where_clause': None,
                'explain_result': {},
                'fallback_reason': 'explain_failed'
            }

        # Check if this was a view error - use complexity analysis only
        if explain_result.get('view_error'):
            logger.info("analyze_query_io view_error using_complexity_only")
            return {
                'tables': {},
                'total_size_bytes': 0,
                'total_rows': 0,
                'total_cpu_cost': 0,
                'where_clause': self._extract_where_clause(query),
                'explain_result': explain_result,
                'fallback_reason': 'view_error_catalog_not_found'
            }

        
        where_clause = self._extract_where_clause(query)

        
        tables_metadata = {}

        
        for table_name, table_info in explain_result.get('tables', {}).items():

            tables_metadata[table_name] = {

                'table': table_name,

                'file_count': 0,                                                   

                'total_size_bytes': table_info.get('estimated_size_bytes', 0),

                'total_records': int(table_info.get('estimated_rows', 0)),

                'cpu_cost': table_info.get('cpu_cost', 0),

                'filters': table_info.get('filters', []),

                'io_analysis': table_info

            }

        
        total_size = explain_result.get('total_size_bytes', 0)

        total_rows = explain_result.get('total_rows', 0)

        total_cpu_cost = explain_result.get('total_cpu_cost', 0)

        
        logger.info("analyze_query_io done tables=%s size_bytes=%s size_gb=%.2f rows=%s", len(tables_metadata), total_size, total_size / (1024**3), total_rows)

        
        return {

            'tables': tables_metadata,

            'total_size_bytes': total_size,

            'total_rows': total_rows,

            'total_cpu_cost': total_cpu_cost,

            'where_clause': where_clause,

            'explain_result': explain_result

        }

    
    def _extract_where_clause(self, query: str) -> Optional[str]:
        """Extracts the WHERE clause from the query (for reference)."""

        query_lower = query.lower()

        where_match = re.search(r'\bwhere\s+(.+?)(?:\s+group\s+by|\s+order\s+by|\s+limit|$)', query_lower, re.IGNORECASE | re.DOTALL)

        
        if where_match:

                                                                                   
            where_start = query_lower.find('where')

            if where_start != -1:

                                                    
                remaining = query[where_start + 5:]                         

                                                  
                for keyword in ['group by', 'order by', 'limit']:

                    keyword_pos = remaining.lower().find(keyword)

                    if keyword_pos != -1:

                        remaining = remaining[:keyword_pos]

                return remaining.strip()

        
        return None

    
    def extract_tables(self, query):
        """Extracts table names from the SQL query (legacy, kept for compatibility)."""

        explain_result = self.explain_io(query)

        
        if explain_result and explain_result.get('tables'):

            return list(explain_result['tables'].keys())

        
        tables = []

        patterns = [

            r'from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)',

            r'join\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)',

        ]

        
        query_lower = query.lower()

        for pattern in patterns:

            matches = re.finditer(pattern, query_lower, re.IGNORECASE)

            for match in matches:

                table = match.group(1)

                table = table.split()[0]

                if table not in tables:

                    tables.append(table)

        
        return tables

    
    def analyze_complexity(self, query):
        """Analyzes SQL query complexity. Returns a dict of complexity metrics."""

        query_lower = query.lower()

        
        joins = len(re.findall(r'\bjoin\b', query_lower))

        
        aggregations = len(re.findall(r'\b(count|sum|avg|min|max|group_concat)\s*\(', query_lower))

        
        subqueries = len(re.findall(r'\(select\s+', query_lower))

        
        partitioned_filters = len(re.findall(r'where.*(date|data|timestamp|year|month|day)', query_lower))

        
        where_clauses = len(re.findall(r'\bwhere\b', query_lower))

        non_partitioned_filters = max(0, where_clauses - partitioned_filters)

        
        complexity = {

            'joins': joins,

            'aggregations': aggregations,

            'subqueries': subqueries,

            'partitioned_filters': partitioned_filters,

            'non_partitioned_filters': non_partitioned_filters

        }

        
        logger.debug("analyze_complexity %s", complexity)

        return complexity

