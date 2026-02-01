.. DyraSQL documentation master file

======================================
DyraSQL - Dynamic SQL Query Routing
======================================

Bem-vindo à documentação do **DyraSQL**, um sistema de roteamento dinâmico de queries SQL
para clusters Trino heterogêneos.

.. image:: https://img.shields.io/badge/python-3.10+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python Version

.. image:: https://img.shields.io/badge/trino-latest-purple.svg
   :target: https://trino.io/
   :alt: Trino

.. image:: https://img.shields.io/badge/docker-compose-blue.svg
   :target: https://docs.docker.com/compose/
   :alt: Docker Compose

.. figure:: _static/architecture.png
   :alt: Arquitetura DyraSQL
   :align: center
   :width: 90%

   Arquitetura do sistema DyraSQL

Visão Geral
-----------

O DyraSQL é um sistema inteligente de roteamento de queries SQL que analisa as
características de cada query e a direciona para o cluster Trino mais adequado,
otimizando o uso de recursos e melhorando a performance.

**Principais Funcionalidades:**

- Análise automática de queries SQL
- Roteamento baseado em score (volume, complexidade, histórico)
- Cache de decisões em DynamoDB
- Suporte a múltiplos clusters Trino (ECS, EMR Standard, EMR Optimized)
- Integração com Apache Iceberg e AWS Glue Catalog

Índice
------

.. toctree::
   :maxdepth: 2
   :caption: Primeiros Passos

   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 2
   :caption: Arquitetura

   architecture
   components
   routing-algorithm

.. toctree::
   :maxdepth: 2
   :caption: Guias

   usage
   api-reference
   troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Desenvolvimento

   contributing
   changelog

Início Rápido
-------------

.. code-block:: bash

   # Clone o repositório
   git clone https://github.com/seu-usuario/dyrasql.git
   cd dyrasql/experimento

   # Configure as variáveis de ambiente
   cp .env.example .env
   # Edite .env com suas configurações

   # Inicie os serviços
   docker compose up -d

   # Teste a API
   curl http://localhost:5001/health

Links Úteis
-----------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
