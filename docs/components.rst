=============
Componentes
=============

Descrição detalhada de cada componente do sistema DyraSQL.

DyraSQL Core
------------

O núcleo do sistema, responsável pela análise e roteamento de queries.

**Localização:** ``dyrasql-core/``

**Tecnologia:** Python 3.10+ com FastAPI

Módulos
^^^^^^^

app.py
""""""

API principal que expõe os endpoints REST.

**Endpoints:**

.. list-table::
   :widths: 20 15 65
   :header-rows: 1

   * - Endpoint
     - Método
     - Descrição
   * - ``/health``
     - GET
     - Health check
   * - ``/api/v1/route``
     - POST
     - Obter decisão de roteamento
   * - ``/api/v1/metrics``
     - POST
     - Salvar métricas pós-execução
   * - ``/v1/info``
     - GET
     - Proxy para info do Trino
   * - ``/v1/statement``
     - POST
     - Executar query com roteamento
   * - ``/{path:path}``
     - *
     - Catch-all para requests subsequentes

query_analyzer.py
"""""""""""""""""

Analisa queries SQL e extrai características.

**Funcionalidades:**

- **Fingerprint**: Hash SHA256 da query normalizada
- **Normalização**: Remove literais, padroniza formato
- **Classificação**: Identifica queries de catálogo/metadados
- **EXPLAIN**: Extrai informações de I/O e custos

**Exemplo de uso:**

.. code-block:: python

   from query_analyzer import QueryAnalyzer

   analyzer = QueryAnalyzer(trino_url="http://localhost:8081")

   result = analyzer.analyze(
       query="SELECT * FROM vendas WHERE data >= '2026-01-01'"
   )

   print(result)
   # {
   #   "fingerprint": "abc123...",
   #   "tables": ["vendas"],
   #   "data_size_gb": 2.5,
   #   "record_count": 1000000,
   #   "complexity": {
   #     "joins": 0,
   #     "aggregations": 0,
   #     "subqueries": 0
   #   }
   # }

decision_engine.py
""""""""""""""""""

Calcula o score de roteamento.

**Algoritmo:**

.. code-block:: text

   Score = w1 × fv + w2 × fc + w3 × fh

   Onde:
   - fv = Fator Volume (normalizado de tamanho e arquivos)
   - fc = Fator Complexidade (JOINs, agregações, subqueries)
   - fh = Fator Histórico (baseado em execuções anteriores)

**Seleção de Cluster:**

.. code-block:: python

   if score < ECS_THRESHOLD:
       return "ecs"
   elif score <= EMR_STANDARD_THRESHOLD:
       return "emr-standard"
   else:
       return "emr-optimized"

history_manager.py
""""""""""""""""""

Gerencia cache de decisões em DynamoDB.

**Funcionalidades:**

- Cache de decisões com TTL de 24h
- Armazenamento de métricas de execução
- Cálculo do fator histórico

**Schema DynamoDB:**

.. code-block:: python

   {
       "fingerprint": str,    # Chave primária
       "cluster": str,        # Cluster selecionado
       "score": Decimal,      # Score calculado
       "factors": str,        # JSON dos fatores
       "timestamp": str,      # ISO 8601
       "ttl": int,           # Unix timestamp
       # Métricas (opcional)
       "execution_time": Decimal,
       "cost": Decimal,
       "success": bool
   }

metadata_connector.py
"""""""""""""""""""""

Conecta a tabelas Apache Iceberg.

**Fontes de dados:**

1. **Iceberg Catalog** (primário)
2. **S3 direto** (fallback)

**Metadados extraídos:**

- Contagem de arquivos
- Tamanho total
- Contagem de registros
- Informações de partição

Clusters Trino
--------------

Três clusters com recursos diferentes.

Trino ECS
^^^^^^^^^

**Propósito:** Queries leves (Score < 0.3)

**Características:**

- Memória: 2-4GB
- Workers: 2
- Porta: 8081
- Use cases: Metadados, COUNT simples, SHOW commands

**Configuração típica:**

.. code-block:: properties

   # config.properties
   coordinator=true
   node-scheduler.include-coordinator=true
   http-server.http.port=8080
   query.max-memory=2GB
   query.max-memory-per-node=1GB

Trino EMR Standard
^^^^^^^^^^^^^^^^^^

**Propósito:** Queries médias (Score 0.3-0.7)

**Características:**

- Memória: 8-12GB
- Workers: 4
- Porta: 8082
- Use cases: Agregações, JOINs simples

**Configuração típica:**

.. code-block:: properties

   # config.properties
   coordinator=true
   node-scheduler.include-coordinator=true
   http-server.http.port=8080
   query.max-memory=8GB
   query.max-memory-per-node=4GB

Trino EMR Optimized
^^^^^^^^^^^^^^^^^^^

**Propósito:** Queries pesadas (Score > 0.7)

**Características:**

- Memória: 16-24GB
- Workers: 8
- Porta: 8083
- Use cases: Múltiplos JOINs, grandes volumes

**Configuração típica:**

.. code-block:: properties

   # config.properties
   coordinator=true
   node-scheduler.include-coordinator=true
   http-server.http.port=8080
   query.max-memory=16GB
   query.max-memory-per-node=8GB

Catálogos Configurados
^^^^^^^^^^^^^^^^^^^^^^

Cada cluster tem os seguintes catálogos:

**Iceberg** (``catalog/iceberg.properties``):

.. code-block:: properties

   connector.name=iceberg
   iceberg.catalog.type=glue
   hive.metastore.glue.region=${AWS_REGION}

**System** (built-in):

- ``system.runtime``: Métricas de runtime
- ``system.jdbc``: Informações JDBC
- ``information_schema``: Schema information

Trino Gateway
-------------

Gateway oficial para roteamento de queries.

**Localização:** ``trino-gateway/``

**Portas:**

- 8085 → 8080 (API principal)
- 8084 → 8081 (API admin)

Configuração
^^^^^^^^^^^^

.. code-block:: yaml

   # config.yaml
   serverConfig:
     node.environment: production
     http-server.http.port: 8080

   routingRules:
     rulesEngineEnabled: false

   dataStore:
     jdbcUrl: jdbc:postgresql://gateway-db:5432/trino_gateway
     driver: org.postgresql.Driver

   clusterStatsConfiguration:
     monitorType: INFO_API

Estado Atual
^^^^^^^^^^^^

- Usa round-robin básico
- Integração completa com DyraSQL Core requer provider Java customizado

Trino Gateway Proxy
-------------------

Proxy alternativo com integração DyraSQL.

**Localização:** ``trino-gateway-proxy/``

**Porta:** 8080

**Funcionalidades:**

- Intercepta queries POST
- Chama DyraSQL Core para roteamento
- Reescrita de URLs
- Suporte a streaming

Fluxo
^^^^^

.. code-block:: text

   1. Cliente → POST /v1/statement
   2. Proxy → DyraSQL Core /api/v1/route
   3. DyraSQL → Retorna cluster
   4. Proxy → POST para cluster
   5. Cluster → Resposta
   6. Proxy → Reescrita de URLs
   7. Proxy → Cliente

Gateway Database
----------------

PostgreSQL para configuração do Trino Gateway.

**Serviço:** ``gateway-db``

**Imagem:** ``postgres:16-alpine``

**Credenciais:**

- Database: ``trino_gateway``
- User: ``gateway``
- Password: ``gateway123``
- Port: ``5432``

**Conteúdo:**

- Configuração de backends
- Regras de roteamento
- Métricas do gateway

Próximos Passos
---------------

- :doc:`routing-algorithm` - Detalhes do algoritmo
- :doc:`api-reference` - Referência da API
- :doc:`usage` - Guia de uso
