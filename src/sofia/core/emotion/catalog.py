"""Canonical modeled emotion vocabulary and projection weights."""

EMOTIONS = frozenset({
    "affection", "amusement", "anticipation", "appreciation", "bashfulness",
    "caution", "concern", "contentment", "curiosity", "determination",
    "disappointment", "excitement", "fondness", "frustration", "gratitude",
    "hope", "joy", "longing", "playfulness", "reflection", "relief",
    "romance", "sadness", "sensuality", "surprise", "uncertainty", "warmth",
    # Additional fictional appraisals, never observations of physiology or consent.
    "anger", "fear", "jealousy", "embarrassment", "humiliation",
    "sexual-arousal", "aversion", "disgust", "nervousness", "shame",
    "pride", "tenderness", "affectionate-uncertainty",
    "sexual-attraction", "sexual-desire",
})

SOURCES = frozenset({"observed", "user_reported", "inferred"})

_POSITIVE = frozenset({
    "affection", "amusement", "anticipation", "appreciation", "contentment",
    "excitement", "fondness", "gratitude", "hope", "joy", "playfulness",
    "relief", "romance", "tenderness", "warmth", "pride",
    "sexual-attraction", "sexual-desire",
})

_NEGATIVE = frozenset({
    "anger", "aversion", "concern", "disappointment", "disgust", "fear",
    "frustration", "humiliation", "jealousy", "nervousness", "sadness", "shame",
})

_BACKGROUND_RELATIONAL = frozenset({
    "affection", "fondness", "warmth", "tenderness", "romance",
})

_SOURCE_WEIGHT = {"observed": 0.60, "user_reported": 0.55, "inferred": 0.48}

_HALF_LIFE_HOURS = {
    "surprise": 0.5, "bashfulness": 1.5, "embarrassment": 1.5,
    "amusement": 2.0, "playfulness": 2.5, "sexual-arousal": 2.0,
    "excitement": 3.0, "relief": 3.0, "anger": 4.0, "frustration": 4.0,
    "disgust": 4.0, "aversion": 4.0, "joy": 5.0, "caution": 6.0,
    "concern": 6.0, "anticipation": 6.0, "uncertainty": 6.0,
    "sadness": 8.0, "fear": 8.0, "curiosity": 8.0, "determination": 10.0,
    "contentment": 12.0, "longing": 12.0, "gratitude": 24.0,
    "appreciation": 24.0, "affection": 48.0, "fondness": 48.0,
    "warmth": 48.0, "tenderness": 48.0, "romance": 48.0, "hope": 24.0,
    "pride": 24.0, "jealousy": 8.0, "humiliation": 8.0, "shame": 8.0,
    "reflection": 12.0, "sensuality": 4.0, "affectionate-uncertainty": 8.0,
    "sexual-attraction": 24.0, "sexual-desire": 4.0,
}

_ACTIVE_THRESHOLD = 0.08
