=============
Contribuindo
=============

Guia para contribuir com o projeto DyraSQL.

Configuração do Ambiente de Desenvolvimento
-------------------------------------------

Pré-requisitos
^^^^^^^^^^^^^^

- Python 3.10+
- Docker e Docker Compose
- Git
- IDE recomendada: VS Code ou PyCharm

Setup Local
^^^^^^^^^^^

1. **Clone o repositório:**

   .. code-block:: bash

      git clone https://github.com/arihenrique/dyrasql.git
      cd dyrasql/experimento

2. **Crie ambiente virtual:**

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # Linux/macOS
      # ou
      .\venv\Scripts\activate  # Windows

3. **Instale dependências de desenvolvimento:**

   .. code-block:: bash

      pip install -r dyrasql-core/requirements.txt
      pip install pytest black flake8 mypy

4. **Configure pre-commit hooks:**

   .. code-block:: bash

      pip install pre-commit
      pre-commit install

Estrutura do Projeto
--------------------

.. code-block:: text

   dyrasql/
   ├── experimento/
   │   ├── dyrasql-core/         # Código fonte principal
   │   │   ├── app.py            # API FastAPI
   │   │   ├── query_analyzer.py # Analisador de queries
   │   │   ├── decision_engine.py # Motor de decisão
   │   │   ├── history_manager.py # Gerenciador de cache
   │   │   └── tests/            # Testes unitários
   │   ├── trino/                # Configurações Trino
   │   ├── trino-gateway/        # Gateway oficial
   │   ├── trino-gateway-proxy/  # Proxy alternativo
   │   ├── docs/                 # Documentação
   │   └── terraform/            # IaC
   └── artigo_sbbd/              # Artigo acadêmico

Padrões de Código
-----------------

Estilo Python
^^^^^^^^^^^^^

Seguimos PEP 8 com as seguintes configurações:

.. code-block:: ini

   # pyproject.toml
   [tool.black]
   line-length = 100
   target-version = ['py310']

   [tool.flake8]
   max-line-length = 100
   ignore = E203, W503

Formatação automática:

.. code-block:: bash

   black dyrasql-core/
   flake8 dyrasql-core/

Type Hints
^^^^^^^^^^

Usamos type hints em todo o código:

.. code-block:: python

   def calculate_score(
       volume_factor: float,
       complexity_factor: float,
       historical_factor: float,
       weights: dict[str, float] | None = None
   ) -> float:
       """
       Calcula o score de roteamento.

       Args:
           volume_factor: Fator de volume (0.0-1.0)
           complexity_factor: Fator de complexidade (0.0-1.0)
           historical_factor: Fator histórico (0.0-1.0)
           weights: Pesos customizados (opcional)

       Returns:
           Score calculado (0.0-1.0)
       """
       ...

Verificação de tipos:

.. code-block:: bash

   mypy dyrasql-core/

Docstrings
^^^^^^^^^^

Usamos formato Google:

.. code-block:: python

   def analyze_query(query: str) -> QueryAnalysis:
       """Analisa uma query SQL e extrai características.

       Executa normalização, fingerprinting e análise de
       complexidade na query fornecida.

       Args:
           query: Query SQL a ser analisada.

       Returns:
           QueryAnalysis contendo fingerprint, tabelas,
           métricas de volume e complexidade.

       Raises:
           QuerySyntaxError: Se a query for inválida.
           ConnectionError: Se não conseguir conectar ao Trino.

       Example:
           >>> result = analyze_query("SELECT * FROM vendas")
           >>> print(result.fingerprint)
           'abc123...'
       """

Testes
------

Estrutura de Testes
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   dyrasql-core/
   └── tests/
       ├── __init__.py
       ├── conftest.py          # Fixtures compartilhadas
       ├── test_query_analyzer.py
       ├── test_decision_engine.py
       ├── test_history_manager.py
       └── test_integration.py

Executar Testes
^^^^^^^^^^^^^^^

.. code-block:: bash

   # Todos os testes
   pytest dyrasql-core/tests/

   # Com cobertura
   pytest --cov=dyrasql-core dyrasql-core/tests/

   # Testes específicos
   pytest dyrasql-core/tests/test_decision_engine.py -v

Exemplo de Teste
^^^^^^^^^^^^^^^^

.. code-block:: python

   import pytest
   from decision_engine import DecisionEngine

   class TestDecisionEngine:
       @pytest.fixture
       def engine(self):
           return DecisionEngine(
               weights={"volume": 0.5, "complexity": 0.3, "historical": 0.2}
           )

       def test_calculate_score_light_query(self, engine):
           score = engine.calculate_score(
               volume_factor=0.1,
               complexity_factor=0.1,
               historical_factor=0.3
           )
           assert score < 0.3
           assert engine.select_cluster(score) == "ecs"

       def test_calculate_score_heavy_query(self, engine):
           score = engine.calculate_score(
               volume_factor=0.9,
               complexity_factor=0.8,
               historical_factor=0.7
           )
           assert score > 0.7
           assert engine.select_cluster(score) == "emr-optimized"

Workflow de Contribuição
------------------------

1. Criar Issue
^^^^^^^^^^^^^^

Antes de começar, crie uma issue descrevendo:

- Bug encontrado ou feature desejada
- Comportamento esperado vs atual
- Passos para reproduzir (se bug)

2. Criar Branch
^^^^^^^^^^^^^^^

.. code-block:: bash

   # Atualizar main
   git checkout main
   git pull origin main

   # Criar branch
   git checkout -b feature/nome-da-feature
   # ou
   git checkout -b fix/descricao-do-bug

Convenção de nomes:

- ``feature/`` - Nova funcionalidade
- ``fix/`` - Correção de bug
- ``docs/`` - Documentação
- ``refactor/`` - Refatoração
- ``test/`` - Testes

3. Desenvolver
^^^^^^^^^^^^^^

.. code-block:: bash

   # Fazer alterações
   # ...

   # Rodar testes
   pytest

   # Verificar formatação
   black --check .
   flake8

   # Commitar
   git add .
   git commit -m "feat: adiciona suporte a X"

Mensagens de commit seguem `Conventional Commits <https://www.conventionalcommits.org/>`_:

- ``feat:`` - Nova feature
- ``fix:`` - Correção de bug
- ``docs:`` - Documentação
- ``refactor:`` - Refatoração
- ``test:`` - Testes
- ``chore:`` - Manutenção

4. Criar Pull Request
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git push origin feature/nome-da-feature

No GitHub:

1. Crie Pull Request para ``main``
2. Preencha o template
3. Aguarde revisão

Template de PR:

.. code-block:: markdown

   ## Descrição

   Breve descrição das alterações.

   ## Tipo de alteração

   - [ ] Bug fix
   - [ ] Nova feature
   - [ ] Breaking change
   - [ ] Documentação

   ## Como testar

   1. Passo 1
   2. Passo 2

   ## Checklist

   - [ ] Testes passando
   - [ ] Documentação atualizada
   - [ ] Código formatado (black, flake8)

Documentação
------------

Atualizando Docs
^^^^^^^^^^^^^^^^

A documentação usa Sphinx com reStructuredText:

.. code-block:: bash

   cd docs
   pip install -r requirements.txt
   make html

Visualizar localmente:

.. code-block:: bash

   open build/html/index.html

Adicionando Nova Página
^^^^^^^^^^^^^^^^^^^^^^^

1. Crie arquivo ``.rst`` em ``docs/source/``
2. Adicione ao ``toctree`` em ``index.rst``
3. Reconstrua: ``make html``

Releases
--------

Versionamento
^^^^^^^^^^^^^

Seguimos `Semantic Versioning <https://semver.org/>`_:

- MAJOR: Mudanças incompatíveis
- MINOR: Novas funcionalidades compatíveis
- PATCH: Correções de bugs

Processo de Release
^^^^^^^^^^^^^^^^^^^

1. Atualizar versão em ``conf.py``
2. Atualizar CHANGELOG
3. Criar tag: ``git tag v1.2.3``
4. Push: ``git push origin v1.2.3``

Código de Conduta
-----------------

- Seja respeitoso e inclusivo
- Aceite críticas construtivas
- Foque no que é melhor para o projeto
- Mantenha discussões técnicas

Contato
-------

- Issues: GitHub Issues
- Discussões: GitHub Discussions
- Email: maintainers@dyrasql.example.com

Próximos Passos
---------------

- :doc:`architecture` - Entenda a arquitetura
- :doc:`api-reference` - Referência da API
- :doc:`changelog` - Histórico de versões
