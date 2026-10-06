"""
LootForge Application Launcher.

Initializes configuration, logs startup diagnostics, and launches the native Qt desktop
interface (default) or the web-based interface (via --web or fallback).
"""

import sys
import webbrowser
import threading
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.config import LootForgeConfig
from src.logger import system_logger


def run_qt_app() -> None:
    """Launches native Qt GUI interface."""
    try:
        from src.qt_app import main as qt_main
        system_logger.info("Starting LootForge native Qt desktop interface...", source="Launcher")
        qt_main()
    except Exception as e:
        system_logger.error(f"Failed to start Qt interface: {e}; falling back to web.", source="Launcher")
        run_web_server()


def open_browser_delayed(url: str, delay_seconds: float = 1.0) -> None:
    """Opens default browser after web server starts."""
    time.sleep(delay_seconds)
    system_logger.info(f"Opening LootForge UI in browser: {url}", source="Launcher")
    webbrowser.open(url)


def run_web_server() -> None:
    """Starts cross-platform web server and browser."""
    from src.server import LootForgeServer
    config = LootForgeConfig.load(str(BASE_DIR / "config.json"))
    server = LootForgeServer(base_dir=BASE_DIR, config=config)
    url = f"http://127.0.0.1:{config.port}"

    if "--headless" not in sys.argv:
        t = threading.Thread(target=open_browser_delayed, args=(url, 1.2), daemon=True)
        t.start()

    system_logger.info(f"Server starting on {url}... Press Ctrl+C to stop.", source="Launcher")
    server.start()


def main() -> None:
    """Main launcher entrypoint."""
    system_logger.info("==========================================", source="Launcher")
    system_logger.info("LootForge: Elden Ring Relic & Loot Injector", source="Launcher")
    system_logger.info("Universal Cross-Platform Mod Engine (Qt & Python)", source="Launcher")
    system_logger.info("==========================================", source="Launcher")

    config = LootForgeConfig.load(str(BASE_DIR / "config.json"))
    system_logger.debug_enabled = config.debug_mode
    system_logger.info(f"Platform: {'Windows' if config.is_windows else 'Linux / Steam Deck'}", source="Launcher")

    if "--web" in sys.argv:
        run_web_server()
    else:
        run_qt_app()


if __name__ == "__main__":
    main()
