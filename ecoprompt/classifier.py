"""Rule-based task complexity classifier.

The AI client usually judges complexity better than keywords can, so tools
accept an explicit `complexity`; this is the fallback when none is given.
"""

from __future__ import annotations

LEVEL_NAMES = {1: "simple", 2: "moderate", 3: "complex", 4: "expert"}

# Checked from the hardest level down; the first level with a match wins.
_KEYWORDS: dict[int, tuple[str, ...]] = {
    4: (
        "prove", "proof", "research", "novel", "architecture", "system design", "multi-step", "multistep",
        "strategy", "legal advice", "diagnos", "refactor", "agent", "valuation", "dcf", "financial model",
        "optimi", "thesis", "dissertation", "end-to-end", "from scratch", "security audit",
    ),
    3: (
        "code", "function", "script", "debug", "bug", "sql", "analy", "compare", "evaluate", "essay",
        "report", "reason", "math", "calculat", "explain why", "case study", "business plan", "forecast",
        "pros and cons", "critique", "review",
    ),
    2: (
        "write", "draft", "email", "explain", "rewrite", "outline", "brainstorm", "cover letter", "linkedin",
        "post", "describe", "suggest", "ideas", "plan",
    ),
    1: (
        "summar", "tl;dr", "tldr", "translate", "grammar", "spell", "proofread", "format", "convert",
        "list", "extract", "classify", "rephrase", "paraphrase", "what is", "define", "title", "shorten",
        "keywords", "capitalize",
    ),
}

# Tasks this long usually carry enough context to need a stronger model.
_LONG_TASK_CHARS = 1500


def classify(task: str) -> tuple[int, str]:
    """Return (level 1-4, human-readable reason)."""
    text = task.lower()
    level, reason = 2, "no clear signal, assuming a moderate task"
    for candidate in (4, 3, 2, 1):
        hits = [k for k in _KEYWORDS[candidate] if k in text]
        if hits:
            level, reason = candidate, f"matched '{hits[0]}'"
            break
    if len(task) > _LONG_TASK_CHARS and level < 3:
        level, reason = level + 1, f"{reason}; bumped up because the task is long"
    return level, reason


def parse_level(value: str | int | None) -> int | None:
    """Accept 1-4 or a level name ("simple", "complex", ...)."""
    if value is None or value == "":
        return None
    if isinstance(value, int) or str(value).strip().isdigit():
        n = int(value)
        return n if 1 <= n <= 4 else None
    names = {v: k for k, v in LEVEL_NAMES.items()}
    return names.get(str(value).strip().lower())
