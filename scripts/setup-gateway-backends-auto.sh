#!/bin/bash
# Script para configurar automaticamente os backends no Trino Gateway
# Este script aguarda o Gateway estar pronto e então registra os backends

set -e

GATEWAY_URL="${GATEWAY_URL:-http://trino-gateway:8080}"
MAX_RETRIES=60
RETRY_INTERVAL=2

echo "=========================================="
echo "Configuração Automática de Backends"
echo "=========================================="
echo "Gateway URL: $GATEWAY_URL"
echo ""

# Função para aguardar o Gateway estar pronto
wait_for_gateway() {
    echo "Aguardando Trino Gateway estar pronto..."
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        # Tenta o endpoint /entity que sempre funciona
        if curl -s -f "$GATEWAY_URL/entity?entityType=GATEWAY_BACKEND" > /dev/null 2>&1; then
            echo "SUCCESS: Trino Gateway is ready!"
            return 0
        fi
        
        retries=$((retries + 1))
        if [ $((retries % 5)) -eq 0 ]; then
            echo "  Aguardando... ($retries/$MAX_RETRIES tentativas)"
        fi
        sleep $RETRY_INTERVAL
    done
    
    echo "ERROR: Timeout - Trino Gateway did not become ready after $MAX_RETRIES attempts"
    return 1
}

# Função para verificar se backend já existe
backend_exists() {
    local name=$1
    local backends=$(curl -s "$GATEWAY_URL/gateway/backend/active" 2>/dev/null || echo "[]")
    echo "$backends" | grep -q "\"name\":\"$name\"" 2>/dev/null
}

# Função para adicionar um backend
add_backend() {
    local name=$1
    local proxy_to=$2
    local routing_group=$3
    
    # Verifica se já existe
    if backend_exists "$name"; then
        echo "  INFO: Backend '$name' already exists, skipping..."
        return 0
    fi
    
    echo "  Adicionando backend: $name"
    echo "    URL: $proxy_to"
    echo "    Routing Group: $routing_group"
    
    # Usa o endpoint /entity?entityType=GATEWAY_BACKEND
    response=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL/entity?entityType=GATEWAY_BACKEND" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$name\",
            \"proxyTo\": \"$proxy_to\",
            \"active\": true,
            \"routingGroup\": \"$routing_group\"
        }" 2>/dev/null)
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo "    SUCCESS: Backend '$name' added successfully"
        return 0
    else
        echo "    WARNING: Error adding backend '$name': HTTP $http_code"
        echo "    Resposta: $body"
        return 1
    fi
}

# Aguarda o Gateway estar pronto
if ! wait_for_gateway; then
    exit 1
fi

echo ""
echo "Configurando backends..."
echo ""

# Aguarda um pouco mais para garantir que o Gateway está totalmente inicializado
sleep 3

# Adiciona os três clusters Trino
# NOTA: As URLs usam os nomes dos serviços do Docker Compose (rede interna)
success_count=0
total_count=3

add_backend "ecs" "http://trino-ecs:8080" "default" && success_count=$((success_count + 1))
add_backend "emr-standard" "http://trino-emr-standard:8080" "default" && success_count=$((success_count + 1))
add_backend "emr-optimized" "http://trino-emr-optimized:8080" "default" && success_count=$((success_count + 1))

# Aguarda um pouco para o Gateway processar os backends
if [ $success_count -gt 0 ]; then
    echo ""
    echo "Aguardando Gateway processar backends..."
    sleep 5
    
    # Verifica se os backends estão ativos
    active_backends=$(curl -s "$GATEWAY_URL/gateway/backend/active" 2>/dev/null | grep -o '"name"' | wc -l || echo "0")
    echo "Backends ativos detectados: $active_backends"
fi

echo ""
echo "=========================================="
if [ $success_count -eq $total_count ]; then
    echo "SUCCESS: Configuration completed successfully!"
    echo "   $success_count/$total_count backends configured"
else
    echo "WARNING: Configuration partially completed"
    echo "   $success_count/$total_count backends configured"
fi
echo "=========================================="

# Lista backends configurados
echo ""
echo "Backends ativos:"
backends=$(curl -s "$GATEWAY_URL/gateway/backend/active" 2>/dev/null)
if command -v python3 >/dev/null 2>&1; then
    echo "$backends" | python3 -m json.tool 2>/dev/null || echo "$backends"
else
    echo "$backends"
fi

echo ""

