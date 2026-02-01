# Dockerfile para DyraSQL Core
FROM python:3.11-slim

# Labels
LABEL maintainer="DyraSQL Project"
LABEL description="DyraSQL Core - Sistema de Roteamento Dinâmico"

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia requirements e instala dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . /app/

# Expõe porta da API
EXPOSE 5000

# Variáveis de ambiente padrão
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Comando para iniciar a aplicação
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]

