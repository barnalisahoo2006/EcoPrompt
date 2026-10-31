import asyncio

import pytest

from ecoprompt import advisor
from ecoprompt.classifier import classify, parse_level
from ecoprompt.footprint import estimate, resolve_model


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ECOPROMPT_DB", str(tmp_path / "test.db"))


@pytest.mark.parametrize(
    "name, expected",
    [
        ("claude-opus-5-5", "claude-opus"),
        ("claude-haiku-5-5", "claude-haiku"),
        ("Claude Sonnet", "claude-sonnet"),
        ("gpt-4o", "gpt-flagship"),
        ("gpt-4o-mini", "gpt-mini"),
        ("o3", "gpt-reasoning"),
        ("gemini-2.5-pro", "gemini-pro"),
        ("gemini-2.5-flash", "gemini-flash"),
        ("llama-3.1-8b", "llama-small"),
        ("mistral-large", "mistral-large"),
        ("totally-unknown", None),
    ],
)
def test_resolve_model(name, expected):
    assert resolve_model(name) == expected


def test_classify_levels():
    assert classify("Translate this paragraph to Dutch")[0] == 1
    assert classify("Draft an email to my professor")[0] == 2
    assert classify("Debug this Python function")[0] == 3
    assert classify("Build a DCF valuation of Unilever")[0] == 4
    assert parse_level("complex") == 3 and parse_level(2) == 2 and parse_level("nope") is None


def test_bigger_models_use_more_energy_and_water():
    small, big = estimate("claude-haiku", 800, 500), estimate("claude-opus", 800, 500)
    assert big.energy_wh > 10 * small.energy_wh
    assert big.water_ml > small.water_ml > 0


def test_typical_query_is_in_published_range():
    # A ~500-token answer from a mid/large model should be roughly 0.1-1 Wh.
    assert 0.1 < estimate("gpt-flagship", 500, 300).energy_wh < 1.0


def test_recommend_simple_task_within_provider():
    r = advisor.recommend("Summarise this article", provider="claude", current_model="claude-opus-5-5")
    assert r["recommended_model"]["id"] == "claude-haiku"
    assert r["savings_per_query"]["energy_percent"] > 90
    assert "Claude Haiku" in r["summary"]


def test_recommend_expert_task_keeps_big_model():
    r = advisor.recommend("Design the architecture of a trading system", current_model="claude-opus")
    assert r["recommended_model"]["id"] == "claude-opus"
    assert r["savings_per_query"]["energy_wh"] == 0
    assert "already the right-sized model" in r["summary"]


def test_recommend_warns_when_current_model_too_weak():
    r = advisor.recommend("x", complexity="expert", current_model="claude-haiku")
    assert r["recommended_model"]["id"] == "claude-opus"
    assert "too hard" in r["summary"]
    assert r["savings_per_query"]["energy_wh"] == 0


def test_invalid_inputs_raise():
    with pytest.raises(advisor.AdvisorError):
        advisor.recommend("x", current_model="unknown-model")
    with pytest.raises(advisor.AdvisorError):
        advisor.recommend("x", output_length="huge")


def test_mcp_tools_end_to_end():
    from mcp import Client

    from server import mcp

    async def run():
        async with Client(mcp) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert names == {"recommend_model", "estimate_footprint", "compare_models", "community_impact"}
            rec = await client.call_tool("recommend_model", {"task": "fix grammar in my email", "provider": "chatgpt"})
            assert not rec.is_error and rec.structured_content["recommended_model"]["id"] == "gpt-mini"
            bad = await client.call_tool("estimate_footprint", {"model": "not-a-model"})
            assert bad.is_error
            impact = await client.call_tool("community_impact", {})
            assert impact.structured_content["recommendations"] == 1

    asyncio.run(run())
