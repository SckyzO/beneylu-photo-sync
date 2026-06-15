# runtimes/docker/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV ENT_DATA_DIR=/data ENT_STATE_DB=/data/state.db
VOLUME ["/data"]
ENTRYPOINT ["ent-exporter"]
CMD ["sync"]
