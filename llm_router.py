"""
llm_router.py -- Intelligent LLM Routing System

This module manages routing between multiple LLM providers (OpenAI, Gemini, & Ollama)
with automatic smart switching based on query complexity (token count).

Features:
  1. LLMRouter class that manages OpenAI, Gemini and Ollama connections
  2. Token counter using tiktoken to measure query size
  3. Auto-routing: tokens > threshold -> Gemini/OpenAI; else -> Ollama
  4. Manual override to force a specific provider
  5. Connection health checks for all providers
"""

import os
import requests as http_requests  # Renamed to avoid clash with FastAPI
from typing import Optional, Generator
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Token counting -- tiktoken with graceful fallback
# ---------------------------------------------------------------------------

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    print("[INFO] tiktoken not installed -- using word-based token estimation")


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Count tokens in a text string.
    Uses tiktoken for accurate counts when available.
    Falls back to a word-based heuristic (words * 1.3) otherwise.
    """
    if _TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
    else:
        return int(len(text.split()) * 1.3)


# ============================================================================
# LLMRouter -- Main routing class
# ============================================================================

class LLMRouter:
    """
    Intelligent router that selects between Gemini, OpenAI and Ollama based on
    query complexity, user preference, and provider availability.
    """

    def __init__(
        self,
        openai_api_key: str = "",
        gemini_api_key: str = "",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.2:3b",
        openai_model: str = "gpt-4o-mini",
        gemini_model: str = "gemini-1.5-flash",
        token_threshold: int = 1500,
        strategy: str = "auto",
    ):
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self.token_threshold = token_threshold
        self.strategy = strategy  # "auto" | "always_ollama" | "always_openai" | "always_gemini"

        # OpenAI client (lazy-initialized)
        self._openai_client = None
        self._init_openai()
        
        # Gemini setup
        self._gemini_configured = False
        self._init_gemini()

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _init_openai(self):
        self._openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except ImportError:
                print("[WARN] openai package not installed")
            except Exception as e:
                print(f"[WARN] OpenAI init failed: {e}")
                
    def _init_gemini(self):
        self._gemini_configured = False
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self._gemini_configured = True
            except ImportError:
                print("[WARN] google-generativeai package not installed")
            except Exception as e:
                print(f"[WARN] Gemini init failed: {e}")

    def update_config(
        self,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        openai_model: Optional[str] = None,
        gemini_model: Optional[str] = None,
        token_threshold: Optional[int] = None,
        strategy: Optional[str] = None,
    ):
        openai_changed = False
        gemini_changed = False
        
        if openai_api_key is not None and openai_api_key != self.openai_api_key:
            self.openai_api_key = openai_api_key
            openai_changed = True
            
        if gemini_api_key is not None and gemini_api_key != self.gemini_api_key:
            self.gemini_api_key = gemini_api_key
            gemini_changed = True
            
        if ollama_url is not None:
            self.ollama_url = ollama_url.rstrip("/")
        if ollama_model is not None:
            self.ollama_model = ollama_model
        if openai_model is not None:
            self.openai_model = openai_model
        if gemini_model is not None:
            self.gemini_model = gemini_model
        if token_threshold is not None:
            self.token_threshold = token_threshold
        if strategy is not None:
            self.strategy = strategy
            
        if openai_changed:
            self._init_openai()
        if gemini_changed:
            self._init_gemini()

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def check_ollama(self) -> bool:
        try:
            resp = http_requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def check_openai(self) -> bool:
        if not self._openai_client:
            return False
        try:
            self._openai_client.models.list()
            return True
        except Exception:
            return bool(self.openai_api_key)

    def check_gemini(self) -> bool:
        return self._gemini_configured

    def get_status(self) -> dict:
        return {
            "ollama_ready": self.check_ollama(),
            "openai_ready": bool(self._openai_client),
            "gemini_ready": self.check_gemini(),
            "strategy": self.strategy,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "openai_model": self.openai_model,
            "gemini_model": self.gemini_model,
            "token_threshold": self.token_threshold,
        }

    # ------------------------------------------------------------------
    # Routing decision
    # ------------------------------------------------------------------

    def decide_provider(self, prompt: str) -> tuple[str, int]:
        token_count = count_tokens(prompt)
        ollama_ok = self.check_ollama()
        openai_ok = bool(self._openai_client)
        gemini_ok = self.check_gemini()

        if self.strategy == "always_gemini":
            if gemini_ok: return ("gemini", token_count)
            elif openai_ok: return ("openai", token_count)
            elif ollama_ok: return ("ollama", token_count)
            return ("fallback", token_count)

        if self.strategy == "always_openai":
            if openai_ok: return ("openai", token_count)
            elif gemini_ok: return ("gemini", token_count)
            elif ollama_ok: return ("ollama", token_count)
            return ("fallback", token_count)

        if self.strategy == "always_ollama":
            if ollama_ok: return ("ollama", token_count)
            elif gemini_ok: return ("gemini", token_count)
            elif openai_ok: return ("openai", token_count)
            return ("fallback", token_count)

        # --- Auto (smart routing) ---
        if token_count > self.token_threshold:
            # Complex query -> prefer Gemini -> OpenAI -> Ollama
            if gemini_ok: return ("gemini", token_count)
            if openai_ok: return ("openai", token_count)
            if ollama_ok: return ("ollama", token_count)
            return ("fallback", token_count)
        else:
            # Simple query -> prefer Ollama -> Gemini -> OpenAI
            if ollama_ok: return ("ollama", token_count)
            if gemini_ok: return ("gemini", token_count)
            if openai_ok: return ("openai", token_count)
            return ("fallback", token_count)

    # ------------------------------------------------------------------
    # Chat completion -- unified interface
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 800) -> dict:
        full_prompt = "\n".join(m.get("content", "") for m in messages)
        provider, token_count = self.decide_provider(full_prompt)

        if provider == "gemini":
            return self._chat_gemini(messages, temperature, max_tokens, token_count)
        elif provider == "openai":
            return self._chat_openai(messages, temperature, max_tokens, token_count)
        elif provider == "ollama":
            return self._chat_ollama(messages, temperature, max_tokens, token_count)
        else:
            return {
                "content": None,
                "provider": "fallback",
                "model": "rule-based",
                "token_count": token_count,
                "error": "No LLM provider available",
            }

    # ------------------------------------------------------------------
    # Gemini implementation
    # ------------------------------------------------------------------
    
    def _chat_gemini(self, messages: list[dict], temperature: float, max_tokens: int, token_count: int) -> dict:
        try:
            import google.generativeai as genai
            
            # Convert messages format to Gemini format
            gemini_messages = []
            system_instruction = None
            
            for m in messages:
                role = m.get("role")
                if role == "system":
                    system_instruction = m.get("content")
                else:
                    gemini_role = "user" if role == "user" else "model"
                    gemini_messages.append({"role": gemini_role, "parts": [m.get("content", "")]})
                    
            model = genai.GenerativeModel(
                model_name=self.gemini_model,
                system_instruction=system_instruction
            )
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            response = model.generate_content(
                gemini_messages,
                generation_config=generation_config
            )
            
            return {
                "content": response.text,
                "provider": "gemini",
                "model": self.gemini_model,
                "token_count": token_count,
            }
        except Exception as e:
            if self._openai_client:
                result = self._chat_openai(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"Gemini failed: {e}"
                return result
            elif self.check_ollama():
                result = self._chat_ollama(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"Gemini failed: {e}"
                return result
            return {
                "content": None,
                "provider": "fallback",
                "model": "rule-based",
                "token_count": token_count,
                "error": f"Gemini failed: {e}",
            }

    # ------------------------------------------------------------------
    # OpenAI implementation
    # ------------------------------------------------------------------

    def _chat_openai(self, messages: list[dict], temperature: float, max_tokens: int, token_count: int) -> dict:
        try:
            response = self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "content": response.choices[0].message.content,
                "provider": "openai",
                "model": self.openai_model,
                "token_count": token_count,
            }
        except Exception as e:
            if self.check_gemini():
                result = self._chat_gemini(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"OpenAI failed: {e}"
                return result
            elif self.check_ollama():
                result = self._chat_ollama(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"OpenAI failed: {e}"
                return result
            return {
                "content": None,
                "provider": "fallback",
                "model": "rule-based",
                "token_count": token_count,
                "error": f"OpenAI failed: {e}",
            }

    # ------------------------------------------------------------------
    # Ollama implementation
    # ------------------------------------------------------------------

    def _chat_ollama(self, messages: list[dict], temperature: float, max_tokens: int, token_count: int) -> dict:
        try:
            response = http_requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")

            return {
                "content": content,
                "provider": "ollama",
                "model": self.ollama_model,
                "token_count": token_count,
            }
        except Exception as e:
            if self.check_gemini():
                result = self._chat_gemini(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"Ollama failed: {e}"
                return result
            elif self._openai_client:
                result = self._chat_openai(messages, temperature, max_tokens, token_count)
                result["fallback_reason"] = f"Ollama failed: {e}"
                return result
            return {
                "content": None,
                "provider": "fallback",
                "model": "rule-based",
                "token_count": token_count,
                "error": f"Ollama failed: {e}",
            }

# ============================================================================
# Module-level default instance (used by logic.py)
# ============================================================================

_default_router = LLMRouter(
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
    ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
    ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    token_threshold=int(os.getenv("TOKEN_THRESHOLD", "1500")),
    strategy=os.getenv("LLM_STRATEGY", "auto"),
)

def get_router() -> LLMRouter:
    return _default_router
