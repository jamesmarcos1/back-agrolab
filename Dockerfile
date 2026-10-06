FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-prod.lock ./
RUN pip install --no-cache-dir -r requirements-prod.lock && useradd --create-home agrolab
COPY --chown=agrolab:agrolab app ./app
COPY --chown=agrolab:agrolab migrations ./migrations
COPY --chown=agrolab:agrolab alembic.ini ./
USER agrolab
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
