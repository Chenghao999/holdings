"""数据获取层：外部行情 API 封装，含重试与降级。不依赖 storage。"""

__all__ = ["a_stock", "fetcher", "gold", "us_stock"]
