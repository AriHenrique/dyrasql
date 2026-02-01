=================
Referência da API
=================

Documentação completa dos endpoints da API DyraSQL.

Visão Geral
-----------

Base URL: ``http://localhost:5001``

Content Types:

- JSON: ``application/json``
- Text: ``text/plain``

Headers comuns:

- ``X-Trino-User``: Usuário Trino (obrigatório para queries)
- ``X-Trino-Source``: Fonte da query (opcional)
- ``X-Trino-Catalog``: Catálogo padrão (opcional)
- ``X-Trino-Schema``: Schema padrão (opcional)

Endpoints
---------

GET /health
^^^^^^^^^^^

Health check do serviço.

**Request:**

.. code-block:: bash

   curl http://localhost:5001/health

**Response (200 OK):**

.. code-block:: json

   {
     "status": "healthy",
     "timestamp": "2024-01-15T12:00:00Z",
     "version": "1.0.0"
   }

POST /api/v1/route
^^^^^^^^^^^^^^^^^^

Obtém decisão de roteamento para uma query.

**Request:**

.. code-block:: bash

   curl -X POST http://localhost:5001/api/v1/route \
     -H "Content-Type: application/json" \
     -d '{
       "query": "SELECT COUNT(*) FROM iceberg.default.vendas"
     }'

**Request Body:**

.. list-table::
   :widths: 20 15 15 50
   :header-rows: 1

   * - Campo
     - Tipo
     - Obrigatório
     - Descrição
   * - ``query``
     - string
     - Sim
     - Query SQL a ser analisada

**Response (200 OK):**

.. code-block:: json

   {
     "fingerprint": "a1b2c3d4e5f6789...",
     "cluster": "ecs",
     "score": 0.25,
     "factors": {
       "volume": 0.20,
       "complexity": 0.10,
       "historical": 0.30
     },
     "cached": false,
     "analysis": {
       "tables": ["iceberg.default.vendas"],
       "data_size_gb": 0.5,
       "record_count": 100000,
       "joins": 0,
       "aggregations": 1,
       "subqueries": 0
     },
     "cluster_url": "http://trino-ecs:8080",
     "cluster_external_url": "http://localhost:8081"
   }

**Response Fields:**

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Campo
     - Tipo
     - Descrição
   * - ``fingerprint``
     - string
     - Hash SHA256 da query normalizada
   * - ``cluster``
     - string
     - Cluster selecionado (ecs, emr-standard, emr-optimized)
   * - ``score``
     - float
     - Score calculado (0.0-1.0)
   * - ``factors``
     - object
     - Fatores individuais do score
   * - ``cached``
     - boolean
     - Se decisão veio do cache
   * - ``analysis``
     - object
     - Detalhes da análise (se não cached)
   * - ``cluster_url``
     - string
     - URL interna do cluster
   * - ``cluster_external_url``
     - string
     - URL externa do cluster

POST /api/v1/metrics
^^^^^^^^^^^^^^^^^^^^

Salva métricas pós-execução de uma query.

**Request:**

.. code-block:: bash

   curl -X POST http://localhost:5001/api/v1/metrics \
     -H "Content-Type: application/json" \
     -d '{
       "fingerprint": "a1b2c3d4e5f6789...",
       "execution_time": 5.2,
       "bytes_processed": 1073741824,
       "success": true,
       "error_message": null
     }'

**Request Body:**

.. list-table::
   :widths: 20 15 15 50
   :header-rows: 1

   * - Campo
     - Tipo
     - Obrigatório
     - Descrição
   * - ``fingerprint``
     - string
     - Sim
     - Fingerprint da query
   * - ``execution_time``
     - float
     - Sim
     - Tempo de execução em segundos
   * - ``bytes_processed``
     - int
     - Não
     - Bytes processados
   * - ``success``
     - boolean
     - Sim
     - Se execução foi bem sucedida
   * - ``error_message``
     - string
     - Não
     - Mensagem de erro (se houver)

**Response (200 OK):**

.. code-block:: json

   {
     "status": "saved",
     "fingerprint": "a1b2c3d4e5f6789..."
   }

GET /v1/info
^^^^^^^^^^^^

Proxy para endpoint info do Trino.

**Request:**

.. code-block:: bash

   curl http://localhost:5001/v1/info

**Response (200 OK):**

.. code-block:: json

   {
     "nodeVersion": {
       "version": "435"
     },
     "environment": "production",
     "coordinator": true,
     "starting": false,
     "uptime": "1.00d"
   }

POST /v1/statement
^^^^^^^^^^^^^^^^^^

Executa uma query SQL com roteamento inteligente.

**Request:**

.. code-block:: bash

   curl -X POST http://localhost:5001/v1/statement \
     -H "Content-Type: text/plain" \
     -H "X-Trino-User: admin" \
     -d "SELECT COUNT(*) FROM iceberg.default.vendas"

**Headers:**

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Header
     - Obrigatório
     - Descrição
   * - ``X-Trino-User``
     - Sim
     - Usuário Trino
   * - ``X-Trino-Source``
     - Não
     - Identificador da aplicação
   * - ``X-Trino-Catalog``
     - Não
     - Catálogo padrão
   * - ``X-Trino-Schema``
     - Não
     - Schema padrão

**Response (200 OK):**

.. code-block:: json

   {
     "id": "20240115_120000_00001_xxxxx",
     "infoUri": "http://localhost:8081/v1/query/20240115_120000_00001_xxxxx",
     "nextUri": "http://localhost:8081/v1/statement/queued/20240115_120000_00001_xxxxx/1",
     "stats": {
       "state": "QUEUED",
       "queued": true,
       "scheduled": false,
       "nodes": 0,
       "totalSplits": 0,
       "queuedSplits": 0,
       "runningSplits": 0,
       "completedSplits": 0,
       "cpuTimeMillis": 0,
       "wallTimeMillis": 0,
       "processedRows": 0,
       "processedBytes": 0
     }
   }

.. note::

   O ``nextUri`` apontará para o cluster selecionado se ``BYPASS_MODE=true``.
   O cliente deve seguir o ``nextUri`` para obter os resultados.

GET /{path:path}
^^^^^^^^^^^^^^^^

Catch-all para requests subsequentes (paginação de resultados).

O DyraSQL Core mantém mapeamento de query ID para cluster, garantindo que
requests de follow-up sejam roteados para o cluster correto.

Códigos de Resposta
-------------------

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Código
     - Descrição
   * - 200
     - Sucesso
   * - 400
     - Requisição inválida (query malformada)
   * - 401
     - Não autorizado (header X-Trino-User ausente)
   * - 404
     - Recurso não encontrado
   * - 500
     - Erro interno do servidor
   * - 502
     - Erro de comunicação com cluster Trino
   * - 503
     - Serviço indisponível

Erros
-----

Formato de Erro
^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "error": {
       "message": "Descrição do erro",
       "errorCode": 1,
       "errorName": "GENERIC_INTERNAL_ERROR",
       "errorType": "INTERNAL_ERROR"
     }
   }

Tipos de Erro Comuns
^^^^^^^^^^^^^^^^^^^^

**Query Syntax Error:**

.. code-block:: json

   {
     "error": {
       "message": "line 1:1: mismatched input 'SELEC' expecting ...",
       "errorCode": 1,
       "errorName": "SYNTAX_ERROR",
       "errorType": "USER_ERROR"
     }
   }

**Table Not Found:**

.. code-block:: json

   {
     "error": {
       "message": "Table 'iceberg.default.tabela_inexistente' does not exist",
       "errorCode": 1,
       "errorName": "TABLE_NOT_FOUND",
       "errorType": "USER_ERROR"
     }
   }

**Cluster Unavailable:**

.. code-block:: json

   {
     "error": {
       "message": "Failed to connect to cluster ecs",
       "errorCode": 503,
       "errorName": "CLUSTER_UNAVAILABLE",
       "errorType": "INTERNAL_ERROR"
     }
   }

Rate Limiting
-------------

Atualmente não há rate limiting implementado. Para produção, considere:

- Implementar rate limiting por usuário/IP
- Usar cache mais agressivo
- Load balancer com rate limiting

Exemplos de Integração
----------------------

cURL
^^^^

.. code-block:: bash

   # Health check
   curl -s http://localhost:5001/health | jq

   # Roteamento
   curl -s -X POST http://localhost:5001/api/v1/route \
     -H "Content-Type: application/json" \
     -d '{"query": "SELECT 1"}' | jq

   # Query com follow-up
   response=$(curl -s -X POST http://localhost:5001/v1/statement \
     -H "Content-Type: text/plain" \
     -H "X-Trino-User: admin" \
     -d "SELECT COUNT(*) FROM iceberg.default.vendas")

   next_uri=$(echo $response | jq -r '.nextUri')

   while [ "$next_uri" != "null" ]; do
     response=$(curl -s "$next_uri")
     next_uri=$(echo $response | jq -r '.nextUri')
   done

   echo $response | jq '.data'

Python (requests)
^^^^^^^^^^^^^^^^^

.. code-block:: python

   import requests
   import time

   BASE_URL = "http://localhost:5001"

   def execute_query(query: str) -> list:
       # Enviar query
       response = requests.post(
           f"{BASE_URL}/v1/statement",
           headers={
               "Content-Type": "text/plain",
               "X-Trino-User": "admin"
           },
           data=query
       )
       result = response.json()

       # Seguir nextUri até completar
       while "nextUri" in result:
           time.sleep(0.1)  # Evitar polling excessivo
           response = requests.get(result["nextUri"])
           result = response.json()

       return result.get("data", [])

   # Uso
   data = execute_query("SELECT COUNT(*) FROM iceberg.default.vendas")
   print(data)

Python (trino-python-client)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from trino.dbapi import connect

   conn = connect(
       host="localhost",
       port=5001,
       user="admin",
       catalog="iceberg",
       schema="default"
   )

   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM vendas")
   result = cursor.fetchall()
   print(result)

Próximos Passos
---------------

- :doc:`usage` - Guia prático de uso
- :doc:`troubleshooting` - Resolução de problemas
- :doc:`configuration` - Configuração avançada
