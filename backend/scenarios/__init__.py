"""Scenario registry — maps scenario name strings to classes.

Usage:
    from scenarios import load_scenario
    scenario = load_scenario(experimental_config)
"""

from scenarios.base import BaseScenario
from scenarios.news_article import NewsArticleScenario

_REGISTRY: dict[str, type[BaseScenario]] = {
    "base": BaseScenario,
    "news_article": NewsArticleScenario,
}


def load_scenario(experimental_config: dict) -> BaseScenario:
    """Instantiate the scenario specified by the experimental config.

    Looks up ``experimental_config["scenario"]`` in the registry.
    Falls back to ``BaseScenario`` when the key is absent, preserving
    backwards-compatible behaviour for existing treatment groups.
    """
    name = experimental_config.get("scenario", "base")
    cls = _REGISTRY.get(name)
    if cls is None:
        raise RuntimeError(
            f"Unknown scenario '{name}'. "
            f"Available: {', '.join(sorted(_REGISTRY))}"
        )
    return cls(experimental_config)
