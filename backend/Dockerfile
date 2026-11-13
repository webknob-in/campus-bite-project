FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached until requirements.txt changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user (uid 10001).
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Secrets are never baked into the image: .dockerignore excludes .env files and
# configuration is supplied at runtime (docker compose env_file / environment).
COPY --chown=app:app . .

# Normalise line endings (a Windows checkout may use CRLF) and make the script executable.
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod 0755 docker-entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
