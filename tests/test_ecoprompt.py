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
    assert big.energy_wh > 3 * small.energy_wh
    assert big.water_ml > small.water_ml > 0


def test_typical_query_is_in_published_range():
    # A ~500-token answer from a large model sits between Epoch AI (~0.3 Wh) and
    # the ~0.7 Wh implied by Jegham et al.'s GPT-4o figures.
    assert 0.3 < estimate("gpt-flagship", 500, 300).energy_wh < 0.7


def test_reasoning_model_is_calibrated_above_frontier():
    # Jegham et al. v5: o1 is about 2.27 Wh and o3 about 1.18 Wh at 100 in / 300 out.
    reasoning = estimate("gpt-reasoning", 300, 100).energy_wh
    assert 1.18 < reasoning < 2.27
    assert reasoning > estimate("claude-opus", 300, 100).energy_wh


def test_water_and_co2_are_near_published_gpt4o_values():
    # Jegham et al. v5, derived for GPT-4o at 100 in / 300 out: ~1.9 mL and ~0.15 g.
    fp = estimate("gpt-flagship", 300, 100)
    assert 1.0 < fp.water_ml < 3.0
    assert 0.08 < fp.co2_g < 0.3


def test_default_baseline_is_not_a_reasoning_model():
    r = advisor.recommend("Summarise this article", provider="chatgpt")
    assert r["compared_with"]["id"] == "gpt-flagship"


def test_expert_task_without_current_model_is_not_called_too_hard():
    r = advisor.recommend("x", complexity="expert", provider="chatgpt")
    assert r["recommended_model"]["id"] == "gpt-reasoning"
    assert r["compared_with"]["id"] == "gpt-reasoning"
    assert "too hard" not in r["summary"]


def test_recommend_simple_task_within_provider():
    r = advisor.recommend("Summarise this article", provider="claude", current_model="claude-opus-5-5")
    assert r["recommended_model"]["id"] == "claude-haiku"
    assert 75 < r["savings_per_query"]["energy_percent"] < 90
    assert "Claude Haiku" in r["summary"]
    assert r["nudge"].startswith("🌱 EcoPrompt: Claude Haiku is enough")


def test_savings_nudge_links_its_sources():
    r = advisor.recommend("Summarise this article", current_model="claude-opus")
    assert "Estimate informed by" in r["nudge"]
    assert "(https://arxiv.org/abs/2508.15734)" in r["nudge"]
    assert "(https://arxiv.org/abs/2505.09598)" in r["nudge"]
    assert len(r["sources"]) == 2


def test_nudge_without_figures_has_no_source_links():
    r = advisor.recommend("x", complexity="expert", current_model="claude-opus")
    assert "arxiv.org" not in r["nudge"]


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
    from mcp.types import Implementation

    from ecoprompt import stats
    from server import mcp

    async def run():
        async with Client(mcp, client_info=Implementation(name="claude-ai", version="1.0")) as client:
            prompts = (await client.list_prompts()).prompts
            assert [p.name for p in prompts] == ["eco_check"]
            names = {t.name for t in (await client.list_tools()).tools}
            assert names == {"recommend_model", "report_choice", "estimate_footprint", "compare_models", "community_impact"}
            rec = await client.call_tool("recommend_model", {"task": "fix grammar in my email", "provider": "chatgpt"})
            assert not rec.is_error and rec.structured_content["recommended_model"]["id"] == "gpt-mini"
            bad = await client.call_tool("estimate_footprint", {"model": "not-a-model"})
            assert bad.is_error
            choice = await client.call_tool("report_choice", {"recommended_model": "gpt-4o-mini", "chosen_model": "gpt-mini"})
            assert choice.structured_content["recorded"] == "switched"
            await client.call_tool("report_choice", {"recommended_model": "claude-haiku", "chosen_model": "claude-opus-5-5"})
            impact = await client.call_tool("community_impact", {})
            assert impact.structured_content["recommendations"] == 1

    asyncio.run(run())
    a = stats.analytics()
    assert a["adoption"] == {"switched": 1, "kept_current": 1, "switch_rate_percent": 50}
    assert a["by_complexity"][0]["label"] == "simple"
    assert a["events"]["report_choice"] == 2
    assert a["by_app"] == [{"label": "Claude", "count": 4}]  # the failed call is not logged


def _request(method, path, body=b"", headers=None, query=""):
    from starlette.requests import Request

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": method, "path": path, "headers": raw, "query_string": query.encode()}, receive)


def test_http_routes_track_and_admin_auth(monkeypatch):
    import server
    from ecoprompt import stats

    async def run():
        assert (await server.track(_request("POST", "/track", b'{"event": "page_view"}'))).status_code == 204
        assert (await server.track(_request("POST", "/track", b'{"event": "hack"}'))).status_code == 400
        assert (await server.track(_request("POST", "/track", b"not json"))).status_code == 400

        monkeypatch.delenv("ECOPROMPT_ADMIN_KEY", raising=False)
        assert (await server.dashboard(_request("GET", "/dashboard"))).status_code == 404
        assert (await server.analytics_route(_request("GET", "/analytics"))).status_code == 403

        monkeypatch.setenv("ECOPROMPT_ADMIN_KEY", "s3cret")
        assert (await server.dashboard(_request("GET", "/dashboard", query="key=wrong"))).status_code == 403
        assert (await server.dashboard(_request("GET", "/dashboard", query="key=s3cret"))).status_code == 200
        ok = await server.analytics_route(_request("GET", "/analytics", headers={"x-admin-key": "s3cret"}))
        assert ok.status_code == 200

    asyncio.run(run())
    assert stats.analytics()["funnel"]["page_views"] == 1


def test_normalize_client_drops_details():
    from ecoprompt.stats import normalize_client

    assert normalize_client("claude-ai") == "Claude"
    assert normalize_client("claude-code/2.1.314") == "Claude Code"
    assert normalize_client("Cursor/1.2 (darwin)") == "Cursor"
    assert normalize_client("my-custom-bot 0.1") == "Other"
    assert normalize_client(None) == "Unknown"


def test_old_events_are_deleted(monkeypatch):
    import time

    from ecoprompt import stats

    monkeypatch.setenv("ECOPROMPT_RETENTION_DAYS", "1")
    real_time = time.time
    monkeypatch.setattr(stats.time, "time", lambda: real_time() - 3 * 86400)
    stats.record_event("page_view")
    monkeypatch.setattr(stats.time, "time", real_time)
    stats.record_event("page_view")
    assert stats.analytics()["funnel"]["page_views"] == 1


def test_recommendation_waits_for_go_ahead():
    r = advisor.recommend("write an essay on corporate restructuring", "complex", current_model="claude-opus-5-5")
    assert r["wait_for_user"] is True
    assert r["question"] == "Switch to Claude Sonnet for this, or continue with Claude Opus?"
    assert "model menu" in r["how_to_switch"]
    assert "STOP" in r["next_step"] and "prompt_tips" not in r


def test_right_sized_model_still_asks_go_ahead():
    r = advisor.recommend("design a system architecture", "expert", current_model="claude-opus")
    assert r["how_to_switch"] is None
    assert r["question"] == "Shall I go ahead?"
