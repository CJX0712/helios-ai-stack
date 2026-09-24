# 作者：晨星
"""P0 门禁：源码卫生扫描（ARCH C2 / C3 / F-18 / F-20）。

本脚本同时承担三项检查，任一命中即以退出码 1 结束：

1. emoji / 符号字面量扫描：源码经 GBK 代码页会被 mangled 成乱码，进而让正则源文件
   报 "bad character range"（F-18）。因此源码里绝不出现 emoji 或符号字面量，
   检测逻辑一律用 ``ord()`` 码点范围判断，本文件自身也不例外。
2. 单文件行数 <= 300（C2 / F-20）。
3. TODO / FIXME 零残留（C10）。

扫描范围：``src/``、``scripts/``、``configs/``、``.github/`` 以及仓库根目录的同后缀文件。
``docs/`` 为人工撰写文档，允许使用箭头等排印符号，不在扫描范围内。

用法::

    python scripts/scan_emoji.py            # 退出码 0 表示通过
    python scripts/scan_emoji.py --verbose  # 打印每一个被扫描的文件
"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path


MAX_FILE_LINES = 300

# 一律禁止的码点区间（emoji 与符号主区）。
# 说明：检测类代码只用 ord() 码点范围判断，不写字符字面量，避免本文件自身被 GBK mangled。
ALWAYS_BANNED_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),  # emoji 主区与扩展
    (0x1F1E6, 0x1F1FF),  # 区域指示符（国旗）
    (0x1F900, 0x1F9FF),  # 补充符号与象形文字
    (0x2600, 0x27BF),  # 杂项符号与 dingbats
    (0x2B00, 0x2BFF),  # 杂项符号与箭头补充
    (0xFE00, 0xFE0F),  # 变体选择符
)

# 仅代码/配置文件禁止、Markdown 允许的排印符号（箭头等）。
CODE_ONLY_BANNED_RANGES: tuple[tuple[int, int], ...] = (
    (0x2190, 0x21FF),  # 箭头
    (0x2500, 0x257F),  # 制表符画线
)

CODE_SUFFIXES: frozenset[str] = frozenset({".py", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".json"})
MARKDOWN_SUFFIXES: frozenset[str] = frozenset({".md", ".html"})
SCAN_SUFFIXES: frozenset[str] = CODE_SUFFIXES | MARKDOWN_SUFFIXES

SCAN_DIRS: tuple[str, ...] = ("src", "scripts", "configs", ".github")

EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {".git", "data", "models", "benchmarks", "build", "dist", "__pycache__", ".pytest-tmp", ".ruff_cache", ".venv"}
)

FORBIDDEN_TOKENS: tuple[str, ...] = ("TODO", "FIXME")


def repo_root() -> Path:
    """返回仓库根目录（本文件位于 <root>/scripts/ 下）。"""
    return Path(__file__).resolve().parent.parent


def iter_scan_files(root: Path) -> list[Path]:
    """收集需要扫描的文件，按路径排序保证输出稳定。"""
    found: list[Path] = []
    for dir_name in SCAN_DIRS:
        base = root / dir_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
                continue
            if path.suffix.lower() in SCAN_SUFFIXES:
                found.append(path)
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
            found.append(path)
    return sorted(set(found), key=lambda p: str(p).lower())


def banned_ranges_for(suffix: str) -> tuple[tuple[int, int], ...]:
    """按文件类型返回需要检查的码点区间集合。"""
    if suffix.lower() in CODE_SUFFIXES:
        return ALWAYS_BANNED_RANGES + CODE_ONLY_BANNED_RANGES
    return ALWAYS_BANNED_RANGES


def scan_chars(path: Path) -> list[str]:
    """扫描单个文件中的 emoji / 符号字面量，返回可读的问题描述列表。"""
    problems: list[str] = []
    ranges = banned_ranges_for(path.suffix)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: 非 UTF-8 编码（{exc.reason}）"]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for char in line:
            code_point = ord(char)
            for low, high in ranges:
                if low <= code_point <= high:
                    problems.append(
                        f"{path}:{line_no}: 命中禁止码点 U+{code_point:04X}（区间 U+{low:04X}-U+{high:04X}）"
                    )
                    break
    return problems


def scan_tokens(path: Path) -> list[str]:
    """扫描 TODO / FIXME 残留。"""
    problems: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return problems
    for line_no, line in enumerate(lines, start=1):
        for token in FORBIDDEN_TOKENS:
            if token in line:
                problems.append(f"{path}:{line_no}: 残留 {token}")
    return problems


def scan_line_count(path: Path) -> list[str]:
    """扫描单文件行数上限。"""
    try:
        total = len(path.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        return []
    if total > MAX_FILE_LINES:
        return [f"{path}: 行数 {total} 超过上限 {MAX_FILE_LINES}"]
    return []


def main(argv: list[str] | None = None) -> int:
    """入口：执行全部门禁检查，返回进程退出码。"""
    parser = argparse.ArgumentParser(description="helios 源码卫生门禁（emoji / 行数 / TODO）")
    parser.add_argument("--verbose", action="store_true", help="打印每个被扫描的文件")
    args = parser.parse_args(argv)

    root = repo_root()
    self_path = Path(__file__).resolve()
    files = list(iter_scan_files(root))

    problems: list[str] = []
    for path in files:
        if path.resolve() == self_path:
            continue  # 扫描器自身可能含 FORBIDDEN_TOKENS 字面量定义，跳过自扫描
        if args.verbose:
            print(f"[scan] {path.relative_to(root).as_posix()}")
        problems.extend(scan_chars(path))
        problems.extend(scan_tokens(path))
        problems.extend(scan_line_count(path))

    total_lines = 0
    for path in files:
        try:
            total_lines += len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            continue

    if problems:
        print(f"FAIL: 命中 {len(problems)} 项门禁问题")
        for item in problems:
            print(f"  - {item}")
        return 1

    print(f"PASS: 扫描 {len(files)} 个文件，累计 {total_lines} 行；emoji 0 命中，行数均 <= {MAX_FILE_LINES}，TODO/FIXME 0 残留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
