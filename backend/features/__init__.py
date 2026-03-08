"""Feature registry — maps feature name strings to classes.

Usage:
    from features import load_features
    runner = load_features(experimental_config)
"""

from features.base import BaseFeature
from features.news_article import NewsArticleSeed
from features.gate_until_user_post import GateUntilUserPost
from features.runner import FeatureRunner

_REGISTRY: dict[str, type[BaseFeature]] = {
    "news_article": NewsArticleSeed,
    "gate_until_user_post": GateUntilUserPost,
}

# Human-readable metadata for each feature (served to the admin wizard).
FEATURES_META: dict[str, dict[str, str]] = {
    "news_article": {
        "label": "Seed news article",
        "description": "Display a news article at session start",
    },
    "gate_until_user_post": {
        "label": "Gate agents",
        "description": "Agents stay silent until the participant posts first",
    },
}

# Backward-compat mapping: old scenario name → equivalent feature list
_SCENARIO_COMPAT: dict[str, list[str]] = {
    "base": [],
    "news_article": ["news_article", "gate_until_user_post"],
}

AVAILABLE_FEATURES = sorted(_REGISTRY.keys())


def load_features(experimental_config: dict) -> FeatureRunner:
    """Build a FeatureRunner from the experimental config.

    Reads ``experimental_config["features"]`` (a list of feature names).
    Falls back to the legacy ``"scenario"`` key for backward compatibility.
    """
    if "features" in experimental_config:
        names = experimental_config["features"]
    elif "scenario" in experimental_config:
        scenario = experimental_config["scenario"]
        names = _SCENARIO_COMPAT.get(scenario)
        if names is None:
            raise RuntimeError(
                f"Unknown legacy scenario '{scenario}'. "
                f"Available: {', '.join(sorted(_SCENARIO_COMPAT))}"
            )
    else:
        names = []

    features = []
    for name in names:
        cls = _REGISTRY.get(name)
        if cls is None:
            raise RuntimeError(
                f"Unknown feature '{name}'. "
                f"Available: {', '.join(AVAILABLE_FEATURES)}"
            )
        features.append(cls(experimental_config))

    return FeatureRunner(features)
