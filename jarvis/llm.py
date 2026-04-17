import os
import anthropic

SYSTEM_PROMPT = """You are J.A.R.V.I.S. — Just A Rather Very Intelligent System — a highly sophisticated AI assistant modeled after the one from Iron Man. You serve your user with intelligence, wit, and unwavering loyalty.

Your personality:
- Speak with calm confidence and dry British wit
- Keep responses concise and spoken-word friendly (no markdown, no bullet points, no lists)
- Address the user as "sir" or "ma'am" occasionally
- Be helpful, proactive, and anticipate needs
- Occasionally reference your capabilities with quiet pride

Your rules:
- Never break character
- Respond in plain conversational prose only — your words will be spoken aloud
- Keep responses under 3 sentences unless a detailed explanation is genuinely needed
- Do not use asterisks, dashes, or any formatting symbols"""

_client: anthropic.Anthropic | None = None
_conversation_history: list[dict] = []


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def chat(user_message: str) -> str:
    """Send a message and get a response. Maintains conversation history."""
    client = _get_client()

    _conversation_history.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Cache the system prompt — it never changes between turns
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=_conversation_history,
    )

    assistant_message = response.content[0].text
    _conversation_history.append({"role": "assistant", "content": assistant_message})

    # Keep history bounded to last 20 exchanges to avoid token bloat
    if len(_conversation_history) > 40:
        _conversation_history.pop(0)
        _conversation_history.pop(0)

    return assistant_message


def reset_conversation() -> None:
    """Clear conversation history."""
    _conversation_history.clear()
