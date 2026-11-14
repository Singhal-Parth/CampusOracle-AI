"""
app.py -- Streamlit Frontend for AI College Data Assistant
"""

import os
from html import escape

from dotenv import load_dotenv
import streamlit as st
import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# FastAPI backend URL
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("CAMPUS_API_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
TIMEOUT = 75  # At most three sequential provider attempts, each with a bounded timeout

# Page config
st.set_page_config(
    page_title="AI College Data Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_backend_health():
    """Check if backend is reachable."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", headers=HEADERS, timeout=5, allow_redirects=False)
        return resp.status_code == 200
    except:
        return False

def get_llm_status_safe():
    """Get LLM status with proper error handling."""
    try:
        resp = requests.get(f"{BACKEND_URL}/llm-status", headers=HEADERS, timeout=5, allow_redirects=False)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"Backend returned {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Backend not running. Start with: uvicorn main:app --reload"}
    except requests.exceptions.ReadTimeout:
        return {"error": "Backend is slow. LLM might be initializing..."}
    except (requests.RequestException, ValueError):
        return {"error": "Unable to read provider status."}

# ---------------------------------------------------------------------------
# Startup Check
# ---------------------------------------------------------------------------
# Check backend connection FIRST
with st.spinner("Connecting to backend..."):
    if not check_backend_health():
        st.error("""
        ⚠️ **Backend server is not running!**
        
        Please start the FastAPI backend:
        
        ```bash
        uvicorn main:app --host 127.0.0.1 --port 8000
        ```
        
        Then refresh this page.
        """)
        st.stop()  # Stop Streamlit execution

# ---------------------------------------------------------------------------
# Custom CSS for a polished chat interface
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 900px;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }

    /* Query type badges */
    .query-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 6px;
    }
    .badge-data {
        background: #e3f2fd;
        color: #1565c0;
    }
    .badge-analytical {
        background: #f3e5f5;
        color: #7b1fa2;
    }
    .badge-knowledge {
        background: #e8f5e9;
        color: #2e7d32;
    }

    /* Model badge styles */
    .model-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        margin-right: 6px;
    }
    .model-ollama {
        background: #fff3e0;
        color: #e65100;
    }
    .model-openai {
        background: #e8eaf6;
        color: #283593;
    }
    .model-fallback {
        background: #fce4ec;
        color: #c62828;
    }
    .model-database {
        background: #e0f2f1;
        color: #00695c;
    }

    /* Token count display */
    .token-info {
        display: inline-block;
        font-size: 0.7rem;
        color: #888;
        margin-left: 4px;
    }

    /* Sidebar styling */
    .sidebar-info {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 3px solid #667eea;
        margin-top: 1rem;
        font-size: 0.85rem;
    }

    /* Status indicators */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .status-green { background: #4caf50; }
    .status-red { background: #f44336; }
    .status-yellow { background: #ff9800; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "role" not in st.session_state:
    st.session_state.role = "student"

# LLM configuration defaults
if "ollama_model" not in st.session_state:
    st.session_state.ollama_model = "llama3.2:3b"
if "llm_strategy" not in st.session_state:
    st.session_state.llm_strategy = "Offline (no provider calls)"


# ---------------------------------------------------------------------------
# Helper: Build LLM config dict from session state
# ---------------------------------------------------------------------------

def get_llm_config() -> dict:
    """Build llm_config dict to send with each query to the backend."""
    strategy_map = {
        "Offline (no provider calls)": "offline",
        "Auto (smart routing)": "auto",
        "Always Ollama": "always_ollama",
        "Always OpenAI": "always_openai",
        "Always Gemini": "always_gemini",
    }
    return {
        "ollama_model": st.session_state.ollama_model,
        "strategy": strategy_map.get(st.session_state.llm_strategy, "offline"),
        "allow_cloud": st.session_state.get("allow_cloud", False),
    }


# ---------------------------------------------------------------------------
# Helper: Render model info badges
# ---------------------------------------------------------------------------

def render_model_badge(model_info: dict):
    """Render provider badge + token count inline."""
    if not model_info:
        return

    provider = model_info.get("provider", "unknown")
    model = escape(str(model_info.get("model", "unknown")))
    token_count = model_info.get("token_count", 0)

    # Choose badge style based on provider
    if provider == "ollama":
        badge_html = f'<span class="model-badge model-ollama">&#9889; via Ollama ({model})</span>'
    elif provider == "openai":
        badge_html = f'<span class="model-badge model-openai">&#129302; via OpenAI {model}</span>'
    elif provider == "gemini":
        badge_html = f'<span class="model-badge" style="background:#e8f0fe; color:#1967d2;">&#10024; via Gemini {model}</span>'
    elif model == "SQLite FTS5":
        badge_html = '<span class="model-badge model-database">Sample document search</span>'
    elif provider == "database":
        badge_html = f'<span class="model-badge model-database">&#128451; Direct SQL Query</span>'
    else:
        badge_html = f'<span class="model-badge model-fallback">&#9881; Rule-based Fallback</span>'

    # Token count (show only for LLM providers)
    token_html = ""
    if provider in ("openai", "ollama", "gemini") and token_count > 0:
        token_html = f'<span class="token-info">&#128202; {token_count:,} tokens</span>'

    st.markdown(badge_html + token_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Settings")

    # Role selector
    role = st.selectbox(
        "Response style (demo)",
        options=["student", "teacher", "admin"],
        index=["student", "teacher", "admin"].index(st.session_state.role),
        help="Demo response context only. This does not authenticate users or restrict data access."
    )
    st.session_state.role = role

    st.divider()

    # ---------------------------------------------------------------
    # LLM Configuration (expandable)
    # ---------------------------------------------------------------
    with st.expander("🤖 LLM Configuration", expanded=False):
        st.caption("Configure how the AI backend processes analytical queries.")

        st.caption("Provider keys and Ollama's address are configured on the backend.")

        st.checkbox(
            "Allow cloud processing for this session", key="allow_cloud", value=False,
            help="Permits sending your query, recent chat, and sample records to OpenAI/Gemini. "
                 "The backend operator must also enable ALLOW_CLOUD_LLM.",
        )

        # Ollama Model
        ollama_model = st.text_input(
            "Ollama Model",
            value=st.session_state.ollama_model,
            placeholder="llama3.2:3b",
            help="Model name to use with Ollama.",
        )
        st.session_state.ollama_model = ollama_model

        # Routing Strategy
        strategy_options = ["Offline (no provider calls)", "Auto (smart routing)", "Always Ollama", "Always OpenAI", "Always Gemini"]
        strategy = st.radio(
            "Routing Strategy",
            options=strategy_options,
            index=strategy_options.index(st.session_state.llm_strategy) if st.session_state.llm_strategy in strategy_options else 0,
            help="Offline makes no provider calls. Always Ollama stays local. Auto may use cloud only with consent.",
        )
        st.session_state.llm_strategy = strategy

        # --- Live status indicators ---
        st.markdown("---")
        st.markdown("**Provider Status:**")

        if st.button("🔄 Refresh Status"):
            st.rerun()
        
        status = get_llm_status_safe()
        
        if "error" in status:
            st.error(status["error"])
        else:
            st.caption("Cloud enabled by operator: " +
                       ("yes" if status.get("cloud_enabled_by_operator") else "no"))
            for label, field in (("OpenAI", "openai_configured"), ("Gemini", "gemini_configured")):
                configured = "configured" if status.get(field) else "unconfigured"
                st.caption(f"{label}: {configured}")

        st.info(
            "Offline uses deterministic rules. Always Ollama stays local. "
            "Auto prefers Ollama for smaller prompts and Gemini/OpenAI for larger ones, "
            "but cloud calls require both your consent and backend permission. "
            "Token counts are estimates."
        )

    st.divider()

    # Example queries section
    st.markdown("## Example Queries")
    st.markdown("Click to try:")

    example_queries = [
        "Show students with attendance below 60%",
        "Identify weak students and suggest improvements",
        "Analyze performance of CSE 3rd year students",
        "What is the minimum attendance policy?",
        "List all students in ECE branch",
        "Who are the top performers?",
    ]

    for eq in example_queries:
        if st.button(f"{eq}", key=f"ex_{eq}", width="stretch"):
            st.session_state.pending_query = eq
            st.rerun()

    st.divider()

    # Conversation history belongs to this Streamlit session; no global API memory.
    st.markdown("## Session Memory")
    exchanges = [m for m in st.session_state.messages if m["role"] == "assistant" and not m.get("error")]
    st.caption(f"{min(3, len(exchanges))} recent exchanges available as context in this session.")
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # Backend status
    st.markdown("## Backend Status")
    if not check_backend_health():
        st.error("⚠️ Backend Offline")
        st.info("Run: uvicorn main:app --reload")
    else:
        st.success("Connected")


# ---------------------------------------------------------------------------
# Main Content -- Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h1>AI College Data Assistant</h1>
    <p>Local prototype using synthetic student records and sample policies.</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chat History Display
# ---------------------------------------------------------------------------

def render_answer_details(result: dict):
    query_type = escape(str(result.get("query_type", "unknown")))
    st.markdown(
        f'<span class="query-badge badge-{query_type}">{query_type}</span>',
        unsafe_allow_html=True,
    )
    render_model_badge(result.get("model_info"))
    with st.expander("Why this result?"):
        st.info(result.get("explanation", "No explanation available."))
    if result.get("sources"):
        with st.expander("Sources from sample documents"):
            for source in result["sources"]:
                st.text(
                    f"[{source['number']}] {source['section']} · {source['document']} "
                    f"· lines {source['start_line']}–{source['end_line']}"
                )
                st.text(source["excerpt"])
    if result.get("data"):
        with st.expander("View Data Table"):
            st.dataframe(pd.DataFrame(result["data"]), width="stretch", hide_index=True)


for message in st.session_state.messages:
    if message.get("error"):
        with st.chat_message("assistant"):
            st.error(message["content"])
        continue

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Show additional details for assistant messages
        if message["role"] == "assistant" and "extra" in message:
            extra = message["extra"]

            render_answer_details(extra)

# ---------------------------------------------------------------------------
# Query Input & Processing
# ---------------------------------------------------------------------------

def send_query(query: str):
    """Send a query to the backend and update the chat."""
    # Send only this session's last three completed exchanges.
    history = []
    previous_query = None
    for message in st.session_state.messages:
        if message["role"] == "user":
            previous_query = message["content"]
        elif previous_query is not None and not message.get("error"):
            history.append({"query": previous_query, "response": message["content"][:2000]})
            previous_query = None
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": query})

    # Show user message
    with st.chat_message("user"):
        st.markdown(query)

    # Call the backend API
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/query",
                    json={
                        "query": query,
                        "role": st.session_state.role,
                        "llm_config": get_llm_config(),
                        "history": history[-3:],
                    },
                    headers=HEADERS,
                    timeout=TIMEOUT,
                    allow_redirects=False,
                )

                if resp.status_code == 200:
                    response_data = resp.json()
                else:
                    response_data = {
                        "answer": f"Error: Backend returned {resp.status_code}",
                        "error": True,
                        "error_details": f"HTTP {resp.status_code}"
                    }
            except requests.exceptions.ConnectionError:
                response_data = {
                    "answer": "❌ Cannot connect to backend. Make sure FastAPI is running on port 8000.",
                    "error": True,
                    "error_details": "ConnectionError"
                }
            except requests.exceptions.ReadTimeout:
                response_data = {
                    "answer": "⏱️ Query timed out. Backend might be processing a complex request.",
                    "error": True,
                    "error_details": "ReadTimeout"
                }
            except (requests.RequestException, ValueError):
                response_data = {
                    "answer": "Unable to read the backend response.",
                    "error": True,
                    "error_details": "Backend response unavailable",
                }
        
        if response_data.get("error"):
            st.error(response_data["answer"])
            
            # Show helpful debug info
            with st.expander("🔍 Debug Info"):
                st.code(f"""
Backend URL: {BACKEND_URL}
Error: {response_data.get('error_details', 'Unknown')}

Troubleshooting:
1. Check if backend is running: python check_backend.py
2. Start backend: uvicorn main:app --reload
3. Check backend logs for errors
                """)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_data["answer"],
                "error": True
            })
        else:
            st.markdown(response_data["answer"])
            
            render_answer_details(response_data)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_data["answer"],
                "extra": response_data,
            })


# Handle pending query from example buttons
if "pending_query" in st.session_state:
    pending = st.session_state.pending_query
    del st.session_state.pending_query
    send_query(pending)

# Chat input
user_input = st.chat_input("Ask about students, attendance, marks, policies...")

if user_input:
    send_query(user_input)
