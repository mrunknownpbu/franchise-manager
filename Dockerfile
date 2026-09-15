FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
RUN useradd -m -u 1000 appuser && mkdir -p /config && chown -R appuser:appuser /app /config
USER appuser
ENV PYTHONUNBUFFERED=1 DATABASE_PATH=/config/franchise-manager.db
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8787/api/health', timeout=5)" || exit 1
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8787"]
