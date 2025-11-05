"""create_server command - Create a new main or interior server."""

import os
import sys
import time
from typing import List, Optional
from pydactyl import PterodactylClient

from commands.base import BaseCommand


def _get_env(name: str, required: bool = True) -> Optional[str]:
    val = os.getenv(name)
    if required and not val:
        raise ValueError(f"Missing required environment variable: {name}")
    return val


def _parse_int_env(name: str) -> int:
    val = _get_env(name)
    try:
        return int(val)  # type: ignore[arg-type]
    except Exception:
        raise ValueError(f"Environment variable {name} must be an integer; got: {val}")


def _list_all_servers(api: PterodactylClient) -> List[dict]:
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


def _extract_suffix_index(name: str, prefix: str) -> Optional[int]:
    if not prefix or not name.startswith(prefix):
        return None
    suffix = name[len(prefix):]
    if suffix.isdigit():
        n = int(suffix)
        return n if n >= 1 else None
    return None


def _next_index_for_kind(api: PterodactylClient, kind: str) -> int:
    if kind not in ("main", "interior"):
        raise ValueError("kind must be 'main' or 'interior'")
    main_prefix = _get_env("MAIN_PREFIX", required=False) or ""
    interior_prefix = _get_env("INTERIOR_PREFIX", required=False) or ""
    prefix = main_prefix if kind == "main" else interior_prefix
    if not prefix:
        raise ValueError(f"Missing required prefix for {kind.upper()}_PREFIX")

    items = _list_all_servers(api)
    max_idx = 0
    for s in items:
        idx = _extract_suffix_index(_get_server_name(s), prefix)
        if idx is not None and idx > max_idx:
            max_idx = idx
    return max_idx + 1


def _upload_jar_with_retry(base_url: str, server_identifier: str, client_key: str, 
                          jar_path: str, jar_contents: bytes, upload_path: str, 
                          server_name: str, max_attempts: int = 6):
    """
    Background thread that attempts to upload JAR file with retries.
    Polls every 5 seconds until server installation is complete.
    """
    import requests
    
    write_url = f"{base_url}/api/client/servers/{server_identifier}/files/write"
    headers = {
        "Authorization": f"Bearer {client_key}",
        "Content-Type": "application/octet-stream",
    }
    params = {
        "file": upload_path,
    }
    
    jar_filename = os.path.basename(jar_path)
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[Upload attempt {attempt}/{max_attempts}] Uploading {jar_filename}...")
            response = requests.post(write_url, headers=headers, params=params, data=jar_contents)
            
            if response.status_code == 204:
                print(f"✓ Successfully uploaded {jar_filename}")
                
                # Start the server
                print("Starting server...")
                try:
                    from pydactyl import PterodactylClient
                    client_api = PterodactylClient(base_url, client_key)
                    client_api.client.servers.send_power_action(server_identifier, "start")
                    print(f"✓ Server '{server_name}' is starting!")
                except Exception as start_exc:
                    print(f"✗ Failed to start server: {start_exc}", file=sys.stderr)
                return
            else:
                print(f"Upload attempt {attempt} failed with status {response.status_code}")
                
        except Exception as exc:
            print(f"Upload attempt {attempt} failed: {exc}")
        
        if attempt < max_attempts:
            print("Retrying in 5 seconds...")
            time.sleep(5)
    
    print(f"✗ Failed to upload {jar_filename} after {max_attempts} attempts", file=sys.stderr)
    print(f"Server created but JAR not uploaded. Upload manually to: {upload_path}", file=sys.stderr)


def _get_egg_runtime(api: PterodactylClient, nest_id: int, egg_id: int) -> tuple[str, str, dict]:
    """Return (docker_image, startup, environment_defaults) for an egg."""
    docker_override = _get_env("DOCKER_IMAGE", required=False)
    startup_override = _get_env("STARTUP_CMD", required=False)
    if docker_override and startup_override:
        return docker_override, startup_override, {}

    egg = api.nests.get_egg_info(nest_id, egg_id)
    data = egg
    try:
        if hasattr(egg, "json"):
            data = egg.json()  # type: ignore[call-arg]
        elif hasattr(egg, "data"):
            data = egg.data  # type: ignore[attr-defined]
    except Exception:
        data = egg
    attrs = data.get("attributes", data) if isinstance(data, dict) else {}
    docker_image = docker_override or attrs.get("docker_image") or ""
    startup = startup_override or attrs.get("startup") or ""

    env_map: dict = {}
    relationships = attrs.get("relationships") if isinstance(attrs, dict) else None
    if isinstance(relationships, dict):
        vars_data = relationships.get("variables", {}).get("data", [])
        for var in vars_data:
            vattr = var.get("attributes", {})
            name = vattr.get("env_variable")
            default = vattr.get("default_value")
            if name:
                env_map[name] = default

    return docker_image, startup, env_map

class CreateServerCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "create_server"
    
    @property
    def help_text(self) -> str:
        return "Create a new server: create_server <main|interior>"
    
    def execute(self, api: PterodactylClient, args: List[str]) -> None:
        # Import allocations global from main
        from main import allocations
        
        if not args:
            print("Usage: create_server <main|interior>", file=sys.stderr)
            return
        
        kind = args[0].lower()
        if kind not in ("main", "interior"):
            print("Usage: create_server <main|interior>", file=sys.stderr)
            return

        # Determine next index and name
        next_idx = _next_index_for_kind(api, kind)
        prefix = _get_env("MAIN_PREFIX" if kind == "main" else "INTERIOR_PREFIX")
        name = f"{prefix}{next_idx}"

        # Required envs
        user_id = _parse_int_env("USER_ID")
        egg_id = _parse_int_env("MAIN_EGG_ID" if kind == "main" else "INTERIOR_EGG_ID")
        nest_id = _parse_int_env("NEST_ID")

        # Runtime (docker image, startup, env defaults)
        docker_image, startup, env_defaults = _get_egg_runtime(api, nest_id, egg_id)
        if not docker_image or not startup:
            print(
                "Cannot determine docker image/startup for egg. Set DOCKER_IMAGE and STARTUP_CMD envs or check nest/egg IDs.",
                file=sys.stderr,
            )
            return

        # Limits
        limits = {"memory": 7000, "swap": 500, "disk": 5000, "io": 500, "cpu": 100}

        # Find the next port for the allocation
        try:
            port_start = _parse_int_env("MAIN_PORT_START" if kind == "main" else "INTERIOR_PORT_START")
            server_port = port_start + next_idx - 1
        except Exception:
            print("Cannot determine port start for allocation. Set MAIN_PORT_START or INTERIOR_PORT_START.", file=sys.stderr)
            return
        
        if server_port not in allocations:
            try:
                print("Creating allocation for server port " + str(server_port))
                api.nodes.create_allocations(node_id=1, ip="127.0.0.1", ports=[str(server_port)])
                # Reload allocations
                from main import _reload_allocations
                _reload_allocations(api)
            except Exception as exc:
                print("Failed to create allocation for server:", exc, file=sys.stderr)
                return

        # Build environment map
        env_map = dict(env_defaults)
        for k, v in os.environ.items():
            if k.startswith("PANEL_ENV_"):
                env_key = k[len("PANEL_ENV_"):]
                env_map[env_key] = v
        env_map["SERVER_NAME"] = name

        # Create the server
        print(f"Creating server '{name}'...")
        try:
            created_response = api.servers.create_server(
                name=name,
                user_id=user_id,
                nest_id=nest_id,
                egg_id=egg_id,
                environment=env_map,
                memory_limit=limits["memory"],
                swap_limit=limits["swap"],
                disk_limit=limits["disk"],
                cpu_limit=limits["cpu"],
                io_limit=limits["io"],
                database_limit=0,
                backup_limit=0,
                allocation_limit=1,
                start_on_completion=True,  # Don't start yet - upload JAR first
                default_allocation=allocations[server_port],
            )

            # Get JSON representation from Response
            try:
                if hasattr(created_response, 'json') and callable(getattr(created_response, 'json', None)):
                    created = created_response.json()  # type: ignore[union-attr]
                elif isinstance(created_response, dict):
                    created = created_response
                else:
                    created = {"attributes": {}}
            except Exception:
                created = {"attributes": {}}
            
            server_attrs = created.get("attributes", {})  # type: ignore[union-attr]
            server_id_numeric = server_attrs.get("id")
            server_identifier = server_attrs.get("identifier")
            
            if not server_identifier:
                print("Failed to get server identifier from response!", file=sys.stderr)
                print(f"Response: {created}")
                return
            
            print(f"Created server '{name}' (id={server_id_numeric}, identifier={server_identifier})")
                
        except Exception as exc:
            print("Failed to create server:", exc, file=sys.stderr)
