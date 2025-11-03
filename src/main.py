#!/usr/bin/env python3
from dotenv import load_dotenv
import os
import sys
from typing import List, Optional, Any
from console import init_readline, read_command
from pydactyl import PterodactylClient


# Load env variables
load_dotenv()
allocations: dict[int, int] = {}


def _get_env(name: str, required: bool = True) -> Optional[str]:
    val = os.getenv(name)
    if required and not val:
        raise ValueError(f"Missing required environment variable: {name}")
    return val


def _init_api_client() -> PterodactylClient | None:
    """Initialize the Pterodactyl client from environment variables.

    Expects API_URL and API_KEY to be present in the environment.
    Returns None if the client can't be constructed.
    """
    try:
        api_url = _get_env("API_URL")
        api_key = _get_env("API_KEY")
        return PterodactylClient(api_url, api_key)
    except Exception as exc:
        print(f"Failed to initialize Pterodactyl client: {exc}", file=sys.stderr)
        return None


def _list_all_servers(api: PterodactylClient) -> List[dict]:
    """Return a list of server dicts from the Application API.

    Tries to support both common response shapes from Pydactyl.
    """
    resp = api.servers.list_servers()
    # Support either attribute access (.data) or dict access
    items = getattr(resp, "data", None)
    if items is None and isinstance(resp, dict):
        items = resp.get("data")
    if items is None:
        # Fallback: assume resp is already a list
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
    suffix = name[len(prefix) :]
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


def _show_servers(api: PterodactylClient, kind: Optional[str]) -> None:
    main_prefix = _get_env("MAIN_PREFIX", required=False) or ""
    interior_prefix = _get_env("INTERIOR_PREFIX", required=False) or ""

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
        suffix = name[len(prefix) :]
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


def _parse_int_env(name: str) -> int:
    val = _get_env(name)
    try:
        return int(val)  # type: ignore[arg-type]
    except Exception:
        raise ValueError(f"Environment variable {name} must be an integer; got: {val}")


def _get_egg_runtime(api: PterodactylClient, nest_id: int, egg_id: int) -> tuple[str, str, dict]:
    """Return (docker_image, startup, environment_defaults) for an egg.

    Falls back to env overrides DOCKER_IMAGE and STARTUP_CMD if present.
    """
    docker_override = _get_env("DOCKER_IMAGE", required=False)
    startup_override = _get_env("STARTUP_CMD", required=False)
    if docker_override and startup_override:
        return docker_override, startup_override, {}

    # Query egg info from API to derive defaults
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

    # Collect default environment vars, if available
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


def _create_server(api: PterodactylClient, kind: str) -> None:
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

    # Limits and feature limits
    limits = {"memory": 7000, "swap": 500, "disk": 5000, "io": 500, "cpu": 100}
    # Feature limits are handled via individual *_limit args below

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
            api.nodes.create_allocations(node_id=1,ip="127.0.0.1",ports=[str(server_port)])
            _reload_allocations(api)
        except Exception as exc:
            print("Failed to create allocation for server:", exc, file=sys.stderr)
            return
    

    # Build environment map (allow overrides via PANEL_ENV_* prefix)
    env_map = dict(env_defaults)
    for k, v in os.environ.items():
        if k.startswith("PANEL_ENV_"):
            env_key = k[len("PANEL_ENV_") :]
            env_map[env_key] = v

    try:
        created = api.servers.create_server(
            name=name,
            user_id=user_id,
            nest_id=nest_id,
            egg_id=egg_id,
            # Use egg's default startup if not overridden
            environment=env_map,
            memory_limit=limits["memory"],
            swap_limit=limits["swap"],
            disk_limit=limits["disk"],
            cpu_limit=limits["cpu"],
            io_limit=limits["io"],
            database_limit=0,
            backup_limit=0,
            allocation_limit=1,
            start_on_completion=True,
            default_allocation=allocations[server_port],
        )

        print(created)

        cid = created.get("attributes", {}).get("id") if isinstance(created, dict) else None
        print(f"Created server '{name}' (id={cid if cid is not None else 'unknown'})")
    except Exception as exc:
        print("Failed to create server:", exc, file=sys.stderr)


def _handle_command(api: Optional[Any], line: str) -> bool:
    """Return False to exit the loop, True to continue."""
    line = line.strip()
    if not line:
        return True
    if line.lower() in {"exit", "quit", "q"}:
        return False

    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "show_servers":
        if api is None:
            print("API is not initialized; cannot run show_servers.", file=sys.stderr)
            return True
        kind = args[0].lower() if args else None
        _show_servers(api, kind)
        return True

    if cmd == "create_server":
        if api is None:
            print("API is not initialized; cannot run create_server.", file=sys.stderr)
            return True
        if not args:
            print("Usage: create_server <main|interior>", file=sys.stderr)
            return True
        kind = args[0].lower()
        _create_server(api, kind)
        return True

    print(f"Unknown command: {cmd}", file=sys.stderr)
    print("Available: show_servers [main|interior], create_server <main|interior>, exit")
    return True

def _reload_allocations(api: PterodactylClient) -> None:
    global allocations
    try:
        raw_allocations = api.nodes.list_node_allocations(node_id=1).collect()
        # find each allocation whose ip is 127.0.0.1 and map the port to the allocation id
        for alloc in raw_allocations:
            if alloc["attributes"]["ip"] == "127.0.0.1":
                allocations[alloc["attributes"]["port"]] = alloc["attributes"]["id"]
    except Exception as exc:
        print("Failed to load allocations:", exc, file=sys.stderr)


if __name__ == "__main__":
    api = _init_api_client()

    if api is None:
        print("API is not initialized; exiting...", file=sys.stderr)
        sys.exit(1)

    _reload_allocations(api)

    # Initialize readline for nicer input handling with history
    init_readline()

    print("Ready!")
    
    while True:
        try:
            line = read_command("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not _handle_command(api, line):
            break
