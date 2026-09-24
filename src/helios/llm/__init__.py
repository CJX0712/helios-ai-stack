# 作者：晨星
"""生成层（M11）：多后端可注入实现（ARCH §7 / C5）。"""

from .template import TemplateLLM, build_prompt


__all__ = ["TemplateLLM", "build_prompt"]
