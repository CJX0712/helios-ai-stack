# 作者：晨星
"""安全算术计算器：仅允许四则运算，拒绝任意代码执行（ARCH §7 / T09 / P0-6）。

用 ``ast`` 白名单遍历表达式，规避 ``eval``；除零 / 溢出 / 非法表达式分别映射独立错误码。
"""

from __future__ import annotations

import ast
import math
import operator
import re

from ..core import codes
from ..core.errors import raise_for


_EXPR_RE = re.compile(r"[\d\.\s\+\-\*\/\(\)\%]+")

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_ALLOWED = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)


def _assert_safe(node: ast.AST) -> None:
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED):
            raise raise_for(
                codes.E_TOOLS_UNSAFE_EXPR,
                message="表达式含不允许的语法",
                detail={"node": type(child).__name__},
            )
        if isinstance(child, ast.Constant) and not isinstance(child.value, (int, float)):
            raise raise_for(codes.E_TOOLS_UNSAFE_EXPR, message="仅支持数值常量")


def evaluate(expr: str) -> float:
    """安全求值算术表达式，返回 float（整数结果返回 int）。"""
    if not expr or not expr.strip():
        raise raise_for(codes.E_TOOLS_BAD_EXPR, message="空表达式")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        raise raise_for(codes.E_TOOLS_BAD_EXPR, message="语法错误", detail={"error": str(exc)}) from exc
    _assert_safe(tree)

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.UnaryOp):
            return _UNARY[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise raise_for(codes.E_TOOLS_DIV_ZERO, message="除零")
            result = _BINOPS[type(node.op)](left, right)
            if not math.isfinite(result):
                raise raise_for(codes.E_TOOLS_OVERFLOW, message="结果溢出", detail={"value": repr(result)})
            return result
        raise raise_for(codes.E_TOOLS_UNSAFE_EXPR, message="不支持的节点")

    value = _eval(tree)
    return int(value) if value == int(value) else value


class Calculator:
    """计算器可注入封装。"""

    def __init__(self, config: object | None = None) -> None:
        self.enabled = bool(int(getattr(config, "enable_calculator", None) or 1))

    def can_handle(self, text: str) -> bool:
        """判断文本中是否含有可求值的算术表达式（允许前后缀自然语言）。"""
        if not self.enabled:
            return False
        return self.find_expression(text) is not None

    def find_expression(self, text: str) -> str | None:
        """从文本中提取首个含运算符的算术子串；无则返回 None。"""
        if not text:
            return None
        match = _EXPR_RE.search(text)
        if not match:
            return None
        expr = match.group(0).strip()
        if not any(op in expr for op in "+-*/%") or not any(c.isdigit() for c in expr):
            return None
        return expr

    def run(self, text: str) -> str:
        """求值并格式化为字符串。"""
        expr = self.find_expression(text) or text.strip()
        return str(evaluate(expr))
