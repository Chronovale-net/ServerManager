"""show_servers command - List managed servers by type."""

import sys
from typing import Any, List, Optional
from commands.base import BaseCommand
from pydactyl import PterodactylClient


def _get_env(name: str, required: bool = True) -> Optional[str]:
    import os
    val = os.getenv(name)
    if required and not val:
        raise ValueError(f"Missing required environment variable: {name}")
    return val


def _list_all_servers(api: Any) -> List[dict]:
    """Return a list of server dicts from the Application API."""
    resp = api.servers.list_servers()
    items = getattr(resp, "data", None)
    if items is None and isinstance(resp, dict):
        items = resp.get("data")
    if items is None:
        items = resp
    if isinstance(items, list):
        return items
    return []


def _get_server_name(item: dict) -> str:
    attrs = item.get("attributes", item)
    return str(attrs.get("name", ""))


class ShowServersCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "show_servers"
    
    @property
    def help_text(self) -> str:
        return "List servers by type: show_servers [main|interior]"
    
    def execute(self, api: PterodactylClient, args: List[str]) -> None:
        main_prefix = _get_env("MAIN_PREFIX", required=False) or ""
        interior_prefix = _get_env("INTERIOR_PREFIX", required=False) or ""

        kind = args[0].lower() if args else None
        valid_kinds = {None, "main", "interior", "both"}
        if kind not in valid_kinds:
            print("Usage: show_servers [main|interior]", file=sys.stderr)
            return

        items = _list_all_servers(api)

        def _matches_prefix_with_index(name: str, prefix: str) -> bool:
            if not prefix:
                return False
            if not name.startswith(prefix):
                return False
            suffix = name[len(prefix):]
            return suffix.isdigit() and int(suffix) >= 1

        def matches(name: str) -> bool:
            if kind in (None, "both"):
                return _matches_prefix_with_index(name, main_prefix) or _matches_prefix_with_index(
                    name, interior_prefix
                )
            if kind == "main":
                return _matches_prefix_with_index(name, main_prefix)
            if kind == "interior":
                return _matches_prefix_with_index(name, interior_prefix)
            return False

        filtered = [s for s in items if matches(_get_server_name(s))]
        print(len(filtered))
