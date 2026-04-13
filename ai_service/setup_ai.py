#!/usr/bin/env python3
"""
Interactive setup script for configuring AI model providers.
Run this when deploying to configure your preferred AI model API.

Usage:
    cd ai_oracle_agent/ai_service
    python setup_ai.py
"""

import os
import shutil
from pathlib import Path


PROVIDERS = {
    "1": {
        "name": "OpenAI",
        "env_key": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
        "api_key_hint": "Get from https://platform.openai.com/api-keys",
    },
    "2": {
        "name": "Claude (Anthropic)",
        "env_key": "claude",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model_env": "CLAUDE_MODEL",
        "default_model": "claude-sonnet-4-6-20251106",
        "api_key_hint": "Get from https://console.anthropic.com/settings/keys",
    },
    "3": {
        "name": "Google Gemini",
        "env_key": "google",
        "api_key_env": "GOOGLE_API_KEY",
        "model_env": "GOOGLE_MODEL",
        "default_model": "gemini-2.0-flash",
        "api_key_hint": "Get from https://aistudio.google.com/app/apikey",
    },
    "4": {
        "name": "Minimax",
        "env_key": "minimax",
        "api_key_env": "MINIMAX_API_KEY",
        "model_env": "MINIMAX_MODEL",
        "default_model": "abab6.5s-chat",
        "api_key_hint": "Get from https://www.minimaxi.com/",
    },
    "5": {
        "name": "Kimi (Moonshot AI)",
        "env_key": "kimi",
        "api_key_env": "KIMI_API_KEY",
        "model_env": "KIMI_MODEL",
        "default_model": "moonshot-v1-8k",
        "api_key_hint": "Get from https://platform.moonshot.cn/",
    },
    "6": {
        "name": "Zhipu AI (智谱AI)",
        "env_key": "zhipu",
        "api_key_env": "ZHIPU_API_KEY",
        "model_env": "ZHIPU_MODEL",
        "default_model": "glm-4-flash",
        "api_key_hint": "Get from https://open.bigmodel.cn/",
    },
    "7": {
        "name": "Ollama (local, free)",
        "env_key": "ollama",
        "api_key_env": None,
        "model_env": "OLLAMA_MODEL",
        "default_model": "llama3.2:3b",
        "api_key_hint": "Install from https://ollama.com, then: ollama pull llama3.2:3b",
    },
}


def print_banner():
    print("\n" + "=" * 60)
    print("  AI Oracle Agent - AI Provider Setup")
    print("=" * 60)


def print_providers():
    print("\nSelect your AI provider:\n")
    for num, provider in PROVIDERS.items():
        print(f"  [{num}] {provider['name']}")
    print()


def get_choice() -> str:
    while True:
        choice = input("Enter number (1-7): ").strip()
        if choice in PROVIDERS:
            return choice
        print("Invalid choice. Please enter a number between 1 and 7.")


def get_api_key(provider_info: dict) -> str | None:
    if provider_info["api_key_env"] is None:
        return None

    print(f"\n  Provider: {provider_info['name']}")
    print(f"  Hint: {provider_info['api_key_hint']}")

    while True:
        api_key = input("  API Key: ").strip()
        if api_key:
            return api_key
        print("  API Key cannot be empty.")


def get_model(provider_info: dict) -> str:
    default = provider_info["default_model"]
    print(f"\n  Model (press Enter to use default: {default})")

    model = input("  Model: ").strip()
    return model if model else default


def write_env_file(provider_key: str, api_key: str | None, model: str):
    env_path = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    # Copy .env.example to .env if .env doesn't exist
    if not env_path.exists() and env_example.exists():
        shutil.copy(env_example, env_path)
        print(f"\n  Created {env_path} from .env.example")

    # Read existing env or create new
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    # Update with new values
    env_vars["LLM_PROVIDER"] = provider_key

    if api_key:
        provider_info = next(p for p in PROVIDERS.values() if p["env_key"] == provider_key)
        if provider_info["api_key_env"]:
            env_vars[provider_info["api_key_env"]] = api_key

    provider_info = next(p for p in PROVIDERS.values() if p["env_key"] == provider_key)
    env_vars[provider_info["model_env"]] = model

    # Write back
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            if value:  # Only write non-empty values
                f.write(f"{key}={value}\n")

    print(f"\n  Saved configuration to {env_path}")


def main():
    print_banner()
    print_providers()

    choice = get_choice()
    provider = PROVIDERS[choice]

    print(f"\n  Selected: {provider['name']}")

    api_key = get_api_key(provider) if provider["api_key_env"] else None
    model = get_model(provider)

    write_env_file(provider["env_key"], api_key, model)

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print("\n  Next steps:")
    print("    1. Install dependencies: pip install -r requirements.txt")
    print("    2. Start the service: python main.py")
    print()


if __name__ == "__main__":
    main()
