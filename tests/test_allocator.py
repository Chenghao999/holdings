"""portfolio.allocator 资产配置占比的单元测试。"""

import pytest

from holdings.portfolio.allocator import allocation_by_asset_type


def test_allocation_single_type():
    result = allocation_by_asset_type({"600519": 1000.0}, {"600519": "stock"})

    assert result == {"stock": 1.0}


def test_allocation_splits_proportionally():
    result = allocation_by_asset_type(
        {"600519": 750.0, "518880": 250.0},
        {"600519": "stock", "518880": "gold"},
    )

    assert result["stock"] == pytest.approx(0.75)
    assert result["gold"] == pytest.approx(0.25)


def test_allocation_groups_multiple_symbols_of_same_type():
    result = allocation_by_asset_type(
        {"600519": 300.0, "000001": 100.0, "518880": 100.0},
        {"600519": "stock", "000001": "stock", "518880": "gold"},
    )

    assert result["stock"] == pytest.approx(0.8)
    assert result["gold"] == pytest.approx(0.2)


def test_allocation_defaults_unknown_symbol_to_stock():
    result = allocation_by_asset_type({"???": 100.0}, {})

    assert result == {"stock": 1.0}


def test_allocation_zero_total_returns_zeros():
    """全零市值不应除零，占比归零。"""
    result = allocation_by_asset_type(
        {"600519": 0.0, "518880": 0.0},
        {"600519": "stock", "518880": "gold"},
    )

    assert result == {"stock": 0.0, "gold": 0.0}


def test_allocation_empty_input():
    assert allocation_by_asset_type({}, {}) == {}
