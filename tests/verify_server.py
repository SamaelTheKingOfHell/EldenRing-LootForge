"""
End-to-end HTTP server verification script for LootForge adhering to [CS-NO-MOCK].

Spins up the actual LootForgeServer in a daemon thread, issues real HTTP requests
to /api/status, /api/options, and /api/localization, validates responses, and terminates cleanly.
"""

import sys
import json
import time
import threading
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import LootForgeConfig
from src.server import LootForgeServer


def run_e2e_check():
    print("[E2E] Starting LootForge server verification...")
    config = LootForgeConfig.load(str(BASE_DIR / "config.json"))
    config.port = 8484  # Test port

    server = LootForgeServer(base_dir=BASE_DIR, config=config)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(1.0)

    base_url = f"http://127.0.0.1:{config.port}"

    # 1. Test /api/status
    with urllib.request.urlopen(f"{base_url}/api/status") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "config" in data
        assert "backup_count" in data
        print(f"[E2E] /api/status passed (Backup count: {data['backup_count']})")

    # 2. Test /api/options
    with urllib.request.urlopen(f"{base_url}/api/options") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert len(data["boss_remembrances"]) > 0
        assert len(data["elite_enemies"]) > 0
        print(f"[E2E] /api/options passed ({len(data['boss_remembrances'])} boss remembrances, {len(data['elite_enemies'])} enemies)")

    # 3. Test /api/localization
    with urllib.request.urlopen(f"{base_url}/api/localization?lang=en") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "app_title" in data
        print(f"[E2E] /api/localization (en) passed: {data['app_title']}")

    with urllib.request.urlopen(f"{base_url}/api/localization?lang=pt_br") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "app_title" in data
        print(f"[E2E] /api/localization (pt_br) passed: {data['app_title']}")

    # 4. Test UI root
    with urllib.request.urlopen(f"{base_url}/") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "<title>LootForge" in html
        print("[E2E] UI root (index.html) passed")

    print("[E2E] ALL END-TO-END CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_e2e_check()
