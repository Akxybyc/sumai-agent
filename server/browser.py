"""浏览器桥：接管用户本机 Chrome（CDP），保留登录态与已装插件。

两种模式：
1. attach  — Chrome 已用 --remote-debugging-port 启动，直接连；
2. launch  — 由本程序拉起 Chrome（可指定用户配置目录，保留登录/插件）。

注意：Chrome 同一时间只能用一个配置目录，使用"用户配置"前必须先关闭已开的 Chrome。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

CHROME_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
]

EDGE_PATHS = [
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
]

DEFAULT_PORT = 9222
DEFAULT_PROFILE = Path(__file__).resolve().parent.parent / ".chrome-test"


def _registry_app_paths() -> list[Path]:
    """从注册表 App Paths 找 Chrome / Edge（客户装在非标准目录也能找到）。"""
    out: list[Path] = []
    try:
        import winreg
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
        ]
        for hive, sub in keys:
            try:
                with winreg.OpenKey(hive, sub) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val:
                        out.append(Path(str(val).strip('"')))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _playwright_chromium() -> list[Path]:
    """Playwright 自带的 Chromium（安装依赖时已下载，一定存在）。"""
    out: list[Path] = []
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not base.exists():
        return out
    # 版本目录名带编号，取编号最大的先用
    dirs = sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("chromium-")],
                  key=lambda d: d.name, reverse=True)
    for d in dirs:
        for rel in ("chrome-win64/chrome.exe", "chrome-win/chrome.exe"):
            f = d / rel
            if f.exists():
                out.append(f)
    return out


def candidates() -> list[tuple[str, Path]]:
    """按优先级返回可用的浏览器 [(来源说明, 路径)]。"""
    res: list[tuple[str, Path]] = []
    env = os.environ.get("SUMAI_CHROME") or os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        res.append(("环境变量", Path(env)))
    for p in CHROME_PATHS + _registry_app_paths():
        if p.exists():
            res.append(("Edge" if "msedge" in p.name.lower() else "Chrome", p))
    for p in _playwright_chromium():
        if p.exists():
            res.append(("内置Chromium", p))
    for p in EDGE_PATHS:
        if p.exists():
            res.append(("Edge", p))
    # 去重
    seen, uniq = set(), []
    for src, p in res:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((src, p))
    return uniq


def find_chrome() -> Path | None:
    c = candidates()
    return c[0][1] if c else None


def user_profile_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data"


def debug_alive(port: int = DEFAULT_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("webSocketDebuggerUrl"))
    except Exception:
        return False


def chrome_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
        ).stdout.lower()
        return "chrome.exe" in out
    except Exception:
        return False


def _port_busy(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def launch(port: int = DEFAULT_PORT, profile: Path | None = None, start_url: str = "about:blank") -> dict:
    """启动带调试端口的浏览器。不依赖客户装 Chrome：内置 Chromium 兜底。"""
    if debug_alive(port):
        return {"ok": True, "mode": "attach", "message": f"已连接到调试端口 {port}"}

    cands = candidates()
    if not cands:
        return {"ok": False, "message": "没找到任何可用浏览器（Chrome/Edge/内置 Chromium 都不可用）。请先运行 1-安装依赖.bat"}

    # 不同端口用不同配置目录，避免"配置目录被占用"导致启动即退出
    profile = profile or (DEFAULT_PROFILE if port == DEFAULT_PORT
                          else DEFAULT_PROFILE.with_name(f".chrome-test-{port}"))
    profile.mkdir(parents=True, exist_ok=True)
    log_path = Path(__file__).resolve().parent.parent / "data" / "chrome.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    tried = []
    for source, exe in cands[:4]:
        args = [
            str(exe),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=ChromeWhatsNewUI",
            start_url,
        ]
        flags = 0
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            with open(log_path, "ab") as log_file:
                proc = subprocess.Popen(args, stdout=log_file, stderr=log_file,
                                        creationflags=flags, close_fds=True)
        except Exception as e:  # noqa: BLE001
            tried.append(f"{source}: {type(e).__name__}")
            continue

        # 冷启动最多等 20 秒；进程提前退出就不必干等
        exited = False
        for _ in range(40):
            time.sleep(0.5)
            if debug_alive(port):
                return {"ok": True, "mode": "launch", "browser": source,
                        "exe": str(exe), "profile": str(profile),
                        "message": f"已启动浏览器（{source}），调试端口 {port}"}
            if os.name == "nt" and proc.poll() is not None:
                exited = True
                break
        tried.append(f"{source}: " + ("进程启动后立即退出（配置目录被占用或无权限）"
                                      if exited else "20 秒内端口未就绪"))

    hint = ""
    if _port_busy(port):
        hint = f"端口 {port} 已被其它程序占用，请关掉占用它的程序后重试。"
    elif any("Chrome:" in t for t in tried):
        hint = "可能是 Chrome 用了日常配置目录（Chrome 136+ 会禁用调试端口），本工具已改用独立配置，一般不会触发。"
    return {"ok": False, "message": "浏览器启动失败：" + "；".join(tried[:2]) + ("　" + hint if hint else ""),
            "log": str(log_path)}


def status(port: int = DEFAULT_PORT) -> dict:
    cands = candidates()
    return {
        "chrome": str(cands[0][1]) if cands else "",
        "browser_source": cands[0][0] if cands else "",
        "candidates": [{"source": s0, "path": str(p0)} for s0, p0 in cands[:5]],
        "debug_port": port,
        "debug_alive": debug_alive(port),
        "chrome_running": chrome_running(),
        "user_profile": str(user_profile_dir()),
        "agent_profile": str(DEFAULT_PROFILE),
    }
