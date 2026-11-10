"""Request-local LLM routing. Offline by default; cloud use requires consent."""

import os
import re
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
STRATEGIES = {"offline", "auto", "always_ollama", "always_openai", "always_gemini"}


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Estimate prompt size locally. No tokenizer download or network request."""
    return max(1, (len(text) + 3) // 4) if text else 0


class LLMRouter:
    """Each request owns its keys, clients, settings, and cloud consent."""

    def __init__(
        self, openai_api_key: str = "", gemini_api_key: str = "",
        ollama_url: str = "http://localhost:11434", ollama_model: str = "llama3.2:3b",
        openai_model: str = "gpt-4o-mini", gemini_model: str = "",
        token_threshold: int = 1500, strategy: str = "offline", allow_cloud: bool = False,
    ):
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self.token_threshold = token_threshold
        self.strategy = strategy if strategy in STRATEGIES else "offline"
        self.allow_cloud = allow_cloud

    def update_config(self, **config):
        """Compatibility helper for the manual diagnostic, never a global instance."""
        allowed = {"openai_api_key", "gemini_api_key", "ollama_model", "openai_model",
                   "gemini_model", "token_threshold", "strategy"}
        for key, value in config.items():
            if key in allowed and value is not None:
                setattr(self, key, value)
        if self.strategy not in STRATEGIES:
            self.strategy = "offline"

    def check_ollama(self) -> bool:
        if self.strategy == "offline":
            return False
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def check_openai(self) -> bool:
        """Configuration check only; it does not validate credentials or spend tokens."""
        return self.allow_cloud and bool(self.openai_api_key)

    def check_gemini(self) -> bool:
        return self.allow_cloud and bool(self.gemini_api_key and self.gemini_model)

    def get_status(self) -> dict:
        return {
            "strategy": self.strategy, "cloud_allowed": self.allow_cloud,
            "openai_configured": self.check_openai(), "gemini_configured": self.check_gemini(),
            "ollama_model": self.ollama_model, "token_threshold": self.token_threshold,
        }

    def _providers(self, prompt: str) -> list[str]:
        if self.strategy == "offline":
            return []
        if self.strategy.startswith("always_"):
            # An explicitly local choice never falls back to a cloud provider.
            order = [self.strategy.removeprefix("always_")]
        elif count_tokens(prompt) > self.token_threshold:
            order = ["gemini", "openai", "ollama"]
        else:
            order = ["ollama", "gemini", "openai"]
        return [p for p in order if p == "ollama" or
                (p == "openai" and self.check_openai()) or
                (p == "gemini" and self.check_gemini())]

    def decide_provider(self, prompt: str) -> tuple[str, int]:
        for provider in self._providers(prompt):
            if provider != "ollama" or self.check_ollama():
                return provider, count_tokens(prompt)
        return "fallback", count_tokens(prompt)

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 800) -> dict:
        prompt = "\n".join(m.get("content", "") for m in messages)
        tokens = count_tokens(prompt)
        # Bounded iteration: provider failures cannot recursively retry one another.
        for provider in self._providers(prompt):
            try:
                if provider == "ollama":
                    response = requests.post(
                        f"{self.ollama_url}/api/chat",
                        json={"model": self.ollama_model, "messages": messages, "stream": False,
                              "options": {"temperature": temperature, "num_predict": max_tokens}},
                        timeout=(3, 20),
                    )
                    response.raise_for_status()
                    content = response.json().get("message", {}).get("content", "")
                    model = self.ollama_model
                elif provider == "openai":
                    from openai import OpenAI
                    with OpenAI(api_key=self.openai_api_key, timeout=20, max_retries=0) as client:
                        response = client.chat.completions.create(
                            model=self.openai_model, messages=messages,
                            temperature=temperature, max_tokens=max_tokens,
                        )
                    content = response.choices[0].message.content
                    model = self.openai_model
                else:
                    # REST keeps Gemini optional without a process-global SDK configuration.
                    if not re.fullmatch(r"[A-Za-z0-9._-]+", self.gemini_model):
                        continue
                    contents = [
                        {"role": "model" if m["role"] == "assistant" else "user",
                         "parts": [{"text": m["content"]}]}
                        for m in messages if m["role"] != "system"
                    ]
                    payload = {
                        "contents": contents,
                        "systemInstruction": {"parts": [{"text": "\n".join(
                            m["content"] for m in messages if m["role"] == "system")}]},
                        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
                    }
                    response = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent",
                        headers={"x-goog-api-key": self.gemini_api_key}, json=payload, timeout=(3, 20),
                    )
                    response.raise_for_status()
                    parts = response.json()["candidates"][0]["content"]["parts"]
                    content = "".join(part.get("text", "") for part in parts)
                    model = self.gemini_model
                if content:
                    return {"content": content, "provider": provider, "model": model, "token_count": tokens}
            except Exception:
                # Provider exception messages can contain keys, URLs, or request data.
                continue
        return {"content": None, "provider": "fallback", "model": "rule-based",
                "token_count": tokens, "error": "No permitted provider returned a response"}


def get_router(config: Optional[dict] = None) -> LLMRouter:
    """Create a new router; never cache credentials or mutate another user's state."""
    config = config or {}
    server_cloud = os.getenv("ALLOW_CLOUD_LLM", "false").lower() == "true"
    return LLMRouter(
        openai_api_key=config.get("openai_api_key") or os.getenv("OPENAI_API_KEY", ""),
        gemini_api_key=config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", ""),
        # Only the operator configures network destinations; clients cannot override them.
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=config.get("ollama_model") or os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        gemini_model=os.getenv("GEMINI_MODEL", ""),
        token_threshold=int(os.getenv("TOKEN_THRESHOLD", "1500")),
        strategy=config.get("strategy") or os.getenv("LLM_STRATEGY", "offline"),
        allow_cloud=server_cloud and config.get("allow_cloud") is True,
    )
