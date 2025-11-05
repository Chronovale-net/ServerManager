#!/usr/bin/env python3
"""ServerManager - Main entry point."""

from dotenv import load_dotenv
import os
import sys
from typing import Optional, Any

from console import init_readline, read_command
from pydactyl import PterodactylClient
from commands import CommandRegistry
from commands.show_servers import ShowServersCommand
from commands.create_server import CreateServerCommand


# Load env variables
load_dotenv()

# Global allocation tracking
allocations: dict[int, int] = {}


def _get_env(name: str, required: bool = True) -> Optional[str]:
    val = os.getenv(name)
    if required and not val:
        raise ValueError(f"Missing required environment variable: {name}")
    return val


def _init_api_client() -> Optional[PterodactylClient]:
    """Initialize the Pterodactyl client from environment variables."""
    try:
        api_url = _get_env("API_URL")
        api_key = _get_env("API_KEY")
        return PterodactylClient(api_url, api_key)
    except Exception as exc:
        print(f"Failed to initialize Pterodactyl client: {exc}", file=sys.stderr)
        return None


def _reload_allocations(api: PterodactylClient) -> None:
    """Reload allocation mappings from Pterodactyl node."""
    global allocations
    try:
        raw_allocations = api.nodes.list_node_allocations(node_id=1).collect()
        # Map port to allocation ID for localhost allocations
        for alloc in raw_allocations:
            if alloc["attributes"]["ip"] == "127.0.0.1":
                allocations[alloc["attributes"]["port"]] = alloc["attributes"]["id"]
        print(f"Loaded {len(allocations)} localhost allocations")
    except Exception as exc:
        print(f"Failed to load allocations: {exc}", file=sys.stderr)


def _handle_command(registry: CommandRegistry, api: Optional[Any], line: str) -> bool:
    """Handle a command line input.
    
    Returns:
        False to exit the loop, True to continue.
    """
    line = line.strip()
    if not line:
        return True
    
    if line.lower() in {"exit", "quit", "q"}:
        return False

    parts = line.split()
    cmd_name = parts[0].lower()
    args = parts[1:]

    command = registry.get(cmd_name)
    if command:
        if api is None:
            print(f"API is not initialized; cannot run {cmd_name}.", file=sys.stderr)
            return True
        try:
            command.execute(api, args)
        except Exception as exc:
            print(f"Error executing {cmd_name}: {exc}", file=sys.stderr)
        return True

    print(f"Unknown command: {cmd_name}", file=sys.stderr)
    print(registry.get_help())
    return True


def main():
    """Main application entry point."""
    # Initialize API client
    api = _init_api_client()
    if api is None:
        print("API is not initialized; exiting...", file=sys.stderr)
        sys.exit(1)

    # Load allocations
    _reload_allocations(api)

    # Set up command registry
    registry = CommandRegistry()
    registry.register(ShowServersCommand())
    registry.register(CreateServerCommand())

    # Initialize readline for command history
    init_readline()

    print("Ready!")
    print(registry.get_help())

    # Main command loop
    while True:
        try:
            line = read_command("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        if not _handle_command(registry, api, line):
            break


if __name__ == "__main__":
    main()
