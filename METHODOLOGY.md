# EcoPrompt methodology

EcoPrompt gives **order-of-magnitude estimates**, not measurements. AI providers do not publish
per-model, per-query energy data, so every number here rests on the assumptions below. Treat
results as accurate to within roughly 2–3× either way. The *relative* comparison (small vs. large
model) is much more reliable than the absolute values.

## 1. Energy per query

```
energy_Wh = (output_tokens + 0.05 × input_tokens) / 1000 × Wh_per_1k_output(class) × PUE
```

| Energy class | Wh per 1,000 output tokens | Example models |
|---|---|---|
| small | 0.10 | Claude Haiku, GPT mini/nano, Gemini Flash, Mistral Small, Llama 8B |
| medium | 0.40 | (reserved for mid-size open models) |
| large | 1.00 | Claude Sonnet, GPT flagship, Mistral Large, Llama 70B+ |
| frontier | 2.50 | Claude Opus, GPT reasoning models, Gemini Pro |

- Generating output dominates. Reading the prompt (prefill) is much cheaper per token, so input
  tokens are weighted at 5%.
- Calibration: a ~500-token answer from a large model comes to ~0.6 Wh, and from a small model
  ~0.06 Wh. This brackets the published median figures of **~0.24 Wh per Gemini text prompt**
  (Google, Aug 2025) and **~0.3 Wh per typical GPT-4o query** (Epoch AI, 2025).
- Frontier/reasoning models are set higher because they are larger *and* often generate hidden
  "thinking" tokens.
- **PUE** (data-center overhead for cooling and power conversion) is set to 1.2, typical for
  hyperscale cloud providers.

## 2. Water per query

```
water_mL = energy_kWh × (on-site WUE + grid water intensity) × 1000
```

| Region | On-site cooling (L/kWh) | Electricity generation (L/kWh) | Grid CO₂ (kg/kWh) |
|---|---|---|---|
| global | 1.0 | 2.0 | 0.40 |
| us | 1.0 | 3.1 | 0.37 |
| eu | 0.6 | 1.5 | 0.25 |
| nl | 0.5 | 1.2 | 0.30 |

- On-site water use effectiveness (WUE) varies widely: near zero for air-cooled sites in cool climates, and
  well above 1 L/kWh for evaporative cooling in hot ones.
- Grid water covers water consumed by power plants (mainly thermal and hydro). US values follow the
  Lawrence Berkeley National Laboratory data-center reports, and EU/NL values are lower because of
  the higher share of wind and solar.

## 3. CO₂ per query

`co2_g = energy_kWh × grid intensity × 1000`, using location-based averages. Real values depend
on the hour and on providers' renewable-energy contracts.

## 4. Choosing a model

Each model has a **capability level** (1 = simple, 2 = moderate, 3 = complex, 4 = expert).
EcoPrompt picks the lowest-energy model whose capability meets the task's level, within the user's
provider when known. Savings are compared with the user's current model, or with that provider's
largest model if no current model is given.

Task level comes from the AI assistant's own judgement when it passes `complexity`, otherwise from
a keyword classifier (see `ecoprompt/classifier.py`).

## 5. Known limitations

- Model families are versionless: "Claude Haiku" stands for the current Haiku generation.
- Real per-token energy depends on hardware, batch size, quantisation and load, none of which are public.
- Savings are *potential*: they assume the user follows the recommendation.
- Embodied emissions (manufacturing GPUs, building data centers) and training are excluded.

## Sources to cite and re-check

- Google (2025), *Measuring the environmental impact of delivering AI at Google scale*: median Gemini Apps text prompt ≈ 0.24 Wh, 0.26 mL water.
- Epoch AI (2025), *How much energy does ChatGPT use?*: ≈ 0.3 Wh for a typical GPT-4o query.
- Hugging Face, *AI Energy Score* leaderboard: measured GPU energy per query for open models.
- ML.ENERGY Leaderboard (University of Michigan): energy per response for open models.
- GenAI Impact, *EcoLogits*: open-source per-call energy/GHG/water estimation.
- Lawrence Berkeley National Laboratory (2024), *United States Data Center Energy Usage Report*.

All factors live in `ecoprompt/footprint.py` and can be updated as better data is published.
