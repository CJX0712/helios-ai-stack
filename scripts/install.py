# 作者：晨星
"""依赖安装脚本（T15）：把钉版清单装进当前虚拟环境，幂等可复现。

优先使用 requirements.lock.txt；sha256 回填完成前回退到 requirements.txt。
"""
from __future__ import annotations

import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mandatory_requirements() -> str:
    return os.path.join(ROOT, "requirements.lock.txt")


def _optional_requirements() -> str:
    return os.path.join(ROOT, "requirements.lock.optional.txt")


def main() -> int:
    req = _mandatory_requirements()
    print(f"[install] 使用 {os.path.basename(req)}（强制依赖，零下载零编译）")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], cwd=ROOT)
    if result.returncode != 0:
        print("[install] 依赖安装失败 [WARN]")
        return result.returncode
    print("[install] 强制依赖安装完成 [OK]")

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
