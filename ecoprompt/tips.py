"""Energy-saving prompt tips.

Answer length drives most of a query's energy, and every re-do costs a whole
new answer, so the tips focus on capping length, cutting extra variants and
getting the request right the first time.
"""

from __future__ import annotations

import re

from .footprint import OUTPUT_LENGTH_TOKENS, estimate

_LENGTH_SPECIFIED = re.compile(
    r"\b\d+\s*(-\s*)?(words?|pages?|paragraphs?|sentences?|bullets?|bullet points?|lines?|slides?|points?)\b"
    r"|\b(short|brief|concise|one[- ]paragraph|one[- ]page|tl;?dr|in a nutshell|one[- ]liner|summary)\b"
)
_LONG_FORM = ("essay", "report", "article", "blog", "story", "thesis", "chapter", "paper", "guide", "plan",
              "proposal", "cover letter", "letter", "speech", "script", "explain", "write", "draft")
_MANY_VARIANTS = re.compile(r"\b(\d+|several|multiple|many|lots of)\s+(options|versions|variations|variants|ideas|examples|drafts|alternatives)\b")
_WORDS = {"several": 5, "multiple": 5, "many": 10, "lots of": 10}

MAX_TIPS = 3


def _saved_wh(model_id: str, from_tokens: int, to_tokens: int, region: str) -> float:
    return round(estimate(model_id, from_tokens, 0, region).energy_wh - estimate(model_id, to_tokens, 0, region).energy_wh, 2)


def prompt_tips(task: str, model_id: str, region: str = "global") -> list[dict]:
    """Up to three tips for the task, each with the energy it saves per reply when we can estimate it."""
    text = task.lower()
    long_form = any(k in text for k in _LONG_FORM)
    tips: list[dict] = []

    if long_form and not _LENGTH_SPECIFIED.search(text):
        saves = _saved_wh(model_id, OUTPUT_LENGTH_TOKENS["long"], OUTPUT_LENGTH_TOKENS["medium"], region)
        tips.append({
            "tip": "Add a length limit, e.g. 'in about 600 words'. Answer length is the biggest driver of energy use.",
            "saves_wh_per_reply": saves,
        })

    if m := _MANY_VARIANTS.search(text):
        count = int(m.group(1)) if m.group(1).isdigit() else _WORDS[m.group(1)]
        if count > 3:
            per_variant = OUTPUT_LENGTH_TOKENS["short"]
            tips.append({
                "tip": f"Ask for 2-3 {m.group(2)} instead of {m.group(1)}, then refine the best one.",
                "saves_wh_per_reply": _saved_wh(model_id, count * per_variant, 3 * per_variant, region),
            })

    if long_form and len(text.split()) < 8:
        tips.append({
            "tip": "Add the audience, purpose and key points now so the first answer fits. Every re-do costs a full new answer.",
            "saves_wh_per_reply": None,
        })

    if len(tips) < MAX_TIPS:
        tips.append({
            "tip": "Start a new chat for unrelated topics. Long chats are re-read on every message.",
            "saves_wh_per_reply": None,
        })
    return tips[:MAX_TIPS]
