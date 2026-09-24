# 作者：晨星
"""计算器工具测试：安全算术、拒绝代码执行、除零与溢出。"""
from __future__ import annotations

import pytest

from helios.core import codes
from helios.tools.calculator import Calculator, evaluate


def test_safe_arithmetic():
    assert evaluate("12*(3+4)") == 84
    assert evaluate("2+3*4") == 14
    assert evaluate("10/4") == 2.5
    assert evaluate("2**10") == 1024


def test_reject_unsafe_expression():
    with pytest.raises(Exception) as exc:
        evaluate("__import__('os').system('ls')")
    assert "E_TOOLS" in str(exc.value) or "unsafe" in str(exc.value).lower()


def test_division_by_zero():
    with pytest.raises(Exception) as exc:
        evaluate("1/0")
    assert codes.E_TOOLS_DIV_ZERO in str(exc.value)


def test_overflow():
    with pytest.raises(Exception) as exc:
        evaluate("1e308*1e308")
    assert codes.E_TOOLS_OVERFLOW in str(exc.value)


def test_calculator_can_handle():
    calc = Calculator()
    assert calc.can_handle("12*(3+4)")
    assert not calc.can_handle("RAG 是什么")
