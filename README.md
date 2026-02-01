# DyraSQL - Dynamic SQL Query Routing

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Trino](https://img.shields.io/badge/trino-latest-purple.svg)](https://trino.io/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-green.svg)](https://arihenrique.github.io/dyrasql/)

Sistema de roteamento dinâmico de queries SQL para clusters Trino heterogêneos.

![Arquitetura DyraSQL](docs/_static/architecture.png)

## Sobre

O DyraSQL analisa queries SQL e as direciona para o cluster Trino mais adequado baseado em:

- **Volume**: Tamanho dos dados
- **Complexidade**: JOINs, agregações, subqueries
- **Histórico**: Performance de execuções anteriores

## Documentação

📚 **Acesse a documentação completa em: [https://arihenrique.github.io/dyrasql/](https://arihenrique.github.io/dyrasql/)**

## Início Rápido

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/dyrasql.git
cd dyrasql

# Configure o ambiente
cp .env.example .env
# Edite .env com suas configurações AWS

# Inicie os serviços
make build && make up

# Teste
curl http://localhost:5001/health
```

## Pré-requisitos

- Docker e Docker Compose
- AWS CLI configurado (`aws configure`)
- Bucket S3 com tabelas Iceberg

## Licença

MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.
