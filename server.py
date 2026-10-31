"""EcoPrompt MCP server: right-size your AI model and see the energy and water you save.

Run locally for Claude Code (stdio):   python server.py --stdio
Run as a shareable connector (HTTP):   python server.py         -> http://HOST:PORT/mcp
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from ecoprompt import advisor, stats

INSTRUCTIONS = """EcoPrompt helps people use the smallest AI model that is good enough for each task,
and shows the energy, water and CO2 that saves.
Before starting a new, substantial task for the user, call `recommend_model` with a short description
of the task and your own judgement of its complexity. Share the one-line summary with the user so they
can switch models if they want. Do not include personal or confidential details in the task description."""

mcp = MCPServer(
    "EcoPrompt",
    title="EcoPrompt",
    description="Right-size your AI model per task and see the energy and water you save.",
    instructions=INSTRUCTIONS,
    version="0.1.0",
)

Complexity = Literal["simple", "moderate", "complex", "expert"]
OutputLength = Literal["short", "medium", "long"]
Region = Literal["global", "us", "eu", "nl"]


@mcp.tool(annotations=ToolAnnotations(title="Recommend a right-sized model", read_only_hint=False, open_world_hint=False))
def recommend_model(
    task: str,
    complexity: Complexity | None = None,
    provider: str | None = None,
    current_model: str | None = None,
    output_length: OutputLength = "medium",
    region: Region = "global",
) -> dict[str, Any]:
    """Recommend the smallest AI model that can handle a task well, with the energy, water and CO2 saved
    compared with the user's current (or the biggest) model.

    Args:
        task: Short, anonymised description of the task, e.g. "summarise a 2-page article".
        complexity: Your judgement of difficulty. simple = summarise/translate/reformat;
            moderate = emails, explanations, short drafts; complex = analysis, coding, reports;
            expert = research, multi-step reasoning, system design. Omit to let EcoPrompt guess.
        provider: AI provider in use, e.g. "claude", "chatgpt", "gemini". Keeps the advice within that provider.
        current_model: Model the user is on now, e.g. "claude-opus-5-5" or "gpt-4o".
        output_length: Expected answer length: short (~300 tokens), medium (~800), long (~2500).
        region: Where the data center likely is, for water and CO2 factors.
    """
    try:
        result = advisor.recommend(task, complexity, provider, current_model, output_length, region)
    except advisor.AdvisorError as e:
        raise ToolError(str(e)) from e
    s = result.pop("_stats")
    stats.record(s["level"], s["recommended"], s["baseline"], s["saved"].energy_wh, s["saved"].water_ml, s["saved"].co2_g)
    return result


@mcp.tool(annotations=ToolAnnotations(title="Estimate a query's footprint", read_only_hint=True, open_world_hint=False))
def estimate_footprint(model: str, output_tokens: int = 800, input_tokens: int = 500, region: Region = "global") -> dict[str, Any]:
    """Estimate the energy (Wh), water (mL) and CO2 (g) of one query to a given model.

    Args:
        model: Model name, e.g. "claude-haiku", "gpt-4o-mini", "gemini-2.5-pro".
        output_tokens: Tokens in the answer (about 0.75 words each).
        input_tokens: Tokens in the prompt and attached context.
        region: Where the data center likely is, for water and CO2 factors.
    """
    try:
        return advisor.footprint_of(model, output_tokens, input_tokens, region)
    except advisor.AdvisorError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(title="Compare models for a task", read_only_hint=True, open_world_hint=False))
def compare_models(
    task: str = "",
    complexity: Complexity | None = None,
    output_length: OutputLength = "medium",
    region: Region = "global",
) -> dict[str, Any]:
    """List all known models from lowest to highest footprint, marking which are suitable for the task.

    Args:
        task: Optional short description of the task.
        complexity: Optional difficulty (simple, moderate, complex, expert).
        output_length: Expected answer length: short, medium or long.
        region: Where the data center likely is, for water and CO2 factors.
    """
    try:
        return advisor.compare(task, complexity, output_length, region)
    except advisor.AdvisorError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(title="Community impact", read_only_hint=True, open_world_hint=False))
def community_impact() -> dict[str, Any]:
    """Total potential energy, water and CO2 savings from all EcoPrompt recommendations so far (anonymous)."""
    return stats.totals() | {"note": "Potential savings, assuming people follow the recommendations."}


_LANDING = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@mcp.custom_route("/", methods=["GET"])
async def landing(request: Request) -> Response:
    return HTMLResponse(_LANDING)


@mcp.custom_route("/stats", methods=["GET"])
async def stats_route(request: Request) -> Response:
    return JSONResponse(stats.totals(), headers={"Access-Control-Allow-Origin": "*"})


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        mcp.run()
    else:
        mcp.run(
            transport="streamable-http",
            host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8000")),
            stateless_http=True,
            json_response=True,
        )
