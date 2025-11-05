"""Command system for ServerManager.

Each command is a class that inherits from BaseCommand and implements:
- name: command name (e.g., "show_servers")
- help_text: brief description
- execute(api, args): run the command logic
"""

from .base import BaseCommand, CommandRegistry

__all__ = ["BaseCommand", "CommandRegistry"]
