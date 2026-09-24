# 作者：晨星
""".gitignore 规则守护（ARCH C9 / F-19）。

背景：如果临时文件规则写成非根锚定的 ``_*.py``，它会同时匹配 ``src/helios/__init__.py``
（下划线开头 + .py 结尾），导致干净克隆里 ``from helios import X`` 直接炸。
本脚本用一个自包含的 gitignore 匹配器（不依赖 git 二进制、不依赖仓库是否已 init）断言：

* 源码与配置文件**不会**被忽略；
* 根目录临时文件、缓存目录**会**被忽略。

用法::

    python scripts/check_gitignore.py      # 退出码 0 表示规则正确
"""

from __future__ import annotations

import contextlib
import re
import sys

from dataclasses import dataclass
from pathlib import Path


def _ensure_utf8() -> None:
    """强制 stdout/stderr 用 UTF-8，避免非 UTF-8 终端（如 en-US CI 的 cp1252）打印中文时崩溃。"""
    for _stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8")


# 必须**不被**忽略的路径（干净克隆后必须存在）。
MUST_KEEP: tuple[str, ...] = (
    "src/helios/__init__.py",
    "src/helios/core/__init__.py",
    "src/helios/core/codes.py",
    "src/helios/core/tests/__init__.py",
    "src/helios/core/examples/minimal.py",
    "scripts/scan_emoji.py",
    "scripts/check_gitignore.py",
    "configs/default.yaml",
    "pyproject.toml",
    "pytest.ini",
    "ruff.toml",
    ".env.example",
    ".gitignore",
)

# 必须**被**忽略的路径（临时文件与产物）。
MUST_IGNORE: tuple[str, ...] = (
    "_tmp.py",
    "_scratch.md",
    "_probe.json",
    "src/helios/__pycache__/codes.cpython-313.pyc",
    "data/.pytest-tmp/basetemp/x.py",
    "data/index/vectors.npz",
    "data/cache/cache.db",
    "models/bge-m3/config.json",
)


@dataclass(frozen=True)
class _Pattern:
    """一条 .gitignore 规则的匹配态表示。"""

    negate: bool
    dir_only: bool
    regex: re.Pattern[str]


def _glob_to_regex(body: str) -> str:
    """把 gitignore glob 片段翻译成正则（支持 *、**、?、[...]）。"""
    out: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if char == "*":
            end = index
            while end < length and body[end] == "*":
                end += 1
            star_count = end - index
            prev_is_sep = index == 0 or body[index - 1] == "/"
            next_is_sep = end >= length or body[end] == "/"
            if star_count >= 2 and prev_is_sep and next_is_sep:
                out.append("(?:.*/)?")
                if end < length:
                    end += 1
            else:
                out.append(".*" if star_count >= 2 else "[^/]*")
            index = end
        elif char == "?":
            out.append("[^/]")
            index += 1
        elif char == "[":
            close = body.find("]", index + 1)
            if close == -1:
                out.append(re.escape(char))
                index += 1
            else:
                out.append(body[index : close + 1])
                index = close + 1
        else:
            out.append(re.escape(char))
            index += 1
    return "".join(out)


def _compile(line: str) -> _Pattern | None:
    """把一行 .gitignore 文本编译成匹配器；注释与空行返回 None。"""
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    negate = raw.startswith("!")
    if negate:
        raw = raw[1:]
    dir_only = raw.endswith("/")
    if dir_only:
        raw = raw[:-1]
    anchored = raw.startswith("/")
    if anchored:
        raw = raw[1:]
    if not raw:
        return None
    prefix = "(?:.*/)?" if (not anchored and "/" not in raw) else ""
    return _Pattern(negate=negate, dir_only=dir_only, regex=re.compile(prefix + _glob_to_regex(raw)))


def load_patterns(gitignore: Path) -> list[_Pattern]:
    """读取 .gitignore，按文件顺序返回全部规则（后者覆盖前者）。"""
    patterns: list[_Pattern] = []
    for line in gitignore.read_text(encoding="utf-8").splitlines():
        compiled = _compile(line)
        if compiled is not None:
            patterns.append(compiled)
    return patterns


def is_ignored(rel_path: str, patterns: list[_Pattern]) -> bool:
    """判断相对路径（posix 风格）是否被忽略，语义贴近 git 的「最后命中生效」。"""
    parts = rel_path.split("/")
    prefixes = ["/".join(parts[: count]) for count in range(1, len(parts) + 1)]
    ignored = False
    for _position, prefix in enumerate(prefixes):
        for pattern in patterns:
            if pattern.dir_only:
                # 目录规则：非锚定按「任意路径段」命中，锚定按「目录前缀」命中
                matched = any(pattern.regex.fullmatch(seg) for seg in parts) or any(
                    pattern.regex.fullmatch(prefix) for prefix in prefixes
                )
                if matched:
                    ignored = not pattern.negate
                continue
            if pattern.regex.fullmatch(prefix):
                ignored = not pattern.negate
    return ignored


def main(argv: list[str] | None = None) -> int:
    """入口：执行双向断言，返回进程退出码。"""
    del argv  # 该门禁无参数，保持签名一致便于脚本化调用
    _ensure_utf8()
    root = Path(__file__).resolve().parent.parent
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        print(f"FAIL: 缺少 {gitignore}")
        return 1

    patterns = load_patterns(gitignore)
    failures: list[str] = []
    for rel in MUST_KEEP:
        if is_ignored(rel, patterns):
            failures.append(f"MUST_KEEP 被误忽略: {rel}")
    for rel in MUST_IGNORE:
        if not is_ignored(rel, patterns):
            failures.append(f"MUST_IGNORE 未被忽略: {rel}")

    if failures:
        print(f"FAIL: .gitignore 规则有 {len(failures)} 处问题")
        for item in failures:
            print(f"  - {item}")
        return 1

    print(
        f"PASS: .gitignore 规则正确 —— {len(MUST_KEEP)} 个源码/配置路径未被忽略，"
        f"{len(MUST_IGNORE)} 个临时/产物路径已被忽略"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
