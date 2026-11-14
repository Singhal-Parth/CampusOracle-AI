"""Manual, credential-free router diagnostic. Regression tests live in tests/.

Run python test_router.py for offline checks. Use --ollama to probe only the
operator's OLLAMA_URL (default localhost:11434). This script never loads keys
from the environment into its router and cannot contact cloud providers.
"""
import argparse
import os
from llm_router import LLMRouter, count_tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama", action="store_true", help="Probe the configured Ollama server")
    args = parser.parse_args()
    router = LLMRouter(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        strategy="always_ollama" if args.ollama else "offline",
    )
    prompt = "What is 2+2? Answer in one word."
    print("Mode:", router.strategy)
    print("Estimated prompt tokens:", count_tokens(prompt))
    print("Selected provider:", router.decide_provider(prompt)[0])
    result = router.chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=50)
    print("Result provider:", result["provider"])
    print("Response:", result["content"] or "No LLM response; rule-based fallback is available in the app.")


if __name__ == "__main__":
    main()
