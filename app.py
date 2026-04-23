"""
app.py -- Streamlit Frontend for AI College Data Assistant
"""

import streamlit as st
import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# FastAPI backend URL
BACKEND_URL = "http://localhost:8000"
TIMEOUT = 30  # Increased from 3 to 30 seconds

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
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return resp.status_code == 200
    except:
        return False

def get_llm_status_safe():
    """Get LLM status with proper error handling."""
    try:
        resp = requests.get(f"{BACKEND_URL}/llm-status", timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"Backend returned {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Backend not running. Start with: uvicorn main:app --reload"}
    except requests.exceptions.ReadTimeout:
        return {"error": "Backend is slow. LLM might be initializing..."}
    except Exception as e:
        return {"error": str(e)}

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
        uvicorn main:app --reload --host 0.0.0.0 --port 8000
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
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = ""
if "ollama_url" not in st.session_state:
    st.session_state.ollama_url = "http://localhost:11434"
if "ollama_model" not in st.session_state:
    st.session_state.ollama_model = "llama3.2:3b"
if "llm_strategy" not in st.session_state:
    st.session_state.llm_strategy = "auto"


# ---------------------------------------------------------------------------
# Helper: Build LLM config dict from session state
# ---------------------------------------------------------------------------

def get_llm_config() -> dict:
    """Build llm_config dict to send with each query to the backend."""
    strategy_map = {
        "Auto (smart routing)": "auto",
        "Always Ollama": "always_ollama",
        "Always OpenAI": "always_openai",
        "Always Gemini": "always_gemini",
    }
    return {
        "openai_api_key": st.session_state.openai_api_key or None,
        "gemini_api_key": st.session_state.gemini_api_key or None,
        "ollama_url": st.session_state.ollama_url,
        "ollama_model": st.session_state.ollama_model,
        "strategy": strategy_map.get(st.session_state.llm_strategy, "auto"),
    }


# ---------------------------------------------------------------------------
# Helper: Render model info badges
# ---------------------------------------------------------------------------

def render_model_badge(model_info: dict):
    """Render provider badge + token count inline."""
    if not model_info:
        return

    provider = model_info.get("provider", "unknown")
    model = model_info.get("model", "unknown")
    token_count = model_info.get("token_count", 0)

    # Choose badge style based on provider
    if provider == "ollama":
        badge_html = f'<span class="model-badge model-ollama">&#9889; via Ollama ({model})</span>'
    elif provider == "openai":
        badge_html = f'<span class="model-badge model-openai">&#129302; via OpenAI {model}</span>'
    elif provider == "gemini":
        badge_html = f'<span class="model-badge" style="background:#e8f0fe; color:#1967d2;">&#10024; via Gemini {model}</span>'
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
        "Select Your Role",
        options=["student", "teacher", "admin"],
        index=["student", "teacher", "admin"].index(st.session_state.role),
        help="Your role affects how the system interprets and responds to queries."
    )
    st.session_state.role = role

    st.divider()

    # ---------------------------------------------------------------
    # LLM Configuration (expandable)
    # ---------------------------------------------------------------
    with st.expander("🤖 LLM Configuration", expanded=False):
        st.caption("Configure how the AI backend processes analytical queries.")

        # OpenAI API Key
        openai_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.openai_api_key,
            type="password",
            placeholder="sk-...",
            help="Optional. Get from https://platform.openai.com/api-keys",
        )
        st.session_state.openai_api_key = openai_key

        # Gemini API Key
        gemini_key = st.text_input(
            "Gemini API Key",
            value=st.session_state.gemini_api_key,
            type="password",
            placeholder="AIzaSy...",
            help="Optional. Get from Google AI Studio",
        )
        st.session_state.gemini_api_key = gemini_key

        # Ollama URL
        ollama_url = st.text_input(
            "Ollama URL",
            value=st.session_state.ollama_url,
            placeholder="http://localhost:11434",
            help="Base URL of your local Ollama server.",
        )
        st.session_state.ollama_url = ollama_url

        # Ollama Model
        ollama_model = st.text_input(
            "Ollama Model",
            value=st.session_state.ollama_model,
            placeholder="llama3.2:3b",
            help="Model name to use with Ollama.",
        )
        st.session_state.ollama_model = ollama_model

        # Routing Strategy
        strategy_options = ["Auto (smart routing)", "Always Ollama", "Always OpenAI", "Always Gemini"]
        strategy = st.radio(
            "Routing Strategy",
            options=strategy_options,
            index=strategy_options.index(st.session_state.llm_strategy) if st.session_state.llm_strategy in strategy_options else 0,
            help="Auto: queries >1500 tokens go to Gemini/OpenAI, smaller ones to Ollama.",
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
            col1, col2, col3 = st.columns(3)
            with col1:
                if status.get("gemini") or status.get("gemini_ready"):
                    st.success("🟢 Gemini")
                elif st.session_state.gemini_api_key:
                    st.warning("🟡 Key Set")
                else:
                    st.error("🔴 Gemini")
            with col2:
                if status.get("openai") or status.get("openai_ready"):
                    st.success("🟢 OpenAI")
                elif st.session_state.openai_api_key:
                    st.warning("🟡 Key Set")
                else:
                    st.error("🔴 OpenAI")
            with col3:
                # Handle both old and new schema
                if status.get("ollama") or status.get("ollama_ready"):
                    st.success("🟢 Ollama")
                else:
                    st.error("🔴 Ollama")
            
            # Active strategy
            st.caption(f"Strategy: {status.get('strategy', 'auto')} | Threshold: {status.get('token_threshold', 1500)} tokens")

        # Tooltip about auto-routing
        st.info(
            "**Auto-routing:** Queries >1500 tokens automatically use OpenAI "
            "for better accuracy. Smaller queries use Ollama for speed & privacy."
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
        if st.button(f"{eq}", key=f"ex_{eq}", use_container_width=True):
            st.session_state.pending_query = eq
            st.rerun()

    st.divider()

    # Session memory display
    st.markdown("## Session Memory")
    try:
        mem_response = requests.get(f"{BACKEND_URL}/session-memory", timeout=TIMEOUT)
        if mem_response.status_code == 200:
            mem_data = mem_response.json()
            st.markdown(f"**Role:** {mem_data['role']}")
            if mem_data["memory"]:
                for i, m in enumerate(mem_data["memory"], 1):
                    with st.expander(f"Q{i}: {m['query'][:50]}..."):
                        st.write(m["response"][:200])
            else:
                st.caption("No queries yet in this session.")
        else:
            st.caption("Session memory unavailable.")
    except Exception:
        st.caption("Backend not connected.")

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
    <p>Ask questions about student data, performance analytics, or college policies using natural language.</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chat History Display
# ---------------------------------------------------------------------------

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

            # Query type badge
            badge_class = f"badge-{extra.get('query_type', 'data')}"
            st.markdown(
                f'<span class="query-badge {badge_class}">{extra.get("query_type", "unknown")}</span>',
                unsafe_allow_html=True
            )

            # Model info badge
            render_model_badge(extra.get("model_info"))

            # Explanation (collapsible)
            with st.expander("Why this result?", expanded=False):
                st.info(extra.get("explanation", "No explanation available."))

            # Data table
            if extra.get("data") and len(extra["data"]) > 0:
                with st.expander("View Data Table", expanded=False):
                    df = pd.DataFrame(extra["data"])
                    st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Query Input & Processing
# ---------------------------------------------------------------------------

def send_query(query: str):
    """Send a query to the backend and update the chat."""
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
                    },
                    timeout=TIMEOUT
                )

                if resp.status_code == 200:
                    response_data = resp.json()
                else:
                    response_data = {
                        "answer": f"Error: Backend returned {resp.status_code}",
                        "error": True,
                        "error_details": resp.text
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
            except Exception as e:
                response_data = {
                    "answer": f"❌ Unexpected error: {str(e)}",
                    "error": True,
                    "error_details": str(e)
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
            
            # Query type badge
            badge_class = f"badge-{response_data.get('query_type', 'data')}"
            st.markdown(
                f'<span class="query-badge {badge_class}">{response_data.get("query_type", "unknown")}</span>',
                unsafe_allow_html=True
            )

            # Model info badge
            model_info = response_data.get("model_info")
            render_model_badge(model_info)

            # Explanation
            with st.expander("Why this result?", expanded=False):
                st.info(response_data.get("explanation", "No explanation available."))

            # Data table
            if response_data.get("data") and len(response_data["data"]) > 0:
                with st.expander("View Data Table", expanded=False):
                    df = pd.DataFrame(response_data["data"])
                    st.dataframe(df, use_container_width=True, hide_index=True)

            # Save to session state
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_data["answer"],
                "extra": {
                    "explanation": response_data.get("explanation", ""),
                    "query_type": response_data.get("query_type", "unknown"),
                    "data": response_data.get("data", []),
                    "model_info": model_info,
                }
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
