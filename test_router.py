"""
test_router.py -- Test script for the LLM Router

Demonstrates:
  1. Small query -> Ollama (or fallback if Ollama is offline)
  2. Large query -> OpenAI auto-switch (or fallback if OpenAI not configured)
  3. Health checks for both providers
  4. Token counting accuracy

Run:  python test_router.py
"""

from llm_router import LLMRouter, count_tokens

def main():
    print("=" * 60)
    print("  LLM Router Test Script")
    print("=" * 60)

    # Create a router with auto strategy and a low threshold for testing
    router = LLMRouter(
        openai_api_key="",       # Empty = not configured
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2:3b",
        token_threshold=50,      # Low threshold for easy testing
        strategy="auto",
    )

    # ---- Health checks ----
    print("\n--- Provider Health Checks ---")
    ollama_ok = router.check_ollama()
    openai_ok = router.check_openai()
    print(f"  Ollama ({router.ollama_url}): {'READY' if ollama_ok else 'OFFLINE'}")
    print(f"  OpenAI: {'READY' if openai_ok else 'NOT CONFIGURED'}")
    print(f"  Strategy: {router.strategy}")
    print(f"  Token threshold: {router.token_threshold}")

    # ---- Token counting demo ----
    print("\n--- Token Counting ---")
    small_text = "Show me students with low attendance"
    large_text = "Analyze the complete academic performance of all students " * 30

    small_count = count_tokens(small_text)
    large_count = count_tokens(large_text)
    print(f"  Small query: '{small_text[:50]}...'")
    print(f"    -> {small_count} tokens")
    print(f"  Large query: ({len(large_text)} chars)")
    print(f"    -> {large_count} tokens")

    # ---- Routing decisions ----
    print("\n--- Routing Decisions ---")

    provider_small, tokens_small = router.decide_provider(small_text)
    print(f"  Small query ({tokens_small} tokens) -> {provider_small.upper()}")

    provider_large, tokens_large = router.decide_provider(large_text)
    print(f"  Large query ({tokens_large} tokens) -> {provider_large.upper()}")

    # ---- Actual chat calls (if any provider is available) ----
    print("\n--- Chat Test ---")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2? Answer in one word."},
    ]

    result = router.chat(messages, temperature=0.1, max_tokens=50)
    if result["content"]:
        print(f"  Provider: {result['provider'].upper()} ({result['model']})")
        print(f"  Tokens: {result['token_count']}")
        print(f"  Response: {result['content']}")
    else:
        print(f"  Provider: {result['provider'].upper()}")
        print(f"  No LLM available: {result.get('error', 'unknown')}")
        print("  (This is expected if neither Ollama nor OpenAI is configured)")

    # ---- Strategy override test ----
    print("\n--- Strategy Override Test ---")
    for strat in ["always_ollama", "always_openai", "auto"]:
        router.update_config(strategy=strat)
        provider, tokens = router.decide_provider(small_text)
        print(f"  Strategy '{strat}' + small query -> {provider.upper()}")

    print("\n" + "=" * 60)
    print("  Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
