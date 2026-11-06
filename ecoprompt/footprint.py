"""Energy, water and CO2 estimates for a single AI query.

All numbers are order-of-magnitude estimates, not measurements. Providers do
not publish per-model, per-query energy figures, so EcoPrompt uses a transparent
model: tokens x energy-per-token (by model size class), scaled by data-center
overhead (PUE), then converted to water and CO2 with regional factors.
See METHODOLOGY.md for the assumptions and their sources.
"""

from __future__ import annotations

from dataclasses import dataclass

# Server-side energy per 1,000 output tokens (Wh), before data-center overhead.
# Calibrated against Epoch AI (2025), Google (2025), Oviedo et al. (2025) and
# Jegham et al. (2025, v5). See METHODOLOGY.md for the evidence behind each class.
ENERGY_CLASSES: dict[str, dict] = {
    "small": {"wh_per_1k_output": 0.30, "label": "Small / fast model"},
    "medium": {"wh_per_1k_output": 0.50, "label": "Mid-size model"},
    "large": {"wh_per_1k_output": 0.85, "label": "Large model"},
    "frontier": {"wh_per_1k_output": 1.70, "label": "Frontier model"},
    "reasoning": {"wh_per_1k_output": 4.50, "label": "Reasoning model"},
}

# Reading the prompt (prefill) costs far less per token than generating output.
# Jegham et al.'s GPT-4o figures imply about 0.06.
INPUT_TOKEN_WEIGHT = 0.05

# pue: data-center overhead multiplier
# wue_l_per_kwh: water evaporated on site for cooling
# grid_water_l_per_kwh: water used to generate the electricity
# grid_kg_co2_per_kwh: carbon intensity of the electricity
REGIONS: dict[str, dict] = {
    "global": {"pue": 1.20, "wue_l_per_kwh": 1.0, "grid_water_l_per_kwh": 4.35, "grid_kg_co2_per_kwh": 0.40},
    "us": {"pue": 1.20, "wue_l_per_kwh": 1.0, "grid_water_l_per_kwh": 4.7, "grid_kg_co2_per_kwh": 0.37},
    "eu": {"pue": 1.20, "wue_l_per_kwh": 0.6, "grid_water_l_per_kwh": 1.5, "grid_kg_co2_per_kwh": 0.25},
    "nl": {"pue": 1.20, "wue_l_per_kwh": 0.5, "grid_water_l_per_kwh": 1.2, "grid_kg_co2_per_kwh": 0.30},
}

# capability: the hardest task level the model handles well
# (1 = simple, 2 = moderate, 3 = complex, 4 = expert).
MODELS: dict[str, dict] = {
    "claude-haiku": {"name": "Claude Haiku", "provider": "anthropic", "capability": 2, "energy_class": "small"},
    "claude-sonnet": {"name": "Claude Sonnet", "provider": "anthropic", "capability": 3, "energy_class": "large"},
    "claude-opus": {"name": "Claude Opus", "provider": "anthropic", "capability": 4, "energy_class": "frontier"},
    "gpt-mini": {"name": "GPT mini / nano", "provider": "openai", "capability": 2, "energy_class": "small"},
    "gpt-flagship": {"name": "GPT flagship", "provider": "openai", "capability": 3, "energy_class": "large"},
    "gpt-reasoning": {"name": "GPT reasoning (o-series / thinking)", "provider": "openai", "capability": 4, "energy_class": "reasoning"},
    "gemini-flash": {"name": "Gemini Flash", "provider": "google", "capability": 2, "energy_class": "small"},
    "gemini-pro": {"name": "Gemini Pro", "provider": "google", "capability": 4, "energy_class": "frontier"},
    "mistral-small": {"name": "Mistral Small", "provider": "mistral", "capability": 2, "energy_class": "small"},
    "mistral-large": {"name": "Mistral Large", "provider": "mistral", "capability": 3, "energy_class": "large"},
    "llama-small": {"name": "Llama 8B-class", "provider": "meta", "capability": 1, "energy_class": "small"},
    "llama-large": {"name": "Llama 70B+-class", "provider": "meta", "capability": 3, "energy_class": "large"},
}

# Ordered (keywords, model_id): the first rule with a keyword in the name wins.
# Brand names come first so e.g. "gemini-2.5-pro" never hits an OpenAI rule.
_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (("haiku",), "claude-haiku"),
    (("sonnet",), "claude-sonnet"),
    (("opus", "claude"), "claude-opus"),
    (("flash",), "gemini-flash"),
    (("gemini",), "gemini-pro"),
    (("mistral-small", "ministral", "mistral small"), "mistral-small"),
    (("mistral", "mixtral"), "mistral-large"),
    (("8b", "3b", "1b"), "llama-small"),
    (("llama",), "llama-large"),
    (("mini", "nano"), "gpt-mini"),
    (("o1", "o3", "o4", "thinking", "reasoning", "-pro"), "gpt-reasoning"),
    (("gpt", "chatgpt"), "gpt-flagship"),
]

PROVIDER_ALIASES = {
    "claude": "anthropic", "anthropic": "anthropic",
    "chatgpt": "openai", "openai": "openai", "gpt": "openai",
    "gemini": "google", "google": "google",
    "mistral": "mistral", "le chat": "mistral",
    "llama": "meta", "meta": "meta",
}

OUTPUT_LENGTH_TOKENS = {"short": 300, "medium": 800, "long": 2500}

# Everyday equivalents used to make small numbers tangible.
WH_PER_PHONE_CHARGE = 15.0
ML_PER_GLASS = 250.0
G_CO2_PER_KM_CAR = 170.0


@dataclass(frozen=True)
class Footprint:
    energy_wh: float
    water_ml: float
    co2_g: float

    def minus(self, other: Footprint) -> Footprint:
        return Footprint(self.energy_wh - other.energy_wh, self.water_ml - other.water_ml, self.co2_g - other.co2_g)

    def scaled(self, factor: float) -> Footprint:
        return Footprint(self.energy_wh * factor, self.water_ml * factor, self.co2_g * factor)

    def as_dict(self) -> dict:
        return {"energy_wh": round(self.energy_wh, 4), "water_ml": round(self.water_ml, 3), "co2_g": round(self.co2_g, 4)}


def resolve_model(name: str) -> str | None:
    """Map a free-form model name ("claude-opus-5-5", "GPT-4o mini") to a catalog id."""
    key = name.strip().lower()
    if key in MODELS:
        return key
    for keywords, model_id in _ALIASES:
        if any(k in key for k in keywords):
            return model_id
    return None


def resolve_provider(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    for alias, provider in PROVIDER_ALIASES.items():
        if alias in key:
            return provider
    return None


def resolve_region(name: str | None) -> str:
    key = (name or "global").strip().lower()
    return key if key in REGIONS else "global"


def estimate(model_id: str, output_tokens: int, input_tokens: int = 0, region: str = "global") -> Footprint:
    """Footprint of one query: energy incl. data-center overhead, water (on-site + grid), CO2."""
    energy_class = ENERGY_CLASSES[MODELS[model_id]["energy_class"]]
    factors = REGIONS[resolve_region(region)]
    effective_tokens = max(output_tokens, 0) + INPUT_TOKEN_WEIGHT * max(input_tokens, 0)
    energy_wh = effective_tokens / 1000 * energy_class["wh_per_1k_output"] * factors["pue"]
    energy_kwh = energy_wh / 1000
    water_ml = energy_kwh * (factors["wue_l_per_kwh"] + factors["grid_water_l_per_kwh"]) * 1000
    co2_g = energy_kwh * factors["grid_kg_co2_per_kwh"] * 1000
    return Footprint(energy_wh, water_ml, co2_g)


def equivalents(fp: Footprint) -> dict:
    return {
        "phone_charges": round(fp.energy_wh / WH_PER_PHONE_CHARGE, 2),
        "glasses_of_water": round(fp.water_ml / ML_PER_GLASS, 2),
        "km_by_car": round(fp.co2_g / G_CO2_PER_KM_CAR, 3),
    }
