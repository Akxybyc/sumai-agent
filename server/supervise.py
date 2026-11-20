"""服务守护：uvicorn 退出后自动拉起，日志写 data/server.log。

用法（推荐，后台常驻）：
    .venv\\Scripts\\python.exe server\\supervise.py

手动看日志：
    data/server.log
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
DATA = ROOT / "data"
LOG = DATA / "server.log"
PY = ROOT / ".venv" / "Scripts" / "python.exe"

DATA.mkdir(exist_ok=True)


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def main() -> None:
    env = os.environ.copy()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env[k] = ""
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"

    backoff = 3
    while True:
        log("启动 uvicorn …")
        try:
            proc = subprocess.Popen(
                [str(PY), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=str(SERVER),
                env=env,
                stdout=LOG.open("a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
        except Exception as e:  # noqa: BLE001
            log(f"启动失败：{type(e).__name__}: {e}")
            time.sleep(backoff)
            continue

        log(f"进程已启动 pid={proc.pid}")
        code = proc.wait()
        log(f"进程退出 code={code}，{backoff} 秒后重启")
        time.sleep(backoff)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("守护进程手动停止")
        sys.exit(0)
