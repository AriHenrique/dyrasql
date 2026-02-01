=============
Início Rápido
=============

Este guia mostra como começar a usar o DyraSQL em poucos minutos.

Verificando a Instalação
------------------------

Antes de continuar, verifique se todos os serviços estão rodando:

.. code-block:: bash

   docker compose ps

Você deve ver todos os serviços com status ``running``:

- ``dyrasql-core``
- ``trino-ecs``
- ``trino-emr-standard``
- ``trino-emr-optimized``
- ``trino-gateway``
- ``gateway-db``

Executando sua Primeira Query
-----------------------------

1. Via API REST
^^^^^^^^^^^^^^^

Execute uma query simples diretamente no DyraSQL Core:

.. code-block:: bash

   curl -X POST http://localhost:5001/v1/statement \
     -H "Content-Type: text/plain" \
     -H "X-Trino-User: admin" \
     -d "SELECT 1"

Resposta esperada:

.. code-block:: json

   {
     "id": "20240101_123456_00001_xxxxx",
     "infoUri": "http://localhost:8081/v1/query/...",
     "nextUri": "http://localhost:8081/v1/statement/...",
     "stats": {
       "state": "QUEUED",
       "queued": true
     }
   }

2. Via Trino CLI
^^^^^^^^^^^^^^^^

Se você tem o Trino CLI instalado:

.. code-block:: bash

   trino --server http://localhost:5001 --user admin

No prompt do Trino:

.. code-block:: sql

   trino> SELECT 1;
    _col0
   -------
       1

   trino> SHOW CATALOGS;
      Catalog
   -----------
    iceberg
    system

3. Via Interface Web
^^^^^^^^^^^^^^^^^^^^

Acesse a interface web do Trino em qualquer cluster:

- **Trino ECS**: http://localhost:8081/ui
- **Trino EMR Standard**: http://localhost:8082/ui
- **Trino EMR Optimized**: http://localhost:8083/ui

Verificando Decisões de Roteamento
----------------------------------

Consulte a API de roteamento para ver como uma query seria roteada:

.. code-block:: bash

   curl -X POST http://localhost:5001/api/v1/route \
     -H "Content-Type: application/json" \
     -d '{
       "query": "SELECT COUNT(*) FROM iceberg.default.vendas WHERE data_venda >= '\''2024-01-01'\''"
     }'

Resposta esperada:

.. code-block:: json

   {
     "fingerprint": "a1b2c3d4e5f6...",
     "cluster": "ecs",
     "score": 0.25,
     "factors": {
       "volume": 0.20,
       "complexity": 0.15,
       "historical": 0.30
     },
     "cached": false,
     "cluster_url": "http://trino-ecs:8080",
     "cluster_external_url": "http://localhost:8081"
   }

Interpretando o Score
---------------------

O DyraSQL calcula um score para cada query:

.. list-table::
   :widths: 25 25 50
   :header-rows: 1

   * - Score
     - Cluster
     - Tipo de Query
   * - < 0.3
     - ECS
     - Queries leves (metadados, COUNT simples)
   * - 0.3 - 0.7
     - EMR Standard
     - Queries médias (agregações, alguns JOINs)
   * - > 0.7
     - EMR Optimized
     - Queries pesadas (múltiplos JOINs, grandes volumes)

Exemplos de Queries
-------------------

Query Leve (Score < 0.3)
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Routed to ECS
   SELECT COUNT(*) FROM iceberg.default.vendas;

   -- Routed to ECS (metadata query)
   SHOW TABLES FROM iceberg.default;

Query Média (Score 0.3-0.7)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Routed to EMR Standard
   SELECT
       produto,
       SUM(quantidade) as total
   FROM iceberg.default.vendas
   WHERE data_venda >= '2024-01-01'
   GROUP BY produto;

Query Pesada (Score > 0.7)
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Routed to EMR Optimized
   SELECT
       v.produto,
       c.nome_cliente,
       SUM(v.valor) as total_vendas
   FROM iceberg.default.vendas v
   JOIN iceberg.default.clientes c ON v.cliente_id = c.id
   JOIN iceberg.default.produtos p ON v.produto_id = p.id
   WHERE v.data_venda BETWEEN '2023-01-01' AND '2024-12-31'
   GROUP BY v.produto, c.nome_cliente
   HAVING SUM(v.valor) > 10000
   ORDER BY total_vendas DESC;

Monitorando Logs
----------------

Veja os logs do DyraSQL Core para acompanhar as decisões:

.. code-block:: bash

   docker compose logs -f dyrasql-core

Exemplo de log:

.. code-block:: text

   INFO: Query fingerprint: a1b2c3d4...
   INFO: Volume factor: 0.20
   INFO: Complexity factor: 0.15
   INFO: Historical factor: 0.30
   INFO: Final score: 0.25
   INFO: Routing to cluster: ecs

Próximos Passos
---------------

- :doc:`configuration` - Configure pesos e thresholds
- :doc:`routing-algorithm` - Entenda o algoritmo de roteamento
- :doc:`api-reference` - Referência completa da API
