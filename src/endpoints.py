"""Endpoint helpers for ServerManager.

This module centralizes how we build API endpoints based on environment
configuration found in `.env` / `.env.example`.

Current variables (see .env.example):
- API_URL: Base API URL, e.g. https://admin.obsium.de/api/application

For now, only the root endpoint is implemented, which is the base API URL
as provided via the environment.
"""
from typing import Optional
import os


ENV_BASE_URL_NAME = "API_URL"


def get_api_base_url(url: Optional[str] = None) -> str:
    """Return the base API URL from argument or environment.

    Args:
        url: Optional explicit base URL. If omitted, uses the env var defined
            by `ENV_BASE_URL_NAME`.

    Returns:
        The base URL string.

    Raises:
        ValueError: if the base URL is not provided and missing from env, or
            if it doesn't look like an http(s) URL.
    """
    if url is None:
        url = os.getenv(ENV_BASE_URL_NAME)

    if not url:
        raise ValueError(
            f"Base API URL not found. Set environment variable {ENV_BASE_URL_NAME} "
            "or pass it explicitly to get_api_base_url(url=...)."
        )

    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(
            "Base API URL must start with http:// or https://; got: " + url
        )

    return url


def get_servers_endpoint(base_url: Optional[str] = None) -> str:
    """Return /servers endpoint URL.

    Args:
        prefix: Optional 
    
    """
    base_url = get_api_base_url(base_url)
    return f"{base_url}/servers"


__all__ = ["get_api_base_url", "get_servers_endpoint", "ENV_BASE_URL_NAME"]
