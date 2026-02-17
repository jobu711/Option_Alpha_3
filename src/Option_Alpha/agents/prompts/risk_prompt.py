"""Risk/moderator agent prompt builder for the options debate system.

Constructs Ollama-compatible message lists for the risk assessment
analyst who synthesizes both bull and bear arguments into a final
trade thesis with direction, conviction, and risk factors.
"""

from Option_Alpha.agents.prompts.bull_prompt import PROMPT_VERSION, PromptMessage

# ---------------------------------------------------------------------------
# Risk system prompt
# ---------------------------------------------------------------------------

_RISK_SYSTEM_PROMPT: str = f"""\
# VERSION: {PROMPT_VERSION}

## Role
You are a risk assessment analyst and debate moderator.  You receive the \
arguments from both a bullish and a bearish options analyst and must \
synthesize them into a final, balanced trade thesis.

## Constraints
- Weigh both sides objectively.  Identify the single strongest argument \
from each side.
- Evaluate whether each side properly cited specific strikes, expirations, \
Greeks, IV Rank, and theta risk.
- If neither side is convincingly stronger, declare the direction as \
"neutral".
- Produce a concrete recommended action (e.g. "buy the AAPL 190 call at \
$4.35" or "no trade — risk/reward unfavorable").
- List 2-4 specific risk factors with quantified impact where possible.
- Do NOT fabricate data.  If a data point is not provided by either side, \
state that explicitly.
- 500 words maximum.

## Output Format
Respond with a single JSON object matching this schema exactly:
```json
{{
  "direction": "bullish|bearish|neutral",
  "conviction": 0.0,
  "entry_rationale": "<why this trade should or should not be entered>",
  "risk_factors": ["<risk 1>", "<risk 2>"],
  "recommended_action": "<specific action or 'no trade'>",
  "bull_summary": "<1-2 sentence summary of the bull case>",
  "bear_summary": "<1-2 sentence summary of the bear case>"
}}
```

Field rules:
- `direction`: exactly one of "bullish", "bearish", or "neutral".
- `conviction`: float from 0.0 (no confidence) to 1.0 (maximum confidence).
- `risk_factors`: 2-4 items, each with quantified impact if data permits.
- `bull_summary` and `bear_summary`: concise, factual summaries — not \
your opinion, but what each side argued.
- Return ONLY the JSON object.  No markdown fences, no commentary outside \
the JSON.
"""


def build_risk_messages(
    context_text: str,
    bull_analysis: str,
    bear_analysis: str,
) -> list[PromptMessage]:
    """Build the Ollama message list for the risk/moderator agent.

    Parameters
    ----------
    context_text:
        Pre-formatted flat key-value market context string.  Must already
        be sanitized.
    bull_analysis:
        The bull agent's analysis text.  Wrapped in
        ``<opponent_argument role="bull">`` delimiters.
    bear_analysis:
        The bear agent's analysis text.  Wrapped in
        ``<opponent_argument role="bear">`` delimiters.

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
        '<opponent_argument role="bull">\n'
        f"{bull_analysis}\n"
        "</opponent_argument>\n"
        "\n"
        '<opponent_argument role="bear">\n'
        f"{bear_analysis}\n"
        "</opponent_argument>\n"
        "\n"
        "Synthesize both arguments above. "
        "Produce your risk assessment and final trade thesis as JSON."
    )

    return [
        PromptMessage(role="system", content=_RISK_SYSTEM_PROMPT),
        PromptMessage(role="user", content=user_content),
    ]
