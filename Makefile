.PHONY: help build up up-detached down logs logs-file logs-stop clean clean-logs init plan apply destroy output docs docs-serve docs-clean

# Log directory
LOGS_DIR := logs
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)
LOG_FILE := $(LOGS_DIR)/docker-compose_$(TIMESTAMP).log

help:
	@echo "Available commands:"
	@echo ""
	@echo "Docker:"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start services (logs saved to logs/)"
	@echo "  make up-detached    - Start services in background (logs saved)"
	@echo "  make down           - Stop services"
	@echo "  make logs           - Show logs in real time"
	@echo "  make logs-file      - Show latest log file"
	@echo "  make logs-stop      - Stop background log capture"
	@echo "  make clean          - Remove containers and volumes"
	@echo "  make clean-logs     - Remove old log files"
	@echo ""
	@echo "Terraform:"
	@echo "  make init    - Initialize Terraform"
	@echo "  make plan    - Show execution plan"
	@echo "  make apply   - Create DynamoDB table"
	@echo "  make destroy - Remove DynamoDB table"
	@echo "  make output  - Show Terraform outputs"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs           - Build HTML documentation"
	@echo "  make docs-serve     - Serve documentation locally"
	@echo "  make docs-clean     - Clean documentation build"

build:
	docker compose build

build-no-cache:
	docker compose build --no-cache

up:
	@mkdir -p $(LOGS_DIR)
	@echo "Starting services and saving logs to $(LOG_FILE)..."
	@echo "Press Ctrl+C to stop (logs will continue to be saved)"
	@docker compose up 2>&1 | tee $(LOG_FILE)

up-detached:
	@mkdir -p $(LOGS_DIR)
	@echo "Starting services in background..."
	@echo "Logs will be saved to $(LOG_FILE)"
	@docker compose up -d
	@sleep 2
	@echo "Capturing initial logs..."
	@docker compose logs --tail=100 > $(LOG_FILE) 2>&1
	@(docker compose logs -f >> $(LOG_FILE) 2>&1 &) && echo $$! > $(LOGS_DIR)/.log_pid
	@echo "Services started. Logs being saved to $(LOG_FILE)"
	@echo "To view logs in real time: make logs"
	@echo "To view log file: make logs-file"
	@echo "To stop log capture: pkill -f 'docker compose logs'"

down:
	@$(MAKE) logs-stop 2>/dev/null || true
	docker compose down

logs:
	docker compose logs -f

logs-file:
	@if [ -d $(LOGS_DIR) ] && [ -n "$$(ls -A $(LOGS_DIR)/docker-compose_*.log 2>/dev/null)" ]; then \
		LATEST_LOG=$$(ls -t $(LOGS_DIR)/docker-compose_*.log 2>/dev/null | head -1); \
		if [ -n "$$LATEST_LOG" ]; then \
			echo "Latest log: $$LATEST_LOG"; \
			echo "Size: $$(du -h $$LATEST_LOG | cut -f1)"; \
			echo "---"; \
			tail -100 $$LATEST_LOG; \
		else \
			echo "No log file found in $(LOGS_DIR)/"; \
		fi \
	else \
		echo "Log directory $(LOGS_DIR)/ does not exist or is empty"; \
	fi

logs-stop:
	@if [ -f $(LOGS_DIR)/.log_pid ]; then \
		PID=$$(cat $(LOGS_DIR)/.log_pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			kill $$PID 2>/dev/null; \
			echo "Log capture stopped (PID: $$PID)"; \
		else \
			echo "Log capture process is not running"; \
		fi; \
		rm -f $(LOGS_DIR)/.log_pid; \
	else \
		echo "No log capture process found"; \
		pkill -f 'docker compose logs' 2>/dev/null && echo "Log capture processes terminated" || echo "No process found"; \
	fi

clean:
	docker compose down -v
	docker system prune -f

clean-logs:
	@if [ -d $(LOGS_DIR) ]; then \
		COUNT=$$(ls -1 $(LOGS_DIR)/docker-compose_*.log 2>/dev/null | wc -l); \
		if [ $$COUNT -gt 0 ]; then \
			echo "Removing $$COUNT log file(s)..."; \
			rm -f $(LOGS_DIR)/docker-compose_*.log; \
			rm -f $(LOGS_DIR)/.log_pid; \
			echo "Logs removed"; \
		else \
			echo "No log files to remove"; \
		fi \
	else \
		echo "Log directory does not exist"; \
	fi

# Terraform commands
init:
	cd terraform && terraform init

plan: init
	cd terraform && terraform plan

apply: plan
	cd terraform && terraform apply

destroy: init
	cd terraform && terraform destroy

output: init
	cd terraform && terraform output

# Legacy command (kept for compatibility)
dynamodb: apply
	@echo "DynamoDB table created via Terraform"

clear:
	rm -Rf logs && rm -Rf explains

delet:
	python ./scripts/delet.py

start: clear delet
	docker compose down && docker compose up

start-v: clear delet
	docker compose down -v && docker compose up --build

# Documentation commands
docs:
	@echo "Building documentation..."
	@cd docs && pip install -q -r requirements.txt && make html
	@echo "Documentation built: docs/_build/html/index.html"

docs-serve: docs
	@echo "Serving documentation at http://localhost:8000"
	@cd docs/_build/html && python -m http.server 8000

docs-clean:
	@echo "Cleaning documentation build..."
	@cd docs && make clean
	@echo "Documentation cleaned"
