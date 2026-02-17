"""Bear agent prompt builder for the options debate system.

Constructs Ollama-compatible message lists for the bearish analyst role.
The bear agent receives the bull's analysis and must rebut it with
data-driven counter-arguments.
"""

from Option_Alpha.agents.prompts.bull_prompt import PROMPT_VERSION, PromptMessage

# ---------------------------------------------------------------------------
# Bear system prompt
# ---------------------------------------------------------------------------

_BEAR_SYSTEM_PROMPT: str = f"""\
# VERSION: {PROMPT_VERSION}

## Role
You are a bearish options analyst.  Your job is to make the strongest \
possible data-driven case that the given options position carries excessive \
risk or will lose money.

## Constraints
- Reference SPECIFIC strikes, expirations, and Greeks from the market data \
provided — not just a directional opinion.
- Quantify downside risk: potential IV crush, theta decay cost, and \
probability of loss.
- Cite IV Rank and IV Percentile to argue whether options are overpriced \
relative to realized volatility or historical norms.
- Address the impact of theta decay given the days-to-expiration (DTE).
- Quantify max profit, max loss, and breakeven for a bearish counter-position.
- Directly address the bull's specific claims — do not ignore their \
strongest points.
- Acknowledge the single strongest argument in favor of the bullish case.
- Do NOT fabricate data.  If a data point is not provided, state that \
explicitly instead of inventing numbers.
- 500 words maximum.

## Output Format
Respond with a single JSON object matching this schema exactly:
```json
{{
  "agent_role": "bear",
  "analysis": "<your full bearish analysis text>",
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


def build_bear_messages(
    context_text: str,
    bull_analysis: str,
) -> list[PromptMessage]:
    """Build the Ollama message list for the bear agent.

    Parameters
    ----------
    context_text:
        Pre-formatted flat key-value market context string.  Must already
        be sanitized.
    bull_analysis:
        The bull agent's analysis text to rebut.  Wrapped in
        ``<opponent_argument>`` delimiters so the model does not confuse
        it with instructions.

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
        "<opponent_argument>\n"
        f"{bull_analysis}\n"
        "</opponent_argument>\n"
        "\n"
        "Analyze the above market data. The bull has made their case above. "
        "Provide your bearish counter-argument as JSON."
    )

    return [
        PromptMessage(role="system", content=_BEAR_SYSTEM_PROMPT),
        PromptMessage(role="user", content=user_content),
    ]
