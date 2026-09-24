# 作者：晨星
"""依赖安装脚本（T15）：把钉版清单装进当前虚拟环境，幂等可复现。

优先使用 requirements.lock.txt；sha256 回填完成前回退到 requirements.txt。
"""
from __future__ import annotations

import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_utf8() -> None:
    """强制 stdout/stderr 用 UTF-8，避免非 UTF-8 终端（如 en-US CI 的 cp1252）打印中文时崩溃。"""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _mandatory_requirements() -> str:
    return os.path.join(ROOT, "requirements.lock.txt")


def _optional_requirements() -> str:
    return os.path.join(ROOT, "requirements.lock.optional.txt")


def _install_package_editable() -> int:
    """安装 helios 源码包（src 布局）为 editable，使 `python -m helios.cli` 与 `helios`
    命令可用。--no-deps 复用已锁定的强制依赖；--no-build-isolation 依赖已装入的
    setuptools/wheel，避免构建期再联网。失败为硬错误：缺包则 CLI/demo 全部不可运行。
    """
    # 确保构建后端存在（一次性，幂等）。
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"],
        cwd=ROOT,
        check=False,
    )
    print("[install] 安装 helios 包（editable，本地构建，不拉取依赖）")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps", "--no-build-isolation"],
        cwd=ROOT,
    )
    if result.returncode == 0:
        print("[install] helios 包安装完成 [OK]")
    else:
        print("[install] helios 包安装失败 [WARN]")
    return result.returncode


def main() -> int:
    _ensure_utf8()
    req = _mandatory_requirements()
    print(f"[install] 使用 {os.path.basename(req)}（强制依赖，零下载零编译）")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], cwd=ROOT)
    if result.returncode != 0:
        print("[install] 依赖安装失败 [WARN]")
        return result.returncode
    print("[install] 强制依赖安装完成 [OK]")

    pkg = _install_package_editable()
    if pkg != 0:
        return pkg

    # 可选通道仅当用户显式开启（HELIOS_INSTALL_OPTIONAL=1）时安装，
    # 避免干净克隆的强制复现在无编译工具链的 CI 上失败。
    if os.environ.get("HELIOS_INSTALL_OPTIONAL") == "1" and os.path.isfile(_optional_requirements()):
        opt = _optional_requirements()
        print(f"[install] 安装可选通道 {os.path.basename(opt)}")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", opt], cwd=ROOT)
        if result.returncode == 0:
            print("[install] 可选依赖安装完成 [OK]")
        else:
            print("[install] 可选依赖安装失败（不影响离线 E2E），可稍后手动安装 [WARN]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
