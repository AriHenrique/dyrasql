============
Arquitetura
============

Visão geral da arquitetura do sistema DyraSQL.

Diagrama de Arquitetura
-----------------------

.. figure:: _static/architecture.png
   :alt: Arquitetura DyraSQL
   :align: center
   :width: 100%

   Diagrama C4 da arquitetura do sistema DyraSQL

O DyraSQL é composto pelos seguintes componentes principais:

- **DyraSQL Core**: Motor de roteamento inteligente
- **Trino Clusters**: ECS (leve), EMR Standard (médio), EMR Optimized (pesado)
- **AWS Services**: DynamoDB (cache), S3 (dados), Glue (catálogo)

Fluxo de Execução
-----------------

1. **Recebimento da Query**

   - Cliente envia query SQL via REST API ou JDBC
   - Trino Gateway recebe na porta 8080
   - Request é encaminhado ao DyraSQL Core

2. **Análise da Query**

   - Query Analyzer gera fingerprint (hash SHA256)
   - Verifica cache em DynamoDB
   - Se cached: retorna decisão imediatamente
   - Se não cached: continua análise

3. **Execução de EXPLAIN**

   - Executa ``EXPLAIN (TYPE IO)`` no cluster ECS
   - Extrai metadados: tamanho, registros, custo CPU
   - Fallback: ``EXPLAIN (TYPE DISTRIBUTED)`` para views

4. **Cálculo do Score**

   - Decision Engine calcula fatores
   - Score = w1×fv + w2×fc + w3×fh
   - Seleciona cluster baseado nos thresholds

5. **Roteamento**

   - Query é enviada ao cluster selecionado
   - Decisão é salva em cache (TTL: 24h)
   - URLs são reescritas conforme modo bypass

6. **Retorno dos Resultados**

   - Resultados são retornados via streaming
   - Requests subsequentes são roteados ao mesmo cluster
   - Métricas de execução são salvas para histórico

Containers Docker
-----------------

O ambiente é composto por 7 containers:

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Container
     - Porta
     - Descrição
   * - ``trino-gateway-proxy``
     - 8080
     - Ponto de entrada alternativo
   * - ``trino-gateway``
     - 8085
     - Gateway oficial Trino
   * - ``gateway-db``
     - 5432
     - PostgreSQL para Gateway
   * - ``dyrasql-core``
     - 5001
     - Motor de roteamento inteligente
   * - ``trino-ecs``
     - 8081
     - Cluster para queries leves
   * - ``trino-emr-standard``
     - 8082
     - Cluster para queries médias
   * - ``trino-emr-optimized``
     - 8083
     - Cluster para queries pesadas

Rede Docker
-----------

Todos os containers estão conectados via rede bridge ``dyrasql-network``:

.. code-block:: yaml

   networks:
     dyrasql-network:
       driver: bridge

Comunicação interna usa nomes DNS dos containers:

- ``trino-ecs:8080``
- ``trino-emr-standard:8080``
- ``trino-emr-optimized:8080``
- ``dyrasql-core:5000``

Integração com AWS
------------------

DynamoDB
^^^^^^^^

- **Tabela**: ``dyrasql-history``
- **Chave primária**: ``fingerprint`` (String)
- **TTL**: 24 horas (atributo ``ttl``)
- **Billing**: Pay per request

Schema:

.. code-block:: json

   {
     "fingerprint": "abc123...",
     "cluster": "ecs",
     "score": "0.25",
     "factors": "{\"volume\": 0.2, \"complexity\": 0.15}",
     "timestamp": "2024-01-01T12:00:00Z",
     "ttl": 1704196800
   }

S3
^^

Estrutura esperada para tabelas Iceberg:

.. code-block:: text

   s3://bucket/prefix/
   └── nome_tabela/
       ├── data/
       │   ├── part-00000.parquet
       │   ├── part-00001.parquet
       │   └── ...
       └── metadata/
           ├── v1.metadata.json
           ├── snap-xxx.avro
           └── ...

AWS Glue Catalog
^^^^^^^^^^^^^^^^

- Metadados de tabelas Iceberg
- Descoberta automática de schemas
- Particionamento e estatísticas

Modos de Operação
-----------------

Modo Proxy (Bypass = false)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Todo tráfego passa pelo DyraSQL Core:

.. code-block:: text

   Cliente → Gateway → DyraSQL Core → Cluster → DyraSQL Core → Cliente

**Vantagens:**

- Controle total sobre requests
- Coleta de métricas detalhadas

**Desvantagens:**

- Maior latência
- Overhead de memória para respostas grandes

Modo Bypass (Bypass = true)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Após roteamento inicial, cliente se conecta diretamente:

.. code-block:: text

   1. Cliente → DyraSQL Core (roteamento)
   2. Cliente → Cluster (dados diretos)

**Vantagens:**

- Menor latência
- Eficiente para grandes volumes

**Desvantagens:**

- Menos controle sobre requests subsequentes

Alta Disponibilidade
--------------------

O ambiente atual é para desenvolvimento/teste. Para produção:

Recomendações
^^^^^^^^^^^^^

1. **DyraSQL Core**

   - Deploy em múltiplas instâncias
   - Load balancer na frente
   - Health checks configurados

2. **Clusters Trino**

   - Usar ECS/EMR reais na AWS
   - Configurar auto-scaling
   - Múltiplos workers por cluster

3. **DynamoDB**

   - Configurar backups
   - Monitorar throttling
   - Considerar DAX para cache

4. **Monitoramento**

   - CloudWatch para métricas
   - Alertas para latência/erros
   - Dashboard de roteamento

Próximos Passos
---------------

- :doc:`components` - Detalhes dos componentes
- :doc:`routing-algorithm` - Algoritmo de roteamento
- :doc:`api-reference` - Referência da API
