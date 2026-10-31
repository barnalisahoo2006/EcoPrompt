"""Model recommendation logic behind the MCP tools."""

from __future__ import annotations

from .classifier import LEVEL_NAMES, classify, parse_level
from .footprint import (
    ENERGY_CLASSES,
    MODELS,
    OUTPUT_LENGTH_TOKENS,
    Footprint,
    equivalents,
    estimate,
    resolve_model,
    resolve_provider,
    resolve_region,
)

DISCLAIMER = "Estimates, not measurements: real values can differ by 2-3x either way. See METHODOLOGY.md."


class AdvisorError(ValueError):
    pass


def _energy_rank(model_id: str) -> float:
    return ENERGY_CLASSES[MODELS[model_id]["energy_class"]]["wh_per_1k_output"]


def _model_info(model_id: str) -> dict:
    m = MODELS[model_id]
    return {"id": model_id, "name": m["name"], "provider": m["provider"], "good_for": LEVEL_NAMES[m["capability"]] + " tasks and easier"}


def _output_tokens(output_length: str) -> int:
    key = (output_length or "medium").strip().lower()
    if key not in OUTPUT_LENGTH_TOKENS:
        raise AdvisorError(f"output_length must be one of {sorted(OUTPUT_LENGTH_TOKENS)}")
    return OUTPUT_LENGTH_TOKENS[key]


def _resolve_level(task: str, complexity: str | int | None) -> tuple[int, str]:
    level = parse_level(complexity)
    if level is not None:
        return level, "complexity given by the caller"
    if complexity not in (None, ""):
        raise AdvisorError("complexity must be 1-4 or one of: simple, moderate, complex, expert")
    return classify(task)


def recommend(
    task: str,
    complexity: str | int | None = None,
    provider: str | None = None,
    current_model: str | None = None,
    output_length: str = "medium",
    region: str = "global",
    input_tokens: int | None = None,
) -> dict:
    level, level_reason = _resolve_level(task, complexity)
    region = resolve_region(region)
    out_tokens = _output_tokens(output_length)
    in_tokens = input_tokens if input_tokens is not None else max(len(task) // 4, 50)

    baseline_id = resolve_model(current_model) if current_model else None
    if current_model and baseline_id is None:
        raise AdvisorError(f"Unknown model '{current_model}'. Known models: {', '.join(MODELS)}")
    provider_id = resolve_provider(provider) or (MODELS[baseline_id]["provider"] if baseline_id else None)

    def suitable(pool: list[str]) -> list[str]:
        return [m for m in pool if MODELS[m]["capability"] >= level]

    same_provider = [m for m in MODELS if MODELS[m]["provider"] == provider_id] if provider_id else list(MODELS)
    candidates = suitable(same_provider) or suitable(list(MODELS))
    recommended_id = min(candidates, key=lambda m: (_energy_rank(m), MODELS[m]["capability"]))
    if baseline_id is None:
        # No current model given: compare against the biggest model people tend to default to.
        baseline_id = max(same_provider or list(MODELS), key=_energy_rank)

    rec_fp = estimate(recommended_id, out_tokens, in_tokens, region)
    base_fp = estimate(baseline_id, out_tokens, in_tokens, region)
    baseline_too_weak = MODELS[baseline_id]["capability"] < level
    saved = base_fp.minus(rec_fp) if not baseline_too_weak else Footprint(0, 0, 0)
    saved = Footprint(max(saved.energy_wh, 0), max(saved.water_ml, 0), max(saved.co2_g, 0))
    pct = round(100 * saved.energy_wh / base_fp.energy_wh) if base_fp.energy_wh else 0
    per_1000 = saved.scaled(1000)

    rec_name, base_name = MODELS[recommended_id]["name"], MODELS[baseline_id]["name"]
    if baseline_too_weak:
        summary = (
            f"This looks like a {LEVEL_NAMES[level]} task, which may be too hard for {base_name}. "
            f"Consider {rec_name} for a better answer."
        )
    elif recommended_id == baseline_id or saved.energy_wh == 0:
        summary = f"{base_name} is already the right-sized model for this {LEVEL_NAMES[level]} task."
    else:
        summary = (
            f"This is a {LEVEL_NAMES[level]} task: {rec_name} is good enough. Using it instead of {base_name} "
            f"uses about {pct}% less energy, saving ~{saved.energy_wh:.2f} Wh, ~{saved.water_ml:.1f} mL of water "
            f"and ~{saved.co2_g:.2f} g CO2 per query (~{per_1000.energy_wh / 1000:.2f} kWh and "
            f"~{per_1000.water_ml / 1000:.1f} L of water per 1,000 queries)."
        )

    return {
        "summary": summary,
        "task_complexity": LEVEL_NAMES[level],
        "complexity_reason": level_reason,
        "recommended_model": _model_info(recommended_id),
        "compared_with": _model_info(baseline_id),
        "footprint_recommended": rec_fp.as_dict(),
        "footprint_compared": base_fp.as_dict(),
        "savings_per_query": saved.as_dict() | {"energy_percent": pct},
        "savings_per_1000_queries": per_1000.as_dict() | {"equivalents": equivalents(per_1000)},
        "assumptions": {"region": region, "output_tokens": out_tokens, "input_tokens": in_tokens},
        "disclaimer": DISCLAIMER,
        "_stats": {"level": level, "recommended": recommended_id, "baseline": baseline_id, "saved": saved},
    }


def footprint_of(model: str, output_tokens: int = 800, input_tokens: int = 500, region: str = "global") -> dict:
    model_id = resolve_model(model)
    if model_id is None:
        raise AdvisorError(f"Unknown model '{model}'. Known models: {', '.join(MODELS)}")
    if output_tokens < 0 or input_tokens < 0:
        raise AdvisorError("Token counts cannot be negative")
    region = resolve_region(region)
    fp = estimate(model_id, output_tokens, input_tokens, region)
    return {
        "model": _model_info(model_id),
        "footprint_per_query": fp.as_dict(),
        "per_1000_queries": fp.scaled(1000).as_dict() | {"equivalents": equivalents(fp.scaled(1000))},
        "assumptions": {"region": region, "output_tokens": output_tokens, "input_tokens": input_tokens},
        "disclaimer": DISCLAIMER,
    }


def compare(task: str = "", complexity: str | int | None = None, output_length: str = "medium", region: str = "global") -> dict:
    level, level_reason = _resolve_level(task, complexity) if (task or complexity) else (1, "no task given")
    region = resolve_region(region)
    out_tokens = _output_tokens(output_length)
    in_tokens = max(len(task) // 4, 50)
    rows = []
    for model_id in sorted(MODELS, key=lambda m: (_energy_rank(m), -MODELS[m]["capability"])):
        fp = estimate(model_id, out_tokens, in_tokens, region)
        rows.append(_model_info(model_id) | {"suitable": MODELS[model_id]["capability"] >= level} | fp.as_dict())
    return {
        "task_complexity": LEVEL_NAMES[level],
        "complexity_reason": level_reason,
        "models": rows,
        "assumptions": {"region": region, "output_tokens": out_tokens, "input_tokens": in_tokens},
        "disclaimer": DISCLAIMER,
    }
