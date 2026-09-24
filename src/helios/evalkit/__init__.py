# 作者：晨星
"""评测层（M13）：独立索引 + 文档级头条指标 + 三组对照基线（ARCH §7 / T14）。"""

from .evaluator import compute_metrics, evaluate, run_baselines


__all__ = ["compute_metrics", "evaluate", "run_baselines"]
