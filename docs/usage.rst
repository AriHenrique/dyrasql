==========
Guia de Uso
==========

Guia prático de uso do DyraSQL.

Executando Queries
------------------

Via REST API
^^^^^^^^^^^^

**Query simples:**

.. code-block:: bash

   curl -X POST http://localhost:5001/v1/statement \
     -H "Content-Type: text/plain" \
     -H "X-Trino-User: admin" \
     -d "SELECT 1"

**Query com catálogo Iceberg:**

.. code-block:: bash

   curl -X POST http://localhost:5001/v1/statement \
     -H "Content-Type: text/plain" \
     -H "X-Trino-User: admin" \
     -d "SELECT COUNT(*) FROM iceberg.default.vendas"

Via Trino CLI
^^^^^^^^^^^^^

.. code-block:: bash

   # Conectar ao DyraSQL Core
   trino --server http://localhost:5001 --user admin

   # No prompt
   trino> USE iceberg.default;
   trino> SELECT * FROM vendas LIMIT 10;

Via DBeaver
^^^^^^^^^^^

1. Criar nova conexão
2. Tipo: Trino
3. Host: localhost
4. Port: 5001
5. User: admin
6. Testar conexão

Consultando Decisões de Roteamento
----------------------------------

API de Roteamento
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   curl -X POST http://localhost:5001/api/v1/route \
     -H "Content-Type: application/json" \
     -d '{
       "query": "SELECT COUNT(*) FROM iceberg.default.vendas"
     }'

Resposta:

.. code-block:: json

   {
     "fingerprint": "abc123...",
     "cluster": "ecs",
     "score": 0.25,
     "factors": {
       "volume": 0.20,
       "complexity": 0.10,
       "historical": 0.30
     },
     "cached": false,
     "cluster_url": "http://trino-ecs:8080",
     "cluster_external_url": "http://localhost:8081"
   }

Verificando Cache
^^^^^^^^^^^^^^^^^

Queries idênticas retornam ``cached: true``:

.. code-block:: bash

   # Primeira execução
   curl -X POST http://localhost:5001/api/v1/route \
     -d '{"query": "SELECT 1"}' | jq .cached
   # false

   # Segunda execução (mesmo fingerprint)
   curl -X POST http://localhost:5001/api/v1/route \
     -d '{"query": "SELECT 1"}' | jq .cached
   # true

Monitoramento
-------------

Logs em Tempo Real
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Todos os serviços
   docker compose logs -f

   # Apenas DyraSQL Core
   docker compose logs -f dyrasql-core

   # Múltiplos serviços
   docker compose logs -f dyrasql-core trino-ecs

Health Checks
^^^^^^^^^^^^^

.. code-block:: bash

   # Script de verificação
   for port in 5001 8081 8082 8083; do
     echo "Port $port: $(curl -s http://localhost:$port/health 2>/dev/null || echo 'DOWN')"
   done

Métricas do Cluster
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Informações do cluster
   curl -s http://localhost:8081/v1/info | jq

   # Queries ativas
   curl -s http://localhost:8081/v1/query | jq

Exemplos de Queries
-------------------

Queries Leves (→ ECS)
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Metadados
   SHOW CATALOGS;
   SHOW TABLES FROM iceberg.default;
   DESCRIBE iceberg.default.vendas;

   -- Contagens simples
   SELECT COUNT(*) FROM iceberg.default.vendas;

   -- Lookups por chave
   SELECT * FROM iceberg.default.clientes WHERE id = 12345;

Queries Médias (→ EMR Standard)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Agregações
   SELECT
       produto,
       COUNT(*) as total,
       SUM(valor) as receita
   FROM iceberg.default.vendas
   WHERE data_venda >= '2024-01-01'
   GROUP BY produto;

   -- JOIN simples
   SELECT v.*, c.nome
   FROM iceberg.default.vendas v
   JOIN iceberg.default.clientes c ON v.cliente_id = c.id
   WHERE v.data_venda = '2024-01-15';

Queries Pesadas (→ EMR Optimized)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Múltiplos JOINs e agregações
   SELECT
       c.regiao,
       p.categoria,
       DATE_TRUNC('month', v.data_venda) as mes,
       COUNT(DISTINCT v.id) as num_vendas,
       SUM(v.valor) as receita_total,
       AVG(v.valor) as ticket_medio
   FROM iceberg.default.vendas v
   JOIN iceberg.default.clientes c ON v.cliente_id = c.id
   JOIN iceberg.default.produtos p ON v.produto_id = p.id
   WHERE v.data_venda BETWEEN '2023-01-01' AND '2024-12-31'
   GROUP BY c.regiao, p.categoria, DATE_TRUNC('month', v.data_venda)
   HAVING SUM(v.valor) > 10000
   ORDER BY receita_total DESC;

   -- Subqueries
   SELECT *
   FROM iceberg.default.clientes
   WHERE id IN (
       SELECT cliente_id
       FROM iceberg.default.vendas
       WHERE valor > (
           SELECT AVG(valor) * 2
           FROM iceberg.default.vendas
       )
   );

Operações Administrativas
-------------------------

Reiniciar Serviços
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Reiniciar um serviço específico
   docker compose restart dyrasql-core

   # Reiniciar todos
   docker compose restart

Reconstruir Imagens
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Após alterações no código
   docker compose build dyrasql-core
   docker compose up -d dyrasql-core

Limpar Volumes
^^^^^^^^^^^^^^

.. code-block:: bash

   # Parar e remover volumes (CUIDADO: perde dados)
   docker compose down -v

   # Reiniciar do zero
   docker compose up -d

Acessar Container
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Shell no container
   docker compose exec dyrasql-core /bin/bash

   # Logs do container
   docker compose logs dyrasql-core --tail=100

Trabalhando com Iceberg
-----------------------

Criar Tabela
^^^^^^^^^^^^

.. code-block:: sql

   CREATE TABLE iceberg.default.nova_tabela (
       id BIGINT,
       nome VARCHAR,
       valor DECIMAL(10, 2),
       data_criacao TIMESTAMP
   ) WITH (
       format = 'PARQUET',
       partitioning = ARRAY['day(data_criacao)']
   );

Inserir Dados
^^^^^^^^^^^^^

.. code-block:: sql

   INSERT INTO iceberg.default.nova_tabela
   VALUES
       (1, 'Produto A', 99.90, TIMESTAMP '2024-01-15 10:00:00'),
       (2, 'Produto B', 149.90, TIMESTAMP '2024-01-15 11:00:00');

Consultar Metadados
^^^^^^^^^^^^^^^^^^^

.. code-block:: sql

   -- Snapshots da tabela
   SELECT * FROM iceberg.default."nova_tabela$snapshots";

   -- Histórico de alterações
   SELECT * FROM iceberg.default."nova_tabela$history";

   -- Arquivos da tabela
   SELECT * FROM iceberg.default."nova_tabela$files";

Integração com Aplicações
-------------------------

Python
^^^^^^

.. code-block:: python

   import requests

   # Obter decisão de roteamento
   response = requests.post(
       "http://localhost:5001/api/v1/route",
       json={"query": "SELECT COUNT(*) FROM vendas"}
   )
   decision = response.json()
   print(f"Cluster: {decision['cluster']}, Score: {decision['score']}")

   # Executar query
   response = requests.post(
       "http://localhost:5001/v1/statement",
       headers={
           "Content-Type": "text/plain",
           "X-Trino-User": "admin"
       },
       data="SELECT COUNT(*) FROM iceberg.default.vendas"
   )
   result = response.json()

Java (JDBC)
^^^^^^^^^^^

.. code-block:: java

   import java.sql.*;

   public class DyraSQLExample {
       public static void main(String[] args) throws SQLException {
           String url = "jdbc:trino://localhost:5001/iceberg/default";
           String user = "admin";

           try (Connection conn = DriverManager.getConnection(url, user, null);
                Statement stmt = conn.createStatement();
                ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM vendas")) {
               while (rs.next()) {
                   System.out.println("Count: " + rs.getLong(1));
               }
           }
       }
   }

Próximos Passos
---------------

- :doc:`api-reference` - Referência completa da API
- :doc:`troubleshooting` - Resolução de problemas
- :doc:`configuration` - Configuração avançada
