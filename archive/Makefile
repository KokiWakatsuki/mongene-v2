.PHONY: up down logs status restart

PYTHON   := python3.13
VENV     := .venv
PID_FILE := .uvicorn.pid
LOG_FILE := .uvicorn.log
HOST     := 127.0.0.1
PORT     := 8000

# 初回セットアップ（venv 作成 + 依存インストール）
$(VENV)/bin/uvicorn:
	@echo "==> Setting up virtual environment ..."
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e ".[dev]"
	@echo "==> Setup complete"

# .env が無ければサンプルからコピー
.env:
	@if [ -f .env.example ]; then cp .env.example .env && echo "==> .env created from .env.example (set GEMINI_API_KEY)"; fi

# 起動: http://localhost:8000/ で UI、 /docs で API
up: $(VENV)/bin/uvicorn .env
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "==> Already running: http://$(HOST):$(PORT) (PID $$(cat $(PID_FILE)))"; \
	else \
		( unset SKIP_LLM_IN_TESTS; \
		  $(VENV)/bin/uvicorn apps.api.main:app --host $(HOST) --port $(PORT) \
		  > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE) ); \
		sleep 2; \
		if kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
			echo "==> Started: http://$(HOST):$(PORT)/  (UI)"; \
			echo "             http://$(HOST):$(PORT)/docs  (Swagger)"; \
			echo "             logs: make logs   stop: make down"; \
		else \
			echo "==> Failed to start. tail $(LOG_FILE):"; \
			tail -20 $(LOG_FILE); rm -f $(PID_FILE); exit 1; \
		fi; \
	fi

# 停止
down:
	@if [ -f $(PID_FILE) ]; then \
		PID=$$(cat $(PID_FILE)); \
		kill $$PID 2>/dev/null || true; \
		rm -f $(PID_FILE); \
		echo "==> Stopped (PID $$PID)"; \
	else \
		pkill -f "uvicorn apps.api.main:app" 2>/dev/null && echo "==> Stopped untracked uvicorn process" || echo "==> Not running"; \
	fi

# 再起動
restart: down up

# ログ追跡
logs:
	@tail -f $(LOG_FILE)

# 動作確認
status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Running: PID $$(cat $(PID_FILE)) on http://$(HOST):$(PORT)"; \
	else \
		echo "Not running"; \
	fi
