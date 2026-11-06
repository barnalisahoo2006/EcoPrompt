# EcoPrompt methodology

EcoPrompt gives **order-of-magnitude estimates**, not measurements. AI providers do not publish
per-model, per-query energy data, so every number here rests on the assumptions below. Treat
results as accurate to within roughly 2–3× either way. This applies to savings percentages too:
"small models use less" holds as a general pattern, but not for every model pair (see section 5).

## 1. Energy per query

```
energy_Wh = (output_tokens + 0.05 × input_tokens) / 1000 × Wh_per_1k_output(class) × PUE
```

| Energy class | Wh per 1,000 output tokens | ~500-token answer | Example models |
|---|---|---|---|
| small | 0.30 | 0.18 Wh | Claude Haiku, GPT mini/nano, Gemini Flash, Mistral Small, Llama 8B |
| medium | 0.50 | 0.30 Wh | (reserved for mid-size open models) |
| large | 0.85 | 0.51 Wh | Claude Sonnet, GPT flagship, Mistral Large, Llama 70B+ |
| frontier | 1.70 | 1.02 Wh | Claude Opus, Gemini Pro |
| reasoning | 4.50 | 2.70 Wh | GPT reasoning models |

- Generating output dominates. Reading the prompt (prefill) is much cheaper per token, so input
  tokens are weighted at 5%. Jegham et al.'s GPT-4o figures imply about 6%.
- **Large** is set between Epoch AI (~0.3 Wh for ~500 tokens) and Jegham et al. (GPT-4o, 0.42 Wh for
  300 output tokens, or ~0.7 Wh at 500). Claude Sonnet is higher in Jegham et al. (0.95 Wh for 300).
- **Small** is a judgement call within a wide range. Jegham et al. report 0.05–0.21 Wh for Llama 8B
  and GPT-4.1 nano at 300 tokens, but 0.45–0.98 Wh for GPT-4.1 mini, GPT-4o mini and Claude 3.5 Haiku.
- **Frontier** is set at twice large. This is a judgement call: we found no per-query figure for
  Claude Opus or Gemini Pro. Google's median of ~0.24 Wh covers Gemini Apps prompts generally.
- **Reasoning** is set between o3 (1.18 Wh) and o1 (2.27 Wh) at 300 output tokens, which gives about
  1.6 Wh. Effort settings raise this: o4-mini (high) is 3.65 Wh. DeepSeek-R1 ranges from 2.35 Wh on
  Azure to 19.25 Wh on DeepSeek's own infrastructure.
- Oviedo et al. give a median of 0.34 Wh for frontier-scale models (middle 50%: 0.18–0.67), rising
  to about 4.3 Wh with 15× more tokens. That is why output length is an input here.
- **PUE** (data-center overhead for cooling and power conversion) is set to 1.2. Published values
  include 1.09 (Google), 1.12–1.14 (Azure, AWS) and 1.27 (DeepSeek).
- When no current model is given, savings are compared with the provider's biggest non-reasoning
  model, because reasoning models are an opt-in choice.

## 2. Water per query

```
water_mL = energy_kWh × (on-site WUE + grid water intensity) × 1000
```

| Region | On-site cooling (L/kWh) | Electricity generation (L/kWh) | Grid CO₂ (kg/kWh) |
|---|---|---|---|
| global | 1.0 | 4.35 | 0.40 |
| us | 1.0 | 4.7 | 0.37 |
| eu | 0.6 | 1.5 | 0.25 |
| nl | 0.5 | 1.2 | 0.30 |

- On-site water use effectiveness (WUE) varies widely: near zero for air-cooled sites in cool climates, and
  well above 1 L/kWh for evaporative cooling in hot ones.
- Grid water covers water consumed by power plants (mainly thermal and hydro). The US value is
  between the Azure (4.35 L/kWh) and AWS (5.11 L/kWh) values in Jegham et al. The global value uses the
  lower of the two as a stand-in, because we found no published global average. EU/NL values are lower
  because of the higher share of wind and solar, and have not been re-checked against this research.
- These figures count both on-site and power plant water, so they are **not comparable** with
  Google's 0.26 mL or Altman's 0.32 mL. Google's figure appears to cover data-center water only, and
  Altman's boundary is unstated. Google's on-site factor is 1.15 L/kWh, Azure's 0.30 and AWS's 0.18.
- Published estimates vary widely with their boundary: about 1.9 mL (GPT-4o, derived from Jegham et
  al.) and 45 mL (Mistral Large 2 lifecycle study, 400 tokens).

## 3. CO₂ per query

`co2_g = energy_kWh × grid intensity × 1000`, using location-based averages. Real values depend
on the hour and on providers' renewable-energy contracts.

Google's 0.03 g per prompt is market-based, so it credits clean energy purchases and is not directly
comparable. At the 0.40 kg/kWh global average used here, Google's 0.24 Wh would be about 0.10 g.
Mistral's 1.14 g covers a broader lifecycle boundary.

## 4. Choosing a model

Each model has a **capability level** (1 = simple, 2 = moderate, 3 = complex, 4 = expert).
EcoPrompt picks the lowest-energy model whose capability meets the task's level, within the user's
provider when known. Savings are compared with the user's current model, or with that provider's
largest non-reasoning model if no current model is given.

Task level comes from the AI assistant's own judgement when it passes `complexity`, otherwise from
a keyword classifier (see `ecoprompt/classifier.py`).

## 5. Known limitations

- Model families are versionless: "Claude Haiku" stands for the current Haiku generation.
- Real per-token energy depends on hardware, batch size, quantisation and load, none of which are public.
- **Size is not a guarantee of savings.** In Jegham et al., Claude 3.5 Haiku (0.975 Wh) is about level
  with Claude 3.5 Sonnet (0.973 Wh), and GPT-4o mini (0.577 Wh) is above GPT-4o (0.423 Wh), partly
  because of the older hardware assumed for it. These figures are inferred from public API
  performance, not measured, but a specific savings percentage should not be presented as precise.
- Reasoning effort is not an input, although it can change energy use several times over.
- Published figures are mostly from 2025, and efficiency is improving quickly: Google reports a 33×
  drop in energy per median prompt over one year.
- Savings are *potential*: they assume the user follows the recommendation.
- Embodied emissions (manufacturing GPUs, building data centers) and training are excluded.

## Sources to cite and re-check

- Elsworth et al. (Google, 2025), *Measuring the environmental impact of delivering AI at Google Scale*, [arXiv:2508.15734](https://arxiv.org/abs/2508.15734): median Gemini Apps text prompt ≈ 0.24 Wh, 0.03 gCO₂e (market-based), 0.26 mL water.
- Jegham et al. (2025), *How Hungry is AI?*, [arXiv:2505.09598](https://arxiv.org/abs/2505.09598) (v5 figures; headline numbers changed between versions, so cite the version).
- Oviedo et al. (Microsoft Research, 2025), *Energy Use of AI Inference: Efficiency Pathways and Test-Time Compute*, [arXiv:2509.20241](https://arxiv.org/abs/2509.20241): median 0.34 Wh for frontier-scale models.
- Li, Ren et al., *Making AI Less "Thirsty"*, [arXiv:2304.03271](https://arxiv.org/abs/2304.03271): the on-site and off-site water framework; its 500 mL figure reflects GPT-3 era systems.
- Mistral AI (2025), Mistral Large 2 lifecycle assessment, with Carbone 4 and ADEME: 1.14 gCO₂e and 45 mL per 400-token response.
- Epoch AI (2025), *How much energy does ChatGPT use?*: ≈ 0.3 Wh for a typical GPT-4o query.
- Hugging Face, *AI Energy Score* leaderboard: measured GPU energy per query for open models.
- ML.ENERGY Leaderboard (University of Michigan): energy per response for open models.
- GenAI Impact, *EcoLogits*: open-source per-call energy/GHG/water estimation.
- Lawrence Berkeley National Laboratory (2024), *United States Data Center Energy Usage Report*.

All factors live in `ecoprompt/footprint.py` and can be updated as better data is published.
