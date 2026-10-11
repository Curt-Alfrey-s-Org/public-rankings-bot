"""
Prometheus metrics endpoint for Rankings Bot API.
Exposes /metrics endpoint for Prometheus scraping.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY
    from prometheus_client import Counter, Histogram, Gauge
    from prometheus_client.multiprocess import MultiProcessCollector
    import os
    
    # Check if we're using multiprocess mode (Gunicorn with multiple workers)
    prometheus_multiproc_dir = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
    
    if prometheus_multiproc_dir:
        # Use multiprocess collector for Gunicorn workers
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
    else:
        # Single process mode (default for uvicorn)
        registry = REGISTRY
    
    # Define metrics
    http_requests_total = Counter(
        'http_requests_total',
        'Total number of HTTP requests',
        ['method', 'endpoint', 'status']
    )
    
    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    
    http_request_size_bytes = Histogram(
        'http_request_size_bytes',
        'HTTP request size in bytes',
        ['method', 'endpoint'],
        buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
    )
    
    http_response_size_bytes = Histogram(
        'http_response_size_bytes',
        'HTTP response size in bytes',
        ['method', 'endpoint'],
        buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
    )
    
    # Ollama metrics
    ollama_requests_total = Counter(
        'ollama_requests_total',
        'Total Ollama API requests',
        ['model', 'endpoint', 'status']
    )

    ollama_request_duration_seconds = Histogram(
        'ollama_request_duration_seconds',
        'Ollama API request duration in seconds',
        ['model', 'endpoint'],
        buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    )

    ollama_tokens_total = Counter(
        'ollama_tokens_total',
        'Total tokens processed by Ollama',
        ['model', 'token_type']
    )

    PROMETHEUS_AVAILABLE = True
    
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed. Install with: pip install prometheus-client")
    http_requests_total = None
    http_request_duration_seconds = None
    http_request_size_bytes = None
    http_response_size_bytes = None
    ollama_requests_total = None
    ollama_request_duration_seconds = None
    ollama_tokens_total = None


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="Prometheus client not available. Install with: pip install prometheus-client",
            status_code=503,
            media_type="text/plain"
        )
    
    try:
        output = generate_latest(registry)
        return Response(content=output, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error("Error generating Prometheus metrics: %s", e)
        return Response(
            content=f"Error generating metrics: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )
