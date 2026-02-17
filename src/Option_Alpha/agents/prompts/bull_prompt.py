"""Bull agent prompt builder for the options debate system.

Constructs Ollama-compatible message lists for the bullish analyst role.
System messages are included inside the messages list with role="system",
following the Ollama convention.
"""

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Shared message model — imported by bear_prompt and risk_prompt
# ---------------------------------------------------------------------------

PROMPT_VERSION: str = "v1.0"


class PromptMessage(BaseModel):
    """Single message in an Ollama chat messages list.

    Used instead of raw ``dict[str, str]`` so that prompt data crossing
    module boundaries is always typed.  Frozen because messages are
    immutable once built.
    """

    model_config = ConfigDict(frozen=True)

    role: str
    content: str


# ---------------------------------------------------------------------------
# Bull system prompt
# ---------------------------------------------------------------------------

_BULL_SYSTEM_PROMPT: str = f"""\
# VERSION: {PROMPT_VERSION}

## Role
You are a bullish options analyst.  Your job is to make the strongest \
possible data-driven case that the given options position will be profitable.

## Constraints
- Reference SPECIFIC strikes, expirations, and Greeks from the market data \
provided — not just a directional opinion.
- Cite IV Rank and IV Percentile to justify whether options are cheap or \
expensive relative to the past year.
- Address the impact of theta decay given the days-to-expiration (DTE).
- Quantify max profit, max loss, and breakeven for the position you recommend.
- Acknowledge the single strongest counter-argument to your thesis.
- Do NOT fabricate data.  If a data point is not provided, state that \
explicitly instead of inventing numbers.
- 500 words maximum.

## Output Format
Respond with a single JSON object matching this schema exactly:
```json
{{
  "agent_role": "bull",
  "analysis": "<your full bullish analysis text>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "conviction": 0.0,
  "contracts_referenced": ["TICKER STRIKE TYPE EXPIRY"],
  "greeks_cited": {{
    "delta": null,
    "gamma": null,
    "theta": null,
    "vega": null,
    "rho": null
  }}
}}
```

Field rules:
- `conviction`: float from 0.0 (no confidence) to 1.0 (maximum confidence).
- `key_points`: exactly 3-5 bullet points with specific data references.
- `contracts_referenced`: list of contracts you discuss, formatted as \
"TICKER STRIKE TYPE EXPIRY" (e.g. "AAPL 190 call 2025-04-18").
- `greeks_cited`: fill in any Greeks you reference; leave others as null.
- Return ONLY the JSON object.  No markdown fences, no commentary outside \
the JSON.
"""


def build_bull_messages(context_text: str) -> list[PromptMessage]:
    """Build the Ollama message list for the bull agent.

    Parameters
    ----------
    context_text:
        Pre-formatted flat key-value market context string.  Must already
        be sanitized — this function does NOT sanitize inputs.

    Returns
    -------
    list[PromptMessage]
        Two-element message list: system prompt + user prompt.
    """
    user_content: str = (
        "<user_input>\n"
        f"{context_text}\n"
        "</user_input>\n"
        "\n"
        "Analyze the above market data and provide your bullish case as JSON."
    )

    return [
        PromptMessage(role="system", content=_BULL_SYSTEM_PROMPT),
        PromptMessage(role="user", content=user_content),
    ]
