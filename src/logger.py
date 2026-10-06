"""
Thread-safe event logger supporting real-time streaming and the floating developer console.

Adheres to [CS-DEBUG] by maintaining an in-memory log buffer, real-time message
dispatch, and structured log records for frontend inspection.
"""

import time
import threading
from typing import List, Dict, Any, Optional


class EventLogger:
    """
    Central logging service for LootForge.
    
    Why:
        Powers the floating developer console button and real-time streaming UI,
        enabling non-intrusive diagnostics across Windows and Steam Deck systems.
    
    Example:
    ```python
    logger = EventLogger(max_history=500, debug=True)
    logger.info("Mod scanner initialized", source="Scanner")
    logs = logger.get_recent_logs(limit=50)
    ```
    """
    
    def __init__(self, max_history: int = 1000, debug: bool = True):
        self._max_history = max_history
        self._debug = debug
        self._lock = threading.Lock()
        self._logs: List[Dict[str, Any]] = []

    @property
    def debug_enabled(self) -> bool:
        """Returns whether debug-level verbosity is enabled."""
        return self._debug

    @debug_enabled.setter
    def debug_enabled(self, value: bool) -> None:
        """Toggles debug verbosity."""
        self._debug = bool(value)

    def log(self, level: str, message: str, source: str = "System", details: Optional[Dict[str, Any]] = None) -> None:
        """
        Appends an event to the circular buffer and echoes to standard output.
        """
        if level == "DEBUG" and not self._debug:
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "timestamp": timestamp,
            "level": level.upper(),
            "source": source,
            "message": message,
            "details": details or {}
        }

        with self._lock:
            self._logs.append(record)
            if len(self._logs) > self._max_history:
                self._logs.pop(0)

        # Standard console echo with clear formatting
        prefix = f"[{timestamp}] [{record['level']}] [{source}]"
        print(f"{prefix} {message}")

    def debug(self, message: str, source: str = "System", details: Optional[Dict[str, Any]] = None) -> None:
        """Log a diagnostic debug trace."""
        self.log("DEBUG", message, source, details)

    def info(self, message: str, source: str = "System", details: Optional[Dict[str, Any]] = None) -> None:
        """Log an informational milestone."""
        self.log("INFO", message, source, details)

    def warning(self, message: str, source: str = "System", details: Optional[Dict[str, Any]] = None) -> None:
        """Log a recoverable condition or warning."""
        self.log("WARN", message, source, details)

    def error(self, message: str, source: str = "System", details: Optional[Dict[str, Any]] = None) -> None:
        """Log an unrecoverable failure or error."""
        self.log("ERROR", message, source, details)

    def get_recent_logs(self, limit: int = 100, min_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent log entries, optionally filtered by level.
        """
        with self._lock:
            entries = list(self._logs)

        if min_level:
            level_order = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
            target_rank = level_order.get(min_level.upper(), 0)
            entries = [e for e in entries if level_order.get(e["level"], 0) >= target_rank]

        return entries[-limit:]

    def clear(self) -> None:
        """Clears all buffered log records."""
        with self._lock:
            self._logs.clear()


# Global singleton instance for shared engine diagnostics
system_logger = EventLogger()
