FROM eclipse-temurin:25-jdk AS builder

RUN apt-get update && apt-get install -y git curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Pin to exact commit for reproducible builds (main @ 2025-01-31).
# Clone with git so .git exists (required by git-commit-id-maven-plugin).
ARG TRINO_GATEWAY_COMMIT=5612a3dedd9435eb5d500820bbf81d1c1f43eb3e
RUN git clone --depth 1 https://github.com/trinodb/trino-gateway.git /build/trino-gateway && \
    cd /build/trino-gateway && \
    git fetch --depth 1 origin "${TRINO_GATEWAY_COMMIT}" && \
    git checkout "${TRINO_GATEWAY_COMMIT}"

WORKDIR /build/trino-gateway

# Build Trino Gateway without modifications - H2 will be added to classpath at runtime
RUN ./mvnw clean package -DskipTests -pl gateway-ha -am && \
    echo "JAR built successfully" && \
    ls -lh gateway-ha/target/*.jar

FROM eclipse-temurin:25-jre

LABEL maintainer="DyraSQL Project"
LABEL description="Trino Gateway oficial - Balanceador de carga e gateway de roteamento para múltiplos clusters Trino"

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/trino-gateway/gateway-ha/target/gateway-ha-*-jar-with-dependencies.jar /app/gateway-ha.jar

# Download PostgreSQL JDBC driver separately and add to classpath
RUN curl -L -o /app/postgresql.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.1/postgresql-42.7.1.jar && \
    echo "=== PostgreSQL driver downloaded ===" && \
    ls -lh /app/postgresql.jar

ENV GATEWAY_CONFIG_PATH=/etc/gateway/config.yaml

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8081/healthcheck || exit 1

# Add PostgreSQL jar to classpath when running the gateway
CMD ["java", "-cp", "/app/gateway-ha.jar:/app/postgresql.jar", "io.trino.gateway.ha.HaGatewayLauncher", "/etc/gateway/config.yaml"]

