FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QUANT_BACKEND_HOST=0.0.0.0 \
    QUANT_BACKEND_PORT=8001 \
    QUANT_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --prefer-binary -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/config \
    && if [ ! -f /app/config/quant.env ]; then cp /app/config/quant.env.example /app/config/quant.env; fi

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8001"]
