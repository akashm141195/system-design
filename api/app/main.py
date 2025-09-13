import asyncio
import os
import socket
import time
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    import orjson
except Exception:  # pragma: no cover - optional JSON
    orjson = None

from .settings import settings
from .caching import get_cache, CacheBackend
from .queue import job_queue


def _jsonable(data: Any) -> Any:
    if orjson is None:
        return data
    return orjson.loads(orjson.dumps(data))


app = FastAPI(title=settings.app_name)

# CORS for demo purposes - allow local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def https_enforcement_and_hsts(request: Request, call_next):
    # Enforce HTTPS if behind a proxy that sets x-forwarded-proto
    if settings.enforce_https:
        proto = request.headers.get("x-forwarded-proto")
        if proto and proto != "https":
            url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(url=url, status_code=308)

    response = await call_next(request)

    # Add HSTS header when https is used
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains; preload"
    return response


@app.on_event("startup")
async def startup_event() -> None:
    # start background workers
    await job_queue.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await job_queue.stop()


async def cache_dep() -> CacheBackend:
    return get_cache()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/whoami")
async def whoami() -> Dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "worker_hint": os.environ.get("WORKER_ID", "n/a"),
    }


@app.get("/compute/{key}")
async def compute_and_cache(key: str, ttl: int = settings.cache_ttl_seconds, use_redis: bool = False, cache: CacheBackend = Depends(cache_dep)) -> Dict[str, Any]:
    # Choose backend dynamically for demo
    if use_redis and settings.redis_url:
        from .caching import RedisCache

        cache = RedisCache(settings.redis_url)

    cached = await cache.get(key)
    if cached is not None:
        return {"key": key, "cached": True, "value": _jsonable(cached)}

    # Simulate expensive computation
    await asyncio.sleep(0.2)
    value = {"ts": time.time(), "key": key, "computed": True}
    await cache.set(key, value, ttl_seconds=ttl)
    return {"key": key, "cached": False, "value": value}


@app.post("/enqueue")
async def enqueue_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    job = await job_queue.enqueue(payload)
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs")
async def jobs_snapshot() -> Dict[str, Any]:
    return job_queue.snapshot()


# Guidance endpoint (docs)
@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "message": "System Design API demo: caching, queue, https, load-balancing",
        "endpoints": [
            "/health",
            "/whoami",
            "/compute/{key}?ttl=60&use_redis=false",
            "/enqueue",
            "/jobs",
        ],
    }
