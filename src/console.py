"""Console input helper with readline history.

Enables arrow-key editing and command history for the REPL by configuring
GNU readline on Linux. Persists history to a file across runs.
"""
from __future__ import annotations

import atexit
import os
from typing import Optional


HISTORY_FILE = os.path.expanduser("~/.servermanager_history")
_readline = None  # type: ignore


def _ensure_history_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def init_readline(history_file: Optional[str] = None, history_length: int = 1000) -> None:
    """Initialize readline: load history and register persistence on exit.

    Safe no-op if readline is unavailable.
    """
    global _readline
    try:
        import readline  # type: ignore
    except Exception:
        _readline = None
        return
    _readline = readline

    path = history_file or HISTORY_FILE
    try:
        _ensure_history_dir(path)
        if os.path.exists(path):
            _readline.read_history_file(path)
    except Exception:
        # Non-fatal if history can't be read
        pass

    try:
        _readline.set_history_length(history_length)
    except Exception:
        pass

    def _save_history() -> None:
        try:
            _readline.write_history_file(path)  # type: ignore[attr-defined]
        except Exception:
            pass

    atexit.register(_save_history)


def read_command(prompt: str = "> ") -> str:
    """Read one command line, adding it to history if readline is active."""
    line = input(prompt)
    if _readline is not None:
        try:
            # Avoid duplicate immediate entries
            hlen = _readline.get_current_history_length()
            last = _readline.get_history_item(hlen) if hlen else None
            if line and line != last:
                _readline.add_history(line)
        except Exception:
            pass
    return line


__all__ = ["init_readline", "read_command", "HISTORY_FILE"]
