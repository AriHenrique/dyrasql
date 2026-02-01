# Dockerfile para Trino - Clusters de Execução (ECS/EMR)
FROM trinodb/trino:latest

# Argumentos de build para configurar o cluster
ARG CLUSTER_TYPE=ecs
ARG WORKER_COUNT=2
ARG MEMORY_GB=4

# Labels
LABEL maintainer="DyraSQL Project"
LABEL description="Trino cluster para ${CLUSTER_TYPE}"
LABEL cluster.type="${CLUSTER_TYPE}"

# A imagem do Trino já vem com curl instalado
# O script configure-credentials.sh usa apenas bash e comandos básicos
# Não precisa instalar pacotes adicionais
USER root
# Verifica se curl está disponível (já vem na imagem)
RUN command -v curl &> /dev/null || (echo "curl não encontrado" && exit 1)

# Configura variáveis de ambiente
ENV CLUSTER_TYPE=${CLUSTER_TYPE}
ENV WORKER_COUNT=${WORKER_COUNT}
ENV MEMORY_GB=${MEMORY_GB}

# Cria diretório para configurações customizadas
RUN mkdir -p /etc/trino/catalog

# Copia script de configuração de credenciais
COPY scripts/configure-credentials.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/configure-credentials.sh

# Volta para o usuário trino
USER trino

# Expõe porta padrão do Trino
EXPOSE 8080

# Comando padrão - será sobrescrito pelo docker-compose
CMD ["/usr/lib/trino/bin/run-trino"]

