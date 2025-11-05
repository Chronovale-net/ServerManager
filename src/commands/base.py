"""Base command class and registry."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydactyl import PterodactylClient


class BaseCommand(ABC):
    """Base class for all commands."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (lowercase, e.g., 'show_servers')."""
        pass
    
    @property
    @abstractmethod
    def help_text(self) -> str:
        """Brief help text for the command."""
        pass
    
    @abstractmethod
    def execute(self, api: PterodactylClient, args: List[str]) -> None:
        """Execute the command.
        
        Args:
            api: PterodactylClient instance
            args: List of command arguments (not including command name)
        """
        pass


class CommandRegistry:
    """Registry for all available commands."""
    
    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}
    
    def register(self, command: BaseCommand) -> None:
        """Register a command."""
        self._commands[command.name] = command
    
    def get(self, name: str) -> Optional[BaseCommand]:
        """Get a command by name."""
        return self._commands.get(name.lower())
    
    def list_commands(self) -> List[str]:
        """Get list of all command names."""
        return sorted(self._commands.keys())
    
    def get_help(self) -> str:
        """Get help text for all commands."""
        lines = ["Available commands:"]
        for name in self.list_commands():
            cmd = self._commands[name]
            lines.append(f"  {name} - {cmd.help_text}")
        lines.append("  exit - Exit the program")
        return "\n".join(lines)
