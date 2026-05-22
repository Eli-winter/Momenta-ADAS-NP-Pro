FROM artifactory.momenta.works/docker/python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir \
    -i https://artifactory.momenta.works/artifactory/api/pypi/pypi-remote/simple/ \
    --extra-index-url https://artifactory.momenta.works/artifactory/api/pypi/pypi-momenta/simple \
    -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Feishu OAuth token dir
ENV FEISHU_TOKEN_DIR=/root/.feishu

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
