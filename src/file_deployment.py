"""Incremental asset copies that keep downloaded mods independent of deployed files."""

import os
import shutil
import tempfile
from pathlib import Path


def sync_asset(source: Path, target: Path) -> bool:
    """Atomically copy changed assets; return whether the destination was replaced.

    Exact size/mtime matches avoid recopying unchanged downloads. A newer unrelated
    destination is never assumed equivalent, and existing hard links are detached.
    """
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        return False
    src_stat = source.stat()
    if target.exists():
        dst_stat = target.stat()
        if (src_stat.st_size, src_stat.st_mtime_ns) == (dst_stat.st_size, dst_stat.st_mtime_ns) and not os.path.samefile(source, target):
            return False
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True
