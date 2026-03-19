from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status"),
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "In-flight HTTP requests",
    labelnames=("method", "path"),
)

metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _resolve_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return request.url.path


async def metrics_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    method = request.method
    path = _resolve_path(request)
    start = perf_counter()
    status_code = 500

    REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed = perf_counter() - start
        REQUEST_COUNT.labels(method=method, path=path, status=str(status_code)).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
        REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()
