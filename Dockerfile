FROM python:3.11-slim

# 非特権ユーザーの作成
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install mcp[cli] fastmcp

# ソースコードのコピー
COPY . .

# 権限の設定
RUN chown -R appuser:appuser /app

# ユーザーの切り替え
USER appuser

ENV GEMINI_API_KEY=""
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "server.py"]
