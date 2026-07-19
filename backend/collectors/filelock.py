"""クロスプラットフォームなファイル排他ロック。

Unix系(macOS/Linux)では fcntl.flock、Windowsでは msvcrt.locking を使う。
memory.py / profiles.py のファイル編集エンドポイントから使われる。
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def exclusive_lock(path: Path) -> Iterator[IO[bytes]]:
        """path をロックファイルとして開き、排他ロックを取得する。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        with open(path, "r+b") as fh:
            # msvcrt.locking はロック対象のバイト範囲が必要なため、
            # 空ファイルの場合は1バイト書き込んでからロックする。
            if os.fstat(fh.fileno()).st_size == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield fh
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    @contextmanager
    def exclusive_lock(path: Path) -> Iterator[IO[bytes]]:
        """path をロックファイルとして開き、排他ロックを取得する。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        with open(path, "rb") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield fh
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
