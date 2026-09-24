# 作者：晨星
"""dataclass <-> dict 序列化辅助（T02）：从 types.py 析出以控制单文件行数。

仅依赖标准库；不 import types，避免循环依赖。
types.py 经 ``from .serde import _build, _coerce`` 重新绑定同名符号，调用方无感。
"""

from __future__ import annotations

import dataclasses
import typing

from typing import Any


def _coerce(value: Any, hint: Any) -> Any:
    """按类型注解把 JSON 反序列化结果还原成契约所需的 Python 类型。"""
    origin = typing.get_origin(hint)
    if dataclasses.is_dataclass(hint) and isinstance(value, dict):
        return _build(hint, value)
    if origin is tuple:
        args = typing.get_args(hint)
        inner = args[0] if args else Any
        if dataclasses.is_dataclass(inner):
            return tuple(_build(inner, item) for item in value)
        return tuple(value)
    if origin is frozenset:
        return frozenset(value)
    return value


def _build(cls: type, data: dict[str, Any]) -> Any:
    """由 dict 构造 dataclass，按字段注解做类型归一。"""
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if field.name not in data:
            continue
        kwargs[field.name] = _coerce(data[field.name], hints.get(field.name, Any))
    return cls(**kwargs)
