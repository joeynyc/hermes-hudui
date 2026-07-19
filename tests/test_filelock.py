"""Tests for backend/collectors/filelock.py — cross-platform exclusive locking.

memory.py / profiles.py rely on this for the fcntl→msvcrt swap that makes the
API importable (and its write path safe) on Windows. These cover the
behavior that must hold on every platform: lock acquisition works, the lock
actually excludes a concurrent holder, and re-entering after release works.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from backend.collectors.filelock import exclusive_lock


def test_lock_creates_parent_dirs_and_file(tmp_path: Path) -> None:
    lock_path = tmp_path / "nested" / "dir" / "test.lock"
    with exclusive_lock(lock_path):
        pass
    assert lock_path.exists()


def test_lock_can_be_reacquired_after_release(tmp_path: Path) -> None:
    lock_path = tmp_path / "test.lock"
    with exclusive_lock(lock_path):
        pass
    with exclusive_lock(lock_path):
        pass


def test_lock_excludes_concurrent_holder(tmp_path: Path) -> None:
    lock_path = tmp_path / "test.lock"
    order: list[str] = []
    first_acquired = threading.Event()

    def hold_first() -> None:
        with exclusive_lock(lock_path):
            order.append("first-acquired")
            first_acquired.set()
            time.sleep(0.2)
            order.append("first-released")

    def hold_second() -> None:
        # 第一スレッドが確実にロックを取得してから競合させる
        first_acquired.wait(timeout=2)
        with exclusive_lock(lock_path):
            order.append("second-acquired")

    t1 = threading.Thread(target=hold_first)
    t2 = threading.Thread(target=hold_second)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # 第二スレッドは第一スレッドが解放するまでロックを取得できないはず
    assert order == ["first-acquired", "first-released", "second-acquired"]
