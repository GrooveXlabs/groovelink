# GrooveLink

[![Tests](https://github.com/GrooveXlabs/groovelink/actions/workflows/test.yml/badge.svg)](https://github.com/GrooveXlabs/groovelink/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A resilient API client for Python with built-in **circuit breaker**, **retry**, **rate limiting**, and **health checks**.

## Features

- **Dual API**: Async (`GrooveLinkClient` via `httpx`) and Sync (`GrooveLinkSync` via `requests`)
- **Circuit Breaker**: Prevent cascading failures with automatic recovery
- **Retry Strategies**: Exponential backoff with jitter, linear, or fixed delays
- **Rate Limiting**: Token bucket algorithm with per-domain and global limits
- **Health Checks**: Automatic latency monitoring and degradation detection
- **Security First**: SSRF-protected URL validation, header redaction, strict timeouts
- **Observability**: Event hooks for every resilience event
- **CLI**: `groovelink health <url>` with rich output

## Quickstart

```bash
pip install -e ".[dev]"
```

### Async

```python
from groovelink import GrooveLinkClient

async with GrooveLinkClient(base_url="https://api.example.com") as client:
    response = await client.get("/users")
    print(response.json())
```

### Sync

```python
from groovelink import GrooveLinkSync

with GrooveLinkSync(base_url="https://api.example.com") as client:
    response = client.get("/users")
    print(response.json())
```

### CLI Health Check

```bash
groovelink health https://api.example.com --samples 5
```

## Architecture

```
groovelink/
├── client.py      # Main resilient client
├── circuit.py     # Circuit breaker
├── retry.py       # Retry strategies
├── ratelimit.py   # Token bucket rate limiter
├── health.py      # Health monitor
├── cache.py       # Response cache for fallbacks
├── validators.py  # URL/input validation
├── exceptions.py  # Custom exceptions
├── cli.py         # Click CLI
└── utils.py       # Shared helpers
```

## Configuration

| Parameter            | Default | Description                          |
|----------------------|---------|--------------------------------------|
| `timeout`            | 30.0    | Request timeout in seconds           |
| `retries`            | 3       | Max retry attempts                   |
| `retry_strategy`     | exp     | `exponential`, `linear`, `fixed`     |
| `base_delay`         | 1.0     | Initial retry delay                  |
| `max_delay`          | 60.0    | Max retry delay cap                  |
| `circuit_threshold`  | 5       | Failures before opening circuit      |
| `circuit_recovery`   | 30.0    | Seconds before half-open test        |
| `rate_limit`         | None    | Global requests per minute           |
| `rate_limit_per_domain` | None | Per-domain requests per minute       |
| `cache_ttl`          | 300.0   | Fallback cache TTL in seconds        |

## Testing

```bash
pytest
```

## Ecosystem

| Project | Description |
|---------|-------------|
| [grooveguard](https://github.com/GrooveXlabs/grooveguard) | MCP Server Security Scanner |
| [groovehub](https://github.com/GrooveXlabs/groovehub) | MCP Server Registry |
| [groovestrike](https://github.com/GrooveXlabs/groovestrike) | Autonomous pentest framework |
| [groovefetch](https://github.com/GrooveXlabs/groovefetch) | AI-native web scraper |
| [purpleforge](https://github.com/GrooveXlabs/purpleforge) | Purple team defense rules |
| [threathound](https://github.com/GrooveXlabs/threathound) | Blue Team SOC automation |
| [redtrack](https://github.com/GrooveXlabs/redtrack) | Red Team recon & attack paths |

## License

MIT — GrooveXlabs
