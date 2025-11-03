"""HTTP header helpers for ServerManager.

Provides a small utility to build common request headers used across the
project:

- Content-Type: application/json
- Accept: Application/vnd.pterodactyl.v1+json
- Authorization: Bearer <token from env>

Assumptions:
- The API token is stored in the environment variable
  `API_KEY`. If you prefer a different name, call
  `get_common_headers(token=...)` with the explicit token.
"""
from typing import Dict, Optional
import os


ENV_TOKEN_NAME = "API_KEY"


def get_common_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Return the common headers used for HTTP requests.

    Args:
        token: Optional API token. If not provided, the function will look for
            the token in the environment variable named by `ENV_TOKEN_NAME`.

    Returns:
        A dict containing Content-Type, Accept and Authorization headers.

    Raises:
        ValueError: if no token is provided and the environment variable is
            not set.
    """
    if token is None:
        token = os.getenv(ENV_TOKEN_NAME)

    if not token:
        raise ValueError(
            f"API token not found. Set the environment variable {ENV_TOKEN_NAME} "
            "or pass the token explicitly to get_common_headers(token=...)."
        )

    return {
        "Content-Type": "application/json",
        "Accept": "Application/vnd.pterodactyl.v1+json",
        "Authorization": f"Bearer {token}",
    }


__all__ = ["get_common_headers", "ENV_TOKEN_NAME"]
