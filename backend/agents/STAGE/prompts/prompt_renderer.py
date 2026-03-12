"""
Prompt renderer with conditional blocks for system vs user prompt variants.

Each role has a single .md template containing shared content plus
conditional blocks delimited by:

    {#SYSTEM} ... {/SYSTEM}   — included only in the system prompt
    {#USER}   ... {/USER}     — included only in the user prompt

Content outside any conditional block is included in both variants.
"""

import re

_BLOCK_RE = re.compile(
    r"\{#(SYSTEM|USER)\}\s*?\n(.*?)\{/\1\}\s*?\n?",
    re.DOTALL,
)


def render(template: str, mode: str) -> str:
    """Render a unified template for the given mode ('system' or 'user').

    Keeps blocks matching *mode*, strips blocks for the other mode,
    and collapses runs of 3+ blank lines down to 2.
    """
    if mode not in ("system", "user"):
        raise ValueError(f"mode must be 'system' or 'user', got {mode!r}")

    keep_tag = mode.upper()  # "SYSTEM" or "USER"

    def _replace(m: re.Match) -> str:
        tag = m.group(1)
        content = m.group(2)
        if tag == keep_tag:
            return content  # keep the content, drop the markers
        return ""           # strip the entire block

    result = _BLOCK_RE.sub(_replace, template)

    # Collapse excessive blank lines left by stripped blocks
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result
