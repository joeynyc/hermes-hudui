"""Regression tests for the MiniMax text provider catalog."""

from backend.api.profiles import profile_options
from backend.api.token_costs import _get_pricing


def test_minimax_presets_keep_flash_first_and_m3_second() -> None:
    options = profile_options()
    assert options["providers"][-3:-1] == ["minimax", "minimax-cn"]

    for provider_id, region, openai_base, anthropic_base in (
        (
            "minimax",
            "global_en",
            "https://api.minimax.io/v1",
            "https://api.minimax.io/anthropic",
        ),
        (
            "minimax-cn",
            "cn_zh",
            "https://api.minimaxi.com/v1",
            "https://api.minimaxi.com/anthropic",
        ),
    ):
        preset = options["provider_presets"][provider_id]
        assert [model["id"] for model in preset["models"]] == [
            "MiniMax-M3.1-Flash",
            "MiniMax-M3",
        ]
        assert all(model["context_window"] == 1_000_000 for model in preset["models"])
        assert all(model["input_modalities"] == ["text", "image", "video"] for model in preset["models"])
        assert preset["models"][0]["thinking"] == ["adaptive"]
        assert preset["models"][0]["reasoning_effort_default"] == "max"
        assert preset["models"][0]["service_tier_supported"] is False
        assert preset["models"][1]["thinking_defaults_by_api"]["anthropic_messages"] == "disabled"
        assert preset["models"][1]["service_tier_supported"] is True
        assert preset["endpoints"] == [
            {
                "region": region,
                "openai_base_url": openai_base,
                "anthropic_base_url": anthropic_base,
                "docs_root": (
                    "https://platform.minimax.io/docs"
                    if provider_id == "minimax"
                    else "https://platform.minimaxi.com/docs"
                ),
            }
        ]


def test_minimax_prices_preserve_unknown_cache_write_rate() -> None:
    flash, flash_key = _get_pricing("MiniMax-M3.1-Flash")
    m3, m3_key = _get_pricing("MiniMax-M3")

    assert flash_key == "minimax-m3.1-flash"
    assert flash["input"] == 0.15
    assert flash["output"] == 0.60
    assert flash["cache_read"] == 0.015
    assert flash["cache_write"] is None
    assert m3_key == "minimax-m3"
    assert m3["input"] == 0.30
    assert m3["output"] == 1.20
    assert m3["cache_read"] == 0.06
    assert m3["cache_write"] is None
