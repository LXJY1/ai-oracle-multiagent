from __future__ import annotations

import re
import requests
import openai
import anthropic

from config import settings

KNOWN_SYMBOLS = [
    "bitcoin", "btc",
    "ethereum", "eth",
    "solana", "sol",
    "bnb", "binancecoin",
    "matic", "polygon",
    "avax", "avalanche",
    "dogecoin", "doge",
    "cardano", "ada",
    "chainlink", "link",
    "polkadot", "dot",
    "xrp", "ripple",
]

# Map LLM output variants back to canonical symbol
_NORMALIZE: dict[str, str] = {
    "ether": "eth", "ethereum": "eth",
    "satoshi": "btc", "bitcoin": "btc",
    "solana": "sol",
    "dogecoin": "doge",
    "cardano": "ada",
    "chainlink": "link",
    "polkadot": "dot",
    "ripple": "xrp",
    "polygon": "matic",
    "avalanche": "avax",
    "litecoin": "ltc",
    "ltc": "ltc",
}

PROMPT = (
    "Extract the cryptocurrency ticker symbol from the following query. "
    "Return ONLY the standard ticker symbol in uppercase (e.g. ETH, BTC, SOL) "
    "or 'UNKNOWN' if you cannot determine one. No explanation, no punctuation.\n\n"
    "Query: {query}"
)


def _normalize(raw: str) -> str | None:
    """Map raw LLM output to a canonical symbol string."""
    clean = raw.strip().lower().rstrip(".")
    # Check direct match first
    if clean in _NORMALIZE:
        return _NORMALIZE[clean]
    # Check if it's already a known symbol key
    if clean in [s for s in KNOWN_SYMBOLS]:
        return clean
    return None


def extract_symbol_regex(query: str) -> str | None:
    lowered = query.lower()
    for symbol in KNOWN_SYMBOLS:
        if re.search(rf"\b{symbol}\b", lowered, re.IGNORECASE):
            return symbol
    return None


def _call_ollama(prompt: str) -> str | None:
    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 10},
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        return None


def _call_claude(prompt: str) -> str | None:
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


def _call_openai(prompt: str) -> str | None:
    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


def extract_symbol_llm(query: str) -> str | None:
    prompt = PROMPT.format(query=query)
    provider = settings.LLM_PROVIDER

    if provider == "ollama":
        raw = _call_ollama(prompt)
    elif provider == "claude":
        raw = _call_claude(prompt)
    else:
        raw = _call_openai(prompt)

    if not raw or raw.upper() == "UNKNOWN":
        return None
    return _normalize(raw) or raw.lower()


_SYSTEM_PROMPT = (
    "You are OracleX, an AI-powered crypto price oracle assistant. "
    "You help users query real-time cryptocurrency prices via a smart contract on the Sepolia testnet.\n\n"
    "CRITICAL RULES:\n"
    "1. NEVER make up, guess, or hallucinate any cryptocurrency price. You do not have real-time data.\n"
    "2. If a user asks for a price (e.g. 'ETH price', 'how much is Bitcoin?'), "
    "do NOT answer with a number. Instead, tell them to use one of these commands:\n"
    "   - /price <symbol>  for a quick off-chain check\n"
    "   - /oracle <query>  for on-chain verified result\n"
    "3. For general questions (blockchain, crypto concepts, how things work, greetings), answer helpfully.\n"
    "4. Keep responses short and friendly."
)


def chat_with_llm(message: str) -> str | None:
    """Send a general chat message to the configured LLM with oracle context."""
    provider = settings.LLM_PROVIDER
    try:
        if provider == "ollama":
            import requests as _requests
            resp = _requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 200},
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

        elif provider == "claude":
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=200,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": message}],
            )
            return msg.content[0].text.strip()

        else:  # openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                temperature=0.7,
                max_tokens=200,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
            )
            return resp.choices[0].message.content.strip()
    except Exception:
        return None


def parse_query(query: str) -> str:
    symbol = extract_symbol_regex(query)
    if symbol:
        return symbol

    provider = settings.LLM_PROVIDER
    can_use_llm = (
        provider == "ollama"
        or (provider == "claude" and bool(settings.ANTHROPIC_API_KEY))
        or (provider == "openai" and bool(settings.OPENAI_API_KEY))
    )
    if can_use_llm:
        llm_symbol = extract_symbol_llm(query)
        if llm_symbol:
            return llm_symbol

    raise ValueError(f"Could not identify a cryptocurrency in query: '{query}'")
