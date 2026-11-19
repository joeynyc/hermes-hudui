"""Pricing regressions for MiniMax text models."""

from backend.api.token_costs import _calc_cost, _get_pricing


def test_minimax_flash_pricing() -> None:
    pricing, key = _get_pricing("MiniMax-M3.1-Flash")
    assert key == "minimax-m3.1-flash"
    assert pricing["input"] == 0.15
    assert pricing["output"] == 0.60


def test_minimax_m3_retains_cache_write_price() -> None:
    pricing, key = _get_pricing("MiniMax-M3")
    assert key == "minimax-m3"
    assert pricing["cache_write"] == 0.30


def test_minimax_flash_cost_with_unknown_cache_write_rate() -> None:
    pricing, _ = _get_pricing("MiniMax-M3.1-Flash")
    assert pricing["cache_write"] is None
    assert _calc_cost({"cache_write": 1_000_000, "input": 1_000_000}, pricing) == 0.15
