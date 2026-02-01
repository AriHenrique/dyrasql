============
Instalação
============

Este guia detalha o processo de instalação e configuração do DyraSQL.

Pré-requisitos
--------------

Antes de iniciar, certifique-se de ter instalado:

Software Necessário
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 25 50 25
   :header-rows: 1

   * - Software
     - Descrição
     - Versão Mínima
   * - Docker
     - Container runtime
     - 24.0+
   * - Docker Compose
     - Orquestração de containers
     - 2.20+
   * - AWS CLI
     - Interface de linha de comando AWS
     - 2.0+
   * - Git
     - Controle de versão
     - 2.0+
   * - Make (opcional)
     - Automação de build
     - 4.0+

Conta AWS
^^^^^^^^^

O DyraSQL utiliza serviços AWS reais:

- **DynamoDB**: Cache de decisões de roteamento
- **S3**: Armazenamento de dados Iceberg
- **AWS Glue Catalog**: Metadados das tabelas

Certifique-se de ter:

1. Uma conta AWS ativa
2. Credenciais de acesso (Access Key ID e Secret Access Key)
3. Permissões IAM para DynamoDB, S3 e Glue Catalog

Instalação Passo a Passo
------------------------

1. Clonar o Repositório
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git clone https://github.com/arihenrique/dyrasql.git
   cd dyrasql/experimento

2. Configurar Credenciais AWS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure suas credenciais AWS:

.. code-block:: bash

   aws configure

Você será solicitado a fornecer:

- **AWS Access Key ID**: Sua chave de acesso
- **AWS Secret Access Key**: Sua chave secreta
- **Default region name**: ``us-east-1`` (recomendado)
- **Default output format**: ``json``

Isso criará os arquivos ``~/.aws/credentials`` e ``~/.aws/config``.

.. note::

   Você também pode usar um perfil específico:

   .. code-block:: bash

      aws configure --profile meu-perfil

3. Configurar Variáveis de Ambiente
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Copie o arquivo de exemplo e edite com suas configurações:

.. code-block:: bash

   cp .env.example .env

Edite o arquivo ``.env``:

.. code-block:: ini

   # Configuração AWS
   AWS_REGION=us-east-1
   AWS_PROFILE=default

   # DynamoDB (cache de decisões)
   DYNAMODB_TABLE=dyrasql-history

   # S3 (dados Iceberg)
   S3_BUCKET=seu-bucket-iceberg
   S3_PREFIX=iceberg/

   # Pesos do algoritmo de roteamento
   DYRASQL_WEIGHT_VOLUME=0.7
   DYRASQL_WEIGHT_COMPLEXITY=0.2
   DYRASQL_WEIGHT_HISTORICAL=0.1

   # Thresholds de seleção de cluster
   DYRASQL_ECS_THRESHOLD=0.3
   DYRASQL_EMR_STANDARD_THRESHOLD=0.5

   # Logging
   LOG_LEVEL=INFO

.. important::

   Substitua ``seu-bucket-iceberg`` pelo nome real do seu bucket S3.

4. Criar Tabela DynamoDB
^^^^^^^^^^^^^^^^^^^^^^^^

**Opção A: Usando Terraform (Recomendado)**

.. code-block:: bash

   # Inicializar Terraform
   make terraform-init

   # Visualizar plano de execução
   make terraform-plan

   # Criar recursos
   make terraform-apply

**Opção B: Usando AWS CLI**

.. code-block:: bash

   aws dynamodb create-table \
       --table-name dyrasql-history \
       --attribute-definitions AttributeName=fingerprint,AttributeType=S \
       --key-schema AttributeName=fingerprint,KeyType=HASH \
       --billing-mode PAY_PER_REQUEST \
       --region us-east-1

Verifique se a tabela foi criada:

.. code-block:: bash

   aws dynamodb describe-table --table-name dyrasql-history

5. Build das Imagens Docker
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Construa as imagens dos serviços:

.. code-block:: bash

   make build

Ou manualmente:

.. code-block:: bash

   docker compose build

6. Iniciar os Serviços
^^^^^^^^^^^^^^^^^^^^^^

Inicie todos os containers:

.. code-block:: bash

   # Modo foreground (ver logs)
   make up

   # Modo background (detached)
   make up-detached

Ou manualmente:

.. code-block:: bash

   docker compose up -d

7. Verificar Instalação
^^^^^^^^^^^^^^^^^^^^^^^

Verifique se todos os serviços estão rodando:

.. code-block:: bash

   docker compose ps

Todos os serviços devem estar com status ``running``.

Teste os endpoints de saúde:

.. code-block:: bash

   # DyraSQL Core
   curl http://localhost:5001/health

   # Trino ECS
   curl http://localhost:8081/v1/info

   # Trino EMR Standard
   curl http://localhost:8082/v1/info

   # Trino EMR Optimized
   curl http://localhost:8083/v1/info

Estrutura de Diretórios
-----------------------

Após a instalação, você terá a seguinte estrutura:

.. code-block:: text

   experimento/
   ├── docker-compose.yml      # Configuração Docker Compose
   ├── .env                    # Variáveis de ambiente (criado por você)
   ├── .env.example            # Exemplo de variáveis
   ├── Makefile                # Comandos de automação
   ├── docs/                   # Documentação (este diretório)
   ├── dyrasql-core/           # Código fonte do DyraSQL Core
   │   ├── app.py              # API principal
   │   ├── query_analyzer.py   # Analisador de queries
   │   ├── decision_engine.py  # Motor de decisão
   │   ├── history_manager.py  # Gerenciador de cache
   │   └── requirements.txt    # Dependências Python
   ├── trino/                  # Configurações Trino
   │   ├── Dockerfile          # Imagem Trino customizada
   │   └── config/             # Configurações por cluster
   ├── trino-gateway/          # Trino Gateway oficial
   │   └── config.yaml         # Configuração do gateway
   └── trino-gateway-proxy/    # Proxy alternativo
       └── app.py              # Proxy com DyraSQL integrado

Próximos Passos
---------------

- :doc:`quickstart` - Execute sua primeira query
- :doc:`configuration` - Configuração avançada
- :doc:`architecture` - Entenda a arquitetura do sistema
