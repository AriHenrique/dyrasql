=============
Configuração
=============

Este guia detalha todas as opções de configuração do DyraSQL.

Variáveis de Ambiente
---------------------

Configuração AWS
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - Variável
     - Obrigatório
     - Descrição
   * - ``AWS_REGION``
     - Sim
     - Região AWS (ex: ``us-east-1``)
   * - ``AWS_PROFILE``
     - Não
     - Perfil AWS a usar (default: ``default``)

Configuração DynamoDB
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - Variável
     - Obrigatório
     - Descrição
   * - ``DYNAMODB_TABLE``
     - Sim
     - Nome da tabela de cache (ex: ``dyrasql-history``)

Configuração S3/Iceberg
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - Variável
     - Obrigatório
     - Descrição
   * - ``S3_BUCKET``
     - Sim
     - Bucket S3 com dados Iceberg
   * - ``S3_PREFIX``
     - Sim
     - Prefixo base para tabelas (ex: ``iceberg/``)

Algoritmo de Roteamento
^^^^^^^^^^^^^^^^^^^^^^^

**Pesos dos Fatores**

O score é calculado como: ``Score = w1×fv + w2×fc + w3×fh``

.. list-table::
   :widths: 35 15 15 35
   :header-rows: 1

   * - Variável
     - Default
     - Range
     - Descrição
   * - ``DYRASQL_WEIGHT_VOLUME``
     - 0.7
     - 0.0-1.0
     - Peso do fator volume (w1)
   * - ``DYRASQL_WEIGHT_COMPLEXITY``
     - 0.2
     - 0.0-1.0
     - Peso do fator complexidade (w2)
   * - ``DYRASQL_WEIGHT_HISTORICAL``
     - 0.1
     - 0.0-1.0
     - Peso do fator histórico (w3)

.. note::

   A soma dos pesos deve ser aproximadamente 1.0 para melhores resultados.

**Thresholds de Cluster**

.. list-table::
   :widths: 40 15 15 30
   :header-rows: 1

   * - Variável
     - Default
     - Range
     - Descrição
   * - ``DYRASQL_ECS_THRESHOLD``
     - 0.3
     - 0.0-1.0
     - Score máximo para ECS
   * - ``DYRASQL_EMR_STANDARD_THRESHOLD``
     - 0.5
     - 0.0-1.0
     - Score máximo para EMR Standard

.. important::

   ``DYRASQL_ECS_THRESHOLD`` < ``DYRASQL_EMR_STANDARD_THRESHOLD``

URLs dos Clusters
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - Variável
     - Default
   * - ``TRINO_ECS_URL``
     - ``http://trino-ecs:8080``
   * - ``TRINO_EMR_STANDARD_URL``
     - ``http://trino-emr-standard:8080``
   * - ``TRINO_EMR_OPTIMIZED_URL``
     - ``http://trino-emr-optimized:8080``
   * - ``DYRASQL_CORE_URL``
     - ``http://dyrasql-core:5000``

Outras Configurações
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Variável
     - Default
     - Descrição
   * - ``LOG_LEVEL``
     - ``INFO``
     - Nível de log (DEBUG, INFO, WARNING, ERROR)
   * - ``BYPASS_MODE``
     - ``true``
     - Se ativo, nextUri aponta diretamente para o cluster
   * - ``STREAMING_THRESHOLD``
     - ``65536``
     - Limite em bytes para usar streaming

Arquivo .env Completo
---------------------

Exemplo completo de configuração:

.. code-block:: ini

   # ============================================
   # Configuração DyraSQL - Arquivo .env
   # ============================================

   # --- AWS ---
   AWS_REGION=us-east-1
   AWS_PROFILE=default

   # --- DynamoDB ---
   DYNAMODB_TABLE=dyrasql-history

   # --- S3/Iceberg ---
   S3_BUCKET=meu-bucket-iceberg
   S3_PREFIX=warehouse/iceberg/

   # --- Algoritmo de Roteamento ---
   # Score = w1×fv + w2×fc + w3×fh
   DYRASQL_WEIGHT_VOLUME=0.7
   DYRASQL_WEIGHT_COMPLEXITY=0.2
   DYRASQL_WEIGHT_HISTORICAL=0.1

   # --- Thresholds ---
   # Score < 0.3 → ECS
   # 0.3 ≤ Score ≤ 0.5 → EMR Standard
   # Score > 0.5 → EMR Optimized
   DYRASQL_ECS_THRESHOLD=0.3
   DYRASQL_EMR_STANDARD_THRESHOLD=0.5

   # --- URLs dos Clusters (Docker interno) ---
   TRINO_ECS_URL=http://trino-ecs:8080
   TRINO_EMR_STANDARD_URL=http://trino-emr-standard:8080
   TRINO_EMR_OPTIMIZED_URL=http://trino-emr-optimized:8080
   DYRASQL_CORE_URL=http://dyrasql-core:5000

   # --- Logging ---
   LOG_LEVEL=INFO

   # --- Modo Bypass ---
   BYPASS_MODE=true
   STREAMING_THRESHOLD=65536

Configuração Trino
------------------

Cada cluster Trino tem sua própria configuração em ``trino/config/<cluster>/``.

Estrutura de Configuração
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   trino/config/
   ├── ecs/
   │   ├── config.properties
   │   ├── node.properties
   │   ├── jvm.config
   │   └── catalog/
   │       ├── iceberg.properties
   │       └── hive.properties
   ├── emr-standard/
   │   └── ...
   └── emr-optimized/
       └── ...

Recursos por Cluster
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 25 20 20 20 15
   :header-rows: 1

   * - Cluster
     - Memória Container
     - Query Memory
     - Workers
     - Porta
   * - ECS
     - 2-4GB
     - 2GB
     - 2
     - 8081
   * - EMR Standard
     - 8-12GB
     - 8GB
     - 4
     - 8082
   * - EMR Optimized
     - 16-24GB
     - 16GB
     - 8
     - 8083

Catálogo Iceberg
^^^^^^^^^^^^^^^^

Configuração do conector Iceberg (``catalog/iceberg.properties``):

.. code-block:: ini

   connector.name=iceberg
   iceberg.catalog.type=glue
   hive.metastore.glue.region=${ENV:AWS_REGION}
   hive.metastore.glue.default-warehouse-dir=s3://${S3_BUCKET}/${S3_PREFIX}
   iceberg.file-format=PARQUET
   fs.native-s3.enabled=true

Ajuste de Performance
---------------------

Cenário 1: Muitas Queries Indo para ECS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Se queries médias estão sendo roteadas para ECS:

.. code-block:: ini

   # Diminuir threshold ECS
   DYRASQL_ECS_THRESHOLD=0.2

   # Ou aumentar peso do volume
   DYRASQL_WEIGHT_VOLUME=0.8
   DYRASQL_WEIGHT_COMPLEXITY=0.15
   DYRASQL_WEIGHT_HISTORICAL=0.05

Cenário 2: Muitas Queries Indo para EMR Optimized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Se queries médias estão sendo roteadas para EMR Optimized:

.. code-block:: ini

   # Aumentar threshold EMR Standard
   DYRASQL_EMR_STANDARD_THRESHOLD=0.7

   # Ou diminuir peso do volume
   DYRASQL_WEIGHT_VOLUME=0.5
   DYRASQL_WEIGHT_COMPLEXITY=0.3
   DYRASQL_WEIGHT_HISTORICAL=0.2

Cenário 3: Balanceamento Uniforme
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Para distribuir queries mais uniformemente:

.. code-block:: ini

   DYRASQL_ECS_THRESHOLD=0.33
   DYRASQL_EMR_STANDARD_THRESHOLD=0.66

Permissões IAM
--------------

O DyraSQL precisa das seguintes permissões:

Política DynamoDB
^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "dynamodb:GetItem",
           "dynamodb:PutItem",
           "dynamodb:UpdateItem",
           "dynamodb:Query",
           "dynamodb:Scan"
         ],
         "Resource": "arn:aws:dynamodb:*:*:table/dyrasql-history"
       }
     ]
   }

Política S3
^^^^^^^^^^^

.. code-block:: json

   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:ListBucket",
           "s3:GetBucketLocation"
         ],
         "Resource": [
           "arn:aws:s3:::seu-bucket-iceberg",
           "arn:aws:s3:::seu-bucket-iceberg/*"
         ]
       }
     ]
   }

Política Glue Catalog
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "glue:GetDatabase",
           "glue:GetDatabases",
           "glue:GetTable",
           "glue:GetTables",
           "glue:GetPartitions"
         ],
         "Resource": "*"
       }
     ]
   }

Próximos Passos
---------------

- :doc:`architecture` - Entenda a arquitetura completa
- :doc:`routing-algorithm` - Detalhes do algoritmo
- :doc:`troubleshooting` - Resolução de problemas
