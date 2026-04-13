from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Supported LLM providers: openai | claude | google | minimax | kimi | zhipu | ollama
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Claude (Anthropic)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6-20251106")

    # Google Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

    # Minimax
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_MODEL: str = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")

    # Kimi (Moonshot AI)
    KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "moonshot-v1-8k")

    # Zhipu AI (智谱AI)
    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_MODEL: str = os.getenv("ZHIPU_MODEL", "glm-4-flash")

    # Ollama (local, free)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    # Price / cache
    PRICE_CACHE_TTL: int = int(os.getenv("PRICE_CACHE_TTL", "5"))
    SYMBOL_CACHE_TTL: int = int(os.getenv("SYMBOL_CACHE_TTL", "1800"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.80"))


settings = Settings()
