.PHONY: help install run run-save annotate funasr clean

PYTHON  ?= python3
VENV    := .venv
CONFIG  := config.json
PORT    := 8686

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖到 .venv
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

run: ## 启动语音输入（按热键录音转文字）
	$(VENV)/bin/python main.py --config $(CONFIG)

run-save: ## 启动语音输入 + 保存数据集（用于标注）
	$(VENV)/bin/python main.py --config $(CONFIG) --save-dataset

annotate: ## 启动 Web 标注工具 (http://127.0.0.1:$(PORT))
	$(VENV)/bin/python tools/annotate_web.py --port $(PORT)

funasr: ## 启动 FunASR 本地服务
	$(VENV)/bin/python -m app.funasr_server

download-models: ## 下载 ASR 模型
	$(VENV)/bin/python -m app.download_models

clean: ## 清理日志和缓存
	rm -rf logs/*.log* app/__pycache__ tools/__pycache__
