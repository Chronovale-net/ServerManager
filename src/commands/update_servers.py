"""update_servers command - Refresh environment variables and reinstall all managed servers."""

import os
import sys
from typing import List
from pydactyl import PterodactylClient

from commands.base import BaseCommand


def _build_env_map(api: PterodactylClient, server_info: dict) -> dict:
    """Reconstruct environment map similar to create_server logic.
    Includes all panel variables plus any PANEL_ENV_* overrides and SERVER_NAME.
    """
    # Current environment from API response
    container = server_info.get("container", {})
    current_env = container.get("environment", {})

    # Start with current environment
    env_map = dict(current_env)

    # Apply overrides from environment variables
    for k, v in os.environ.items():
        if k.startswith("PANEL_ENV_"):
            env_key = k[len("PANEL_ENV_"):]
            env_map[env_key] = v

    # Inject SERVER_NAME (derived from server name)
    server_name = server_info.get("name") or server_info.get("uuid") or "unknown"
    env_map["SERVER_NAME"] = server_name
    return env_map


class UpdateServersCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "update_servers"

    @property
    def help_text(self) -> str:
        return "Refresh startup/env for all servers and reinstall them"

    def execute(self, api: PterodactylClient, args: List[str]) -> None:
        print("Updating server list...")
        try:
            servers_resp = api.servers.list_servers(includes=("allocations",))
            servers = getattr(servers_resp, "data", None)
            if servers is None and isinstance(servers_resp, dict):
                servers = servers_resp.get("data")
            if not isinstance(servers, list):
                servers = []
        except Exception as exc:
            print(f"Failed to list servers: {exc}", file=sys.stderr)
            return

        # filter servers to only start with the main or interior prefixes
        main_prefix = os.getenv("MAIN_PREFIX", "")
        interior_prefix = os.getenv("INTERIOR_PREFIX", "")
        if main_prefix or interior_prefix:
            def _matches_prefix(name: str) -> bool:
                if not name.startswith(main_prefix) and not name.startswith(interior_prefix):
                    return False
                # break on - and check if the rest is numeric
                parts = name.split("-", 1)
                if len(parts) < 2:
                    return False
                suffix = parts[1]
                return suffix.isdigit() and int(suffix) >= 1

            filtered_servers = []
            for entry in servers:
                attrs = entry.get("attributes", {})
                name = attrs.get("name", "")
                if _matches_prefix(name):
                    filtered_servers.append(entry)
            servers = filtered_servers

        if not servers:
            print("No servers found.")
            return

        print(f"Found {len(servers)} servers. Beginning updates...")

        # Iterate all servers
        for entry in servers:
            attrs = entry.get("attributes", {})
            server_id = attrs.get("id")
            name = attrs.get("name", f"id:{server_id}")
            egg_id = attrs.get("egg")  # current egg

            if not server_id:
                print("Skipping server with missing id", file=sys.stderr)
                continue

            # Fetch detailed info including variables for environment reconstruction
            try:
                detail = api.servers.get_server_info(server_id=server_id, includes=("egg",))
                if hasattr(detail, "json") and callable(getattr(detail, "json", None)):
                    detail_data = detail.json()  # type: ignore
                else:
                    detail_data = detail if isinstance(detail, dict) else {}
                server_info = detail_data.get("attributes", detail_data)
            except Exception as exc:
                print(f"[{name}] Failed to fetch detailed info: {exc}", file=sys.stderr)
                continue

            # Build environment map similar to creation logic
            env_map = _build_env_map(api, server_info)

            print(f"[{name}] Updating startup/env (egg={egg_id})...")
            try:
                # We only refresh environment; keep docker image/startup as current
                api.servers.update_server_startup(server_id=server_id, egg_id=egg_id, environment=env_map, skip_scripts=False)
                print(f"[{name}] Startup/environment updated. Reinstalling...")
                api.servers.reinstall_server(server_id)
                print(f"[{name}] Reinstall requested.")

                # client_key = os.getenv("PANEL_ENV_CLIENT_KEY", "")
                # client_api = PterodactylClient(api._url, client_key)
                # client_api.client.servers.send_power_action(server_id, "start")
            except Exception as exc:
                print(f"[{name}] Failed to update/reinstall: {exc}", file=sys.stderr)

        print("All servers processed.")
