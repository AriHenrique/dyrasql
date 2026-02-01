=======================
Algoritmo de Roteamento
=======================

Detalhes do algoritmo de roteamento inteligente do DyraSQL.

Visão Geral
-----------

O DyraSQL utiliza um algoritmo baseado em score para decidir qual cluster
Trino deve executar cada query. O score é calculado a partir de três fatores:

- **Fator Volume (fv)**: Baseado no tamanho dos dados
- **Fator Complexidade (fc)**: Baseado na estrutura da query
- **Fator Histórico (fh)**: Baseado em execuções anteriores

Fórmula do Score
----------------

.. code-block:: text

   Score = w1 × fv + w2 × fc + w3 × fh

Onde:

- **w1** = ``DYRASQL_WEIGHT_VOLUME`` (default: 0.7)
- **w2** = ``DYRASQL_WEIGHT_COMPLEXITY`` (default: 0.2)
- **w3** = ``DYRASQL_WEIGHT_HISTORICAL`` (default: 0.1)

.. note::

   A soma dos pesos deve ser aproximadamente 1.0 para melhores resultados.

Fator Volume (fv)
-----------------

O fator volume é calculado a partir dos metadados da tabela.

Cálculo
^^^^^^^

.. code-block:: python

   def calculate_volume_factor(data_size_gb: float, file_count: int) -> float:
       # Normalização do tamanho (0-1)
       size_score = min(data_size_gb / 100.0, 1.0)  # Cap em 100GB

       # Normalização da contagem de arquivos (0-1)
       file_score = min(file_count / 1000.0, 1.0)  # Cap em 1000 arquivos

       # Média ponderada
       return 0.7 * size_score + 0.3 * file_score

Extração de Metadados
^^^^^^^^^^^^^^^^^^^^^

Os metadados são obtidos via ``EXPLAIN (TYPE IO)``:

.. code-block:: sql

   EXPLAIN (TYPE IO)
   SELECT * FROM vendas WHERE data >= '2024-01-01'

Resposta:

.. code-block:: json

   {
     "inputTableColumnInfos": [
       {
         "table": {
           "catalog": "iceberg",
           "schema": "default",
           "table": "vendas"
         },
         "estimate": {
           "outputRowCount": 1000000,
           "outputSizeInBytes": 2684354560
         }
       }
     ]
   }

Fator Complexidade (fc)
-----------------------

O fator complexidade analisa a estrutura da query SQL.

Componentes
^^^^^^^^^^^

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Componente
     - Peso
     - Descrição
   * - JOINs
     - 0.3
     - Cada JOIN adiciona 0.1 (máx 0.3)
   * - Agregações
     - 0.2
     - GROUP BY, HAVING, funções de agregação
   * - Subqueries
     - 0.3
     - Cada subquery adiciona 0.1 (máx 0.3)
   * - Filtros particionados
     - -0.1
     - Reduz complexidade (partition pruning)
   * - Filtros não-particionados
     - 0.1
     - Aumenta complexidade (full scan)

Cálculo
^^^^^^^

.. code-block:: python

   def calculate_complexity_factor(query_analysis: dict) -> float:
       complexity = 0.0

       # JOINs (cada um adiciona 0.1, máx 0.3)
       joins = query_analysis.get("joins", 0)
       complexity += min(joins * 0.1, 0.3)

       # Agregações
       if query_analysis.get("has_aggregation", False):
           complexity += 0.2

       # Subqueries
       subqueries = query_analysis.get("subqueries", 0)
       complexity += min(subqueries * 0.1, 0.3)

       # Filtros particionados (reduz complexidade)
       if query_analysis.get("has_partition_filter", False):
           complexity -= 0.1

       # Filtros não-particionados (aumenta complexidade)
       if query_analysis.get("has_non_partition_filter", False):
           complexity += 0.1

       return max(0.0, min(complexity, 1.0))

Exemplos
^^^^^^^^

**Query simples (fc ≈ 0.0):**

.. code-block:: sql

   SELECT COUNT(*) FROM vendas

**Query média (fc ≈ 0.3):**

.. code-block:: sql

   SELECT produto, SUM(valor)
   FROM vendas
   GROUP BY produto

**Query complexa (fc ≈ 0.7):**

.. code-block:: sql

   SELECT v.*, c.nome, p.descricao
   FROM vendas v
   JOIN clientes c ON v.cliente_id = c.id
   JOIN produtos p ON v.produto_id = p.id
   WHERE v.data BETWEEN '2023-01-01' AND '2024-12-31'
   GROUP BY v.id, c.nome, p.descricao
   HAVING SUM(v.valor) > 1000

Fator Histórico (fh)
--------------------

O fator histórico ajusta o roteamento baseado em execuções anteriores.

Cache de Decisões
^^^^^^^^^^^^^^^^^

Decisões são armazenadas em DynamoDB com TTL de 24 horas:

.. code-block:: json

   {
     "fingerprint": "abc123...",
     "cluster": "emr-standard",
     "score": 0.45,
     "factors": {
       "volume": 0.35,
       "complexity": 0.25,
       "historical": 0.40
     },
     "execution_time": 5.2,
     "success": true,
     "timestamp": "2024-01-01T12:00:00Z"
   }

Cálculo
^^^^^^^

.. code-block:: python

   def calculate_historical_factor(history: list) -> float:
       if not history:
           return 0.5  # Valor neutro para queries novas

       # Considerar últimas 10 execuções
       recent = history[-10:]

       success_rate = sum(1 for h in recent if h["success"]) / len(recent)
       avg_time = sum(h["execution_time"] for h in recent) / len(recent)

       # Score baseado em performance
       if success_rate < 0.8:
           # Baixa taxa de sucesso: aumentar score (cluster maior)
           return 0.7
       elif avg_time > 60:
           # Tempo alto: aumentar score
           return 0.6
       elif avg_time < 5:
           # Tempo baixo: diminuir score (cluster menor é suficiente)
           return 0.3
       else:
           return 0.5

Seleção de Cluster
------------------

Após calcular o score, o cluster é selecionado:

.. code-block:: python

   def select_cluster(score: float) -> str:
       if score < ECS_THRESHOLD:  # default: 0.3
           return "ecs"
       elif score <= EMR_STANDARD_THRESHOLD:  # default: 0.5
           return "emr-standard"
       else:
           return "emr-optimized"

Diagrama de Decisão
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Score: 0.0 ─────────────── 0.3 ─────────────── 0.5 ─────────────── 1.0
                   │                    │                    │
                   │                    │                    │
                   ▼                    ▼                    ▼
              ┌─────────┐        ┌─────────────┐      ┌──────────────┐
              │   ECS   │        │ EMR Standard│      │EMR Optimized │
              │ (Leve)  │        │   (Médio)   │      │   (Pesado)   │
              └─────────┘        └─────────────┘      └──────────────┘

Casos Especiais
---------------

Queries de Metadados
^^^^^^^^^^^^^^^^^^^^

Queries de catálogo são sempre roteadas para ECS:

.. code-block:: sql

   SHOW TABLES
   SHOW CATALOGS
   DESCRIBE tabela
   SELECT * FROM information_schema.*

Queries Cached
^^^^^^^^^^^^^^

Se a decisão estiver em cache e válida (< 24h):

1. Retorna decisão imediatamente
2. Não executa EXPLAIN
3. Reduz latência significativamente

Fallback de EXPLAIN
^^^^^^^^^^^^^^^^^^^

Se ``EXPLAIN (TYPE IO)`` falhar:

1. Tenta ``EXPLAIN (TYPE DISTRIBUTED)``
2. Se falhar, usa apenas análise de complexidade
3. Score baseado apenas em fc (fv = 0.5, fh = 0.5)

Fingerprinting
--------------

Queries similares recebem o mesmo fingerprint.

Normalização
^^^^^^^^^^^^

.. code-block:: python

   def normalize_query(query: str) -> str:
       # Remove comentários
       query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
       query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)

       # Normaliza whitespace
       query = ' '.join(query.split())

       # Substitui literais por placeholders
       query = re.sub(r"'[^']*'", "'?'", query)
       query = re.sub(r'\b\d+\b', '?', query)

       # Lowercase
       query = query.lower()

       return query

Exemplo
^^^^^^^

.. code-block:: sql

   -- Query original
   SELECT * FROM vendas WHERE data = '2024-01-15' AND valor > 1000

   -- Query normalizada
   select * from vendas where data = '?' and valor > ?

   -- Fingerprint (SHA256)
   a1b2c3d4e5f6789...

Tuning do Algoritmo
-------------------

Ajuste para Mais Queries em ECS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: ini

   DYRASQL_ECS_THRESHOLD=0.4
   DYRASQL_WEIGHT_VOLUME=0.5

Ajuste para Mais Queries em EMR Optimized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: ini

   DYRASQL_EMR_STANDARD_THRESHOLD=0.4
   DYRASQL_WEIGHT_COMPLEXITY=0.4

Balanceamento Uniforme
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: ini

   DYRASQL_ECS_THRESHOLD=0.33
   DYRASQL_EMR_STANDARD_THRESHOLD=0.66
   DYRASQL_WEIGHT_VOLUME=0.33
   DYRASQL_WEIGHT_COMPLEXITY=0.33
   DYRASQL_WEIGHT_HISTORICAL=0.34

Métricas e Monitoramento
------------------------

Logs de Decisão
^^^^^^^^^^^^^^^

.. code-block:: text

   INFO: Query analysis started
   INFO: Fingerprint: a1b2c3d4...
   INFO: Tables: ["iceberg.default.vendas"]
   INFO: Data size: 2.5GB, Files: 150
   INFO: Volume factor: 0.35
   INFO: Complexity: joins=1, aggs=true, subqueries=0
   INFO: Complexity factor: 0.25
   INFO: Historical factor: 0.40
   INFO: Final score: 0.33
   INFO: Selected cluster: emr-standard

Próximos Passos
---------------

- :doc:`api-reference` - Referência completa da API
- :doc:`configuration` - Ajuste de pesos e thresholds
- :doc:`troubleshooting` - Resolução de problemas
