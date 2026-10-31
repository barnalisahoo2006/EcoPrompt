# EcoPrompt

An MCP connector that tells you the **smallest AI model good enough for each task**, and how much
**energy, water and CO₂** that saves per query. It works with Claude, ChatGPT, Cursor and any other
MCP-compatible tool.

> "This is a simple task: Claude Haiku is good enough. Using it instead of Claude Opus uses about
> 96% less energy, saving ~2.31 Wh, ~6.9 mL of water and ~0.92 g CO2 per query."

## Tools

| Tool | What it does |
|---|---|
| `recommend_model` | Right-sized model for a task, with savings vs. your current model |
| `estimate_footprint` | Energy, water and CO₂ of one query to a given model |
| `compare_models` | All models ranked by footprint, marked suitable or not for the task |
| `community_impact` | Anonymous running total of potential savings |

HTTP routes: `/` (landing page with setup steps and live counter), `/mcp` (the connector),
`/stats` (JSON totals), `/health`.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pip install pytest && .venv/bin/python -m pytest -q   # run the tests
```

**In Claude Code on your Mac** (stdio, just for you):

```bash
claude mcp add ecoprompt -- ~/EcoPrompt/.venv/bin/python ~/EcoPrompt/server.py --stdio
```

**As an HTTP server** (what people at RSM will connect to):

```bash
.venv/bin/python server.py            # http://127.0.0.1:8000/mcp
HOST=0.0.0.0 PORT=8000 .venv/bin/python server.py   # reachable from other machines
```

## Deploy so everyone at RSM can use it

1. Push this folder to a GitHub repository.
2. On [render.com](https://render.com), choose **New → Blueprint** and select the repo. `render.yaml`
   sets up a free web service.
3. Your connector URL is `https://<your-service>.onrender.com/mcp`. Share the landing page
   `https://<your-service>.onrender.com/` and people can follow the setup steps there.

Notes:
- Render's free tier sleeps after inactivity, so the first request can take ~30 s.
- Its disk is temporary, so the community counter resets on redeploys. For a persistent counter,
  attach a Render disk and set `ECOPROMPT_DB=/data/ecoprompt.db`, or move the counter to a hosted database.

## Privacy

Prompt text is never stored. The counter keeps only the task level, the two model ids and the
estimated savings. There are no accounts, names or IP addresses.

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md). The figures are estimates, accurate to roughly 2–3× either way.
