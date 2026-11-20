"""工具层接口定义。

真实实现放在 a1688.py / aliexpress.py / llm.py，每个工具提供两种驱动：
- api 驱动（首选）
- rpa 驱动（Playwright 兜底）
智能体只依赖这里的统一接口，不关心底层走哪条路。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolResult:
    ok: bool
    driver: str  # api | rpa
    data: object = None
    error: str = ""


class ProductSourceTool:
    """1688 选品工具：搜索、详情。"""

    name = "1688.product"

    async def search(self, keyword: str, limit: int = 12) -> ToolResult:
        raise NotImplementedError

    async def detail(self, item_id: str) -> ToolResult:
        raise NotImplementedError


class ListingTool:
    """速卖通刊登工具：类目 schema、图片上传、发布、编辑。"""

    name = "aliexpress.listing"

    async def category_schema(self, category_id: str) -> ToolResult:
        raise NotImplementedError

    async def upload_image(self, path: str) -> ToolResult:
        raise NotImplementedError

    async def publish(self, draft: dict) -> ToolResult:
        raise NotImplementedError

    async def update_goods_code(self, product_id: str, code: str) -> ToolResult:
        raise NotImplementedError
