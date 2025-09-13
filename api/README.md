# System Design API (FastAPI)

This small FastAPI app demonstrates key system design concepts:

- Caching: in-memory TTL LRU-like cache, optional Redis backend
- Encryption in transit: HTTPS-ready (HSTS), with local TLS run instructions
- Queue: Async background worker processing a simple in-memory job queue
- Load balancing: Multi-process workers and a `/whoami` endpoint to observe distribution

## Requirements

- Python 3.10+
- Optional: Redis (if you want to test Redis caching)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Environment variables (prefix `APP_`):

- `APP_CACHE_BACKEND`: `memory` (default) or `redis`
- `APP_REDIS_URL`: e.g. `redis://localhost:6379/0`
- `APP_CACHE_TTL_SECONDS`: default TTL, e.g. `60`
- `APP_QUEUE_WORKER_CONCURRENCY`: worker count (default `2`)
- `APP_ENFORCE_HTTPS`: `true`/`false` (default `true`)
- `APP_HSTS_MAX_AGE`: seconds, default one year

## Run (development)

Plain HTTP (localhost):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run with HTTPS locally (self-signed)

Generate a self-signed cert:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 \
  -subj "/CN=localhost"
```

Run uvicorn with TLS:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

HSTS is set automatically on HTTPS requests.

## Caching demo

- Memory cache (default):
  - `GET /compute/foo`
  - Call again to see `{ cached: true }`
- Redis cache (optional): set `APP_REDIS_URL`, then:
  - `GET /compute/foo?use_redis=true`

## Queue demo

- Enqueue a job:

```bash
curl -X POST http://localhost:8000/enqueue \
  -H 'content-type: application/json' \
  -d '{"a": 1, "b": 2, "note": "hello"}'
```

- Check jobs:

```bash
curl http://localhost:8000/jobs
```

## Load balancing

Start multiple workers:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Hit `/whoami` multiple times to see different PIDs/hostnames.

In production behind a reverse proxy (Nginx, Envoy, ALB), ensure it terminates TLS and forwards `x-forwarded-proto=https` so the app enforces HTTPS redirects correctly.
