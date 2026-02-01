=========
Changelog
=========

Todas as mudanças notáveis do projeto são documentadas aqui.

O formato segue `Keep a Changelog <https://keepachangelog.com/pt-BR/1.0.0/>`_
e o projeto adere ao `Versionamento Semântico <https://semver.org/lang/pt-BR/>`_.

[1.0.0] - 2026-XX-XX
--------------------

Adicionado
^^^^^^^^^^

- Sistema de roteamento inteligente baseado em score
- Análise de queries com EXPLAIN (TYPE IO)
- Cache de decisões em DynamoDB com TTL de 24h
- Suporte a 3 clusters Trino (ECS, EMR Standard, EMR Optimized)
- Algoritmo configurável via variáveis de ambiente
- API REST para consulta de decisões de roteamento
- Modo bypass para conexão direta com clusters
- Streaming de respostas para grandes volumes
- Integração com Apache Iceberg e AWS Glue Catalog
- Documentação completa com Sphinx

Componentes
^^^^^^^^^^^

- **DyraSQL Core**: Motor de roteamento em Python/FastAPI
- **Query Analyzer**: Análise e fingerprinting de queries
- **Decision Engine**: Cálculo de score e seleção de cluster
- **History Manager**: Cache e histórico em DynamoDB
- **Trino Gateway Proxy**: Proxy alternativo com roteamento integrado

Dependências
^^^^^^^^^^^^

- Python 3.10+
- FastAPI 0.104.1
- Trino (latest)
- Docker Compose 2.20+
- AWS SDK (boto3) 1.34.0

[0.1.0] - 2026-XX-XX (Beta)
---------------------------

Adicionado
^^^^^^^^^^

- Protótipo inicial do sistema
- Configuração Docker Compose básica
- Integração com Trino Gateway oficial
- Scripts de setup e configuração

Limitações Conhecidas
^^^^^^^^^^^^^^^^^^^^^

- Trino Gateway usa round-robin (sem integração com score)
- Sem interface de monitoramento
- Cache sem invalidação manual

Roadmap
-------

[1.1.0] - Planejado
^^^^^^^^^^^^^^^^^^^

- Dashboard de monitoramento em tempo real
- Métricas exportadas para Prometheus
- Invalidação manual de cache
- Suporte a mais backends de cache

[1.2.0] - Planejado
^^^^^^^^^^^^^^^^^^^

- Provider Java para Trino Gateway
- Machine learning para otimização de pesos
- Auto-scaling baseado em carga
- Suporte a múltiplos catálogos

[2.0.0] - Futuro
^^^^^^^^^^^^^^^^

- Arquitetura multi-tenant
- Federação de clusters
- Roteamento geo-distribuído
- SaaS/Cloud offering
