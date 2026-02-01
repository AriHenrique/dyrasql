======================
Resolução de Problemas
======================

Guia para diagnóstico e resolução de problemas comuns.

Problemas de Inicialização
--------------------------

Container Não Inicia
^^^^^^^^^^^^^^^^^^^^

**Sintoma:** Container fica em estado "Restarting" ou "Exit".

**Diagnóstico:**

.. code-block:: bash

   docker compose ps
   docker compose logs <container>

**Soluções comuns:**

1. **Porta em uso:**

   .. code-block:: bash

      # Verificar portas
      lsof -i :5001
      lsof -i :8081

      # Matar processo
      kill -9 <PID>

2. **Memória insuficiente:**

   .. code-block:: bash

      # Verificar memória disponível
      docker system df
      docker system prune

3. **Arquivo de configuração inválido:**

   .. code-block:: bash

      # Verificar sintaxe do .env
      cat .env | grep -v '^#' | grep -v '^$'

DyraSQL Core Não Conecta ao DynamoDB
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Sintoma:** Erro "Unable to locate credentials" ou "AccessDeniedException".

**Diagnóstico:**

.. code-block:: bash

   docker compose logs dyrasql-core | grep -i dynamo
   docker compose logs dyrasql-core | grep -i credential

**Soluções:**

1. **Verificar credenciais AWS:**

   .. code-block:: bash

      # Testar credenciais localmente
      aws sts get-caller-identity
      aws dynamodb list-tables

2. **Verificar montagem de credenciais:**

   .. code-block:: bash

      # Dentro do container
      docker compose exec dyrasql-core cat /root/.aws/credentials

3. **Verificar variáveis de ambiente:**

   .. code-block:: bash

      docker compose exec dyrasql-core env | grep AWS

Trino Não Conecta ao S3/Glue
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Sintoma:** Erro "Access Denied" ou "Table not found".

**Diagnóstico:**

.. code-block:: bash

   docker compose logs trino-ecs | grep -i error
   docker compose logs trino-ecs | grep -i s3

**Soluções:**

1. **Verificar permissões IAM:**

   .. code-block:: bash

      # Testar acesso S3
      aws s3 ls s3://seu-bucket/

      # Testar acesso Glue
      aws glue get-databases

2. **Verificar configuração do catálogo:**

   .. code-block:: bash

      cat trino/config/ecs/catalog/iceberg.properties

Problemas de Roteamento
-----------------------

Query Indo para Cluster Errado
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Sintoma:** Query leve sendo roteada para EMR Optimized (ou vice-versa).

**Diagnóstico:**

.. code-block:: bash

   # Verificar decisão de roteamento
   curl -X POST http://localhost:5001/api/v1/route \
     -H "Content-Type: application/json" \
     -d '{"query": "sua query aqui"}'

**Soluções:**

1. **Ajustar thresholds:**

   .. code-block:: ini

      # .env
      DYRASQL_ECS_THRESHOLD=0.35
      DYRASQL_EMR_STANDARD_THRESHOLD=0.65

2. **Ajustar pesos:**

   .. code-block:: ini

      # Dar mais peso ao volume
      DYRASQL_WEIGHT_VOLUME=0.8
      DYRASQL_WEIGHT_COMPLEXITY=0.15
      DYRASQL_WEIGHT_HISTORICAL=0.05

3. **Limpar cache:**

   .. code-block:: bash

      # Remover item do DynamoDB
      aws dynamodb delete-item \
        --table-name dyrasql-history \
        --key '{"fingerprint": {"S": "abc123..."}}'

EXPLAIN Falhando
^^^^^^^^^^^^^^^^

**Sintoma:** Score sempre 0.5 (fallback) ou erro de análise.

**Diagnóstico:**

.. code-block:: bash

   docker compose logs dyrasql-core | grep -i explain

**Soluções:**

1. **Verificar se tabela existe:**

   .. code-block:: sql

      SHOW TABLES FROM iceberg.default;

2. **Testar EXPLAIN manualmente:**

   .. code-block:: bash

      curl -X POST http://localhost:8081/v1/statement \
        -H "Content-Type: text/plain" \
        -H "X-Trino-User: admin" \
        -d "EXPLAIN (TYPE IO) SELECT * FROM iceberg.default.vendas"

3. **Verificar conectividade com cluster ECS:**

   .. code-block:: bash

      curl http://localhost:8081/v1/info

Cache Não Funcionando
^^^^^^^^^^^^^^^^^^^^^

**Sintoma:** ``cached: false`` sempre, mesmo para queries repetidas.

**Diagnóstico:**

.. code-block:: bash

   # Verificar item no DynamoDB
   aws dynamodb get-item \
     --table-name dyrasql-history \
     --key '{"fingerprint": {"S": "abc123..."}}'

**Soluções:**

1. **Verificar TTL:**

   .. code-block:: bash

      # TTL pode ter expirado (24h)
      aws dynamodb describe-table \
        --table-name dyrasql-history \
        --query "Table.TimeToLiveDescription"

2. **Verificar normalização:**

   Queries com espaços ou formatação diferente podem gerar
   fingerprints diferentes.

Problemas de Performance
------------------------

Query Lenta
^^^^^^^^^^^

**Sintoma:** Queries demoram mais que o esperado.

**Diagnóstico:**

.. code-block:: bash

   # Verificar qual cluster está executando
   docker compose logs dyrasql-core | grep "Routing to"

   # Verificar recursos do cluster
   docker stats

**Soluções:**

1. **Verificar se está no cluster correto:**

   Query pesada em ECS será lenta. Ajuste thresholds.

2. **Aumentar recursos do container:**

   .. code-block:: yaml

      # docker-compose.yml
      trino-ecs:
        deploy:
          resources:
            limits:
              memory: 8G

3. **Verificar partition pruning:**

   .. code-block:: sql

      EXPLAIN SELECT * FROM vendas WHERE data_venda = '2024-01-15'

Timeout em Requests
^^^^^^^^^^^^^^^^^^^

**Sintoma:** Erro de timeout ou conexão fechada.

**Diagnóstico:**

.. code-block:: bash

   docker compose logs dyrasql-core | grep -i timeout

**Soluções:**

1. **Aumentar timeout do cliente:**

   .. code-block:: bash

      curl --max-time 300 ...

2. **Habilitar streaming:**

   .. code-block:: ini

      STREAMING_THRESHOLD=32768

3. **Usar modo bypass:**

   .. code-block:: ini

      BYPASS_MODE=true

Problemas de Conectividade
--------------------------

Não Consegue Acessar Endpoints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Sintoma:** "Connection refused" ou "Host unreachable".

**Diagnóstico:**

.. code-block:: bash

   # Verificar se containers estão rodando
   docker compose ps

   # Verificar rede
   docker network ls
   docker network inspect dyrasql-network

**Soluções:**

1. **Reiniciar containers:**

   .. code-block:: bash

      docker compose restart

2. **Recriar rede:**

   .. code-block:: bash

      docker compose down
      docker network prune
      docker compose up -d

3. **Verificar firewall:**

   .. code-block:: bash

      # macOS
      sudo pfctl -d

      # Linux
      sudo ufw status

Gateway Não Roteia
^^^^^^^^^^^^^^^^^^

**Sintoma:** Trino Gateway retorna erro ou não distribui queries.

**Diagnóstico:**

.. code-block:: bash

   docker compose logs trino-gateway | grep -i error
   curl http://localhost:8085/entity/GATEWAY_BACKEND

**Soluções:**

1. **Verificar backends registrados:**

   .. code-block:: bash

      curl -s http://localhost:8084/entity/GATEWAY_BACKEND | jq

2. **Registrar backends manualmente:**

   .. code-block:: bash

      ./scripts/setup-gateway-backends.sh

3. **Verificar health dos clusters:**

   .. code-block:: bash

      for port in 8081 8082 8083; do
        echo "Port $port: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/v1/info)"
      done

Logs e Debugging
----------------

Habilitar Logs Detalhados
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: ini

   # .env
   LOG_LEVEL=DEBUG

Analisar Logs
^^^^^^^^^^^^^

.. code-block:: bash

   # Filtrar por nível
   docker compose logs dyrasql-core 2>&1 | grep ERROR

   # Filtrar por timestamp
   docker compose logs --since 1h dyrasql-core

   # Salvar logs
   docker compose logs > logs.txt 2>&1

Debugging Interativo
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Entrar no container
   docker compose exec dyrasql-core /bin/bash

   # Testar conectividade
   curl http://trino-ecs:8080/v1/info

   # Verificar processos
   ps aux

Comandos Úteis
--------------

.. code-block:: bash

   # Reset completo
   docker compose down -v
   docker system prune -af
   docker compose build --no-cache
   docker compose up -d

   # Verificar saúde de todos os serviços
   for svc in dyrasql-core trino-ecs trino-emr-standard trino-emr-optimized; do
     echo -n "$svc: "
     docker compose exec $svc curl -s localhost:8080/health 2>/dev/null || echo "DOWN"
   done

   # Monitorar recursos
   docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

Suporte
-------

Se o problema persistir:

1. Colete logs completos:

   .. code-block:: bash

      docker compose logs > support-logs.txt 2>&1

2. Verifique versões:

   .. code-block:: bash

      docker --version
      docker compose version
      aws --version

3. Abra issue no GitHub com:

   - Descrição do problema
   - Passos para reproduzir
   - Logs relevantes
   - Configuração (sem credenciais)

Próximos Passos
---------------

- :doc:`configuration` - Ajuste fino de configurações
- :doc:`architecture` - Entenda a arquitetura
- :doc:`api-reference` - Referência da API
