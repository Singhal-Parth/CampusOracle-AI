"""
logic.py -- Context Engine + Decision Engine + LLM Integration

This module is the brain of the AI College Data Assistant. It contains:
  1. Context Engine  -- manages user role & session memory (last 3 queries)
  2. Decision Engine  -- classifies queries and routes to the right handler
  3. LLM Integration  -- Routes through LLMRouter (OpenAI / Ollama / fallback)
  4. RAG Simulation   -- keyword-based document retrieval from static files

Flow: User Query -> Context Engine -> Decision Engine -> Response
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv

import db  # Our database module
from llm_router import get_router, LLMRouter  # Intelligent LLM routing

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# LLM Router (replaces direct OpenAI client)
# ---------------------------------------------------------------------------
# The router manages OpenAI + Ollama connections, token counting,
# and automatic provider selection.  See llm_router.py for details.

llm_router: LLMRouter = get_router()


# ═══════════════════════════════════════════════════════════════════════════
# 1. CONTEXT ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class ContextEngine:
    """
    Manages session context for each user interaction.

    Responsibilities:
      - Track user role (student / teacher / admin)
      - Maintain a sliding window of the last 3 queries (session memory)
      - Enrich queries with contextual information
    """

    def __init__(self):
        self.user_role: str = "student"        # Default role
        self.session_memory: list[dict] = []   # Last 3 query-response pairs

    def set_role(self, role: str):
        """Set the current user role."""
        self.user_role = role.lower().strip()

    def add_to_memory(self, query: str, response: str):
        """
        Add a query-response pair to session memory.
        Keeps only the last 3 entries (sliding window).
        """
        self.session_memory.append({
            "query": query,
            "response": response[:200]  # Truncate long responses for memory
        })
        # Keep only last 3 entries
        if len(self.session_memory) > 3:
            self.session_memory = self.session_memory[-3:]

    def get_context_summary(self) -> str:
        """Build a context string for LLM prompts."""
        context_parts = [f"User Role: {self.user_role}"]

        if self.session_memory:
            context_parts.append("Recent conversation history:")
            for i, mem in enumerate(self.session_memory, 1):
                context_parts.append(f"  Q{i}: {mem['query']}")
                context_parts.append(f"  A{i}: {mem['response']}")

        return "\n".join(context_parts)

    def get_memory_display(self) -> list[dict]:
        """Return session memory for UI display."""
        return self.session_memory.copy()


# Global context engine instance (shared across requests in a session)
context_engine = ContextEngine()


# ═══════════════════════════════════════════════════════════════════════════
# 2. DECISION ENGINE — Query Classification
# ═══════════════════════════════════════════════════════════════════════════

# Keywords that signal each query type
DATA_KEYWORDS = [
    "show", "list", "display", "attendance below", "attendance above",
    "marks of", "score", "students in", "all students", "how many",
    "count", "percentage", "who has", "fetch", "get"
]

ANALYTICAL_KEYWORDS = [
    "analyze", "analyse", "analysis", "suggest", "improve", "improvement",
    "identify weak", "weak students", "performance", "trend", "compare",
    "top performer", "best student", "worst", "bottom", "predict",
    "insight", "recommend", "evaluation", "assess"
]

KNOWLEDGE_KEYWORDS = [
    "policy", "policies", "rule", "rules", "guideline", "guidelines",
    "eligibility", "criteria", "requirement", "minimum attendance",
    "grading", "grade scale", "remedial", "mentorship", "fee",
    "library", "disciplinary", "scholarship", "improvement exam"
]


def classify_query(query: str) -> str:
    """
    Classify a user query into one of three categories:
      - 'data'       → Direct database query (SQL)
      - 'analytical'  → Needs LLM/rule-based analysis
      - 'knowledge'   → RAG simulation from static documents

    Classification uses keyword matching with priority:
    analytical > knowledge > data (fallback to data if ambiguous)
    """
    query_lower = query.lower()

    # Check analytical first (higher priority — these need deeper processing)
    if any(kw in query_lower for kw in ANALYTICAL_KEYWORDS):
        return "analytical"

    # Check knowledge queries
    if any(kw in query_lower for kw in KNOWLEDGE_KEYWORDS):
        return "knowledge"

    # Default: treat as data query (most common case)
    if any(kw in query_lower for kw in DATA_KEYWORDS):
        return "data"

    # If no keywords match, route to analytical for LLM to handle
    return "analytical"


# ═══════════════════════════════════════════════════════════════════════════
# 3. QUERY HANDLERS — One per query type
# ═══════════════════════════════════════════════════════════════════════════

def handle_data_query(query: str) -> dict:
    """
    Handle data queries by mapping natural language to SQL queries.
    Returns structured data directly from the database.
    """
    query_lower = query.lower()
    data = []
    explanation = ""

    # --- Attendance queries ---
    if "attendance" in query_lower and ("below" in query_lower or "less" in query_lower or "under" in query_lower):
        # Extract threshold number from query, default to 60
        threshold = _extract_number(query_lower, default=60.0)
        data = db.get_low_attendance(threshold)
        explanation = (
            f"Queried the attendance table for students with attendance < {threshold}%. "
            f"Found {len(data)} student(s) matching this criteria."
        )

    # --- Branch/Year filtering ---
    elif "students in" in query_lower or "branch" in query_lower:
        branch = _extract_branch(query_lower)
        year = _extract_year(query_lower)
        data = db.get_students_by_branch_year(branch=branch, year=year)
        filter_desc = []
        if branch:
            filter_desc.append(f"branch={branch.upper()}")
        if year:
            filter_desc.append(f"year={year}")
        explanation = (
            f"Filtered students by {' and '.join(filter_desc) if filter_desc else 'no filter'}. "
            f"Found {len(data)} student(s)."
        )

    # --- Marks queries ---
    elif "marks" in query_lower or "score" in query_lower:
        branch = _extract_branch(query_lower)
        year = _extract_year(query_lower)
        data = db.get_student_marks(branch=branch, year=year)
        explanation = f"Retrieved marks data. Found {len(data)} record(s)."

    # --- All students ---
    elif "all students" in query_lower or "list" in query_lower:
        data = db.get_all_students_with_details()
        explanation = f"Retrieved all {len(data)} students with attendance and average marks."

    # --- Count queries ---
    elif "how many" in query_lower or "count" in query_lower:
        branch = _extract_branch(query_lower)
        year = _extract_year(query_lower)
        data = db.get_students_by_branch_year(branch=branch, year=year)
        explanation = f"Counted {len(data)} student(s) matching the criteria."

    # --- Fallback: get all data ---
    else:
        data = db.get_all_students_with_details()
        explanation = "Could not determine specific filter. Showing all students."

    # Format answer text
    if data:
        answer = _format_data_as_text(data)
    else:
        answer = "No students found matching your query."

    return {
        "answer": answer,
        "explanation": explanation,
        "query_type": "data",
        "data": data
    }


def handle_analytical_query(query: str) -> dict:
    """
    Handle analytical queries that require deeper insights.
    Routes through LLMRouter; falls back to rule-based analysis if no LLM available.
    """
    query_lower = query.lower()

    # Gather relevant data based on query content
    if "weak" in query_lower:
        data = db.get_weak_students()
        data_context = "Weak students (attendance < 60% or avg marks < 50%)"
    elif "top" in query_lower or "best" in query_lower or "performer" in query_lower:
        data = db.get_top_performers()
        data_context = "Top performing students by average marks"
    elif _extract_branch(query_lower):
        branch = _extract_branch(query_lower)
        year = _extract_year(query_lower)
        data = db.get_all_students_with_details()
        # Filter by branch/year
        if branch:
            data = [d for d in data if d["branch"].upper() == branch.upper()]
        if year:
            data = [d for d in data if d["year"] == year]
        data_context = f"Students in {branch.upper() if branch else 'all'} branch" + (f" year {year}" if year else "")
    else:
        data = db.get_all_students_with_details()
        data_context = "All students data"

    # Route through LLM router -- it decides provider automatically
    return _llm_analysis(query, data, data_context)


def handle_knowledge_query(query: str) -> dict:
    """
    Handle knowledge queries using RAG simulation.
    Searches static documents in knowledge_base/ for relevant passages.
    """
    query_lower = query.lower()

    # Load and search knowledge base documents
    relevant_passages = _search_knowledge_base(query_lower)

    if not relevant_passages:
        return {
            "answer": "I couldn't find specific information about that in our documents.",
            "explanation": "Searched college policies and academic guidelines but found no matching content.",
            "query_type": "knowledge",
            "data": [],
            "model_info": {"provider": "none", "model": "keyword-search", "token_count": 0},
        }

    # Route through LLM router for synthesis
    return _llm_rag_response(query, relevant_passages)


# ═══════════════════════════════════════════════════════════════════════════
# 4. LLM INTEGRATION via LLMRouter + Rule-Based Fallback
# ═══════════════════════════════════════════════════════════════════════════

def _llm_analysis(query: str, data: list, data_context: str) -> dict:
    """
    Send data + query through the LLM router for analytical insights.
    Falls back to rule-based analysis if no LLM provider is available.
    """
    # Build a data summary for the LLM
    data_summary = _format_data_for_llm(data)
    context = context_engine.get_context_summary()

    prompt = f"""You are an AI academic advisor for a college management system.

{context}

Data Context: {data_context}
Student Data:
{data_summary}

User Query: {query}

Please provide:
1. A clear, structured answer to the query
2. Specific insights based on the data
3. Actionable suggestions if relevant
4. Explain which students are flagged and why

Format your response in a readable way with bullet points where appropriate."""

    messages = [
        {"role": "system", "content": "You are a helpful college academic advisor."},
        {"role": "user", "content": prompt},
    ]

    # Route through LLM router
    result = llm_router.chat(messages, temperature=0.7, max_tokens=800)

    # Build model_info metadata for the UI
    model_info = {
        "provider": result["provider"],
        "model": result["model"],
        "token_count": result["token_count"],
    }

    # If the router returned actual content, use it
    if result["content"]:
        return {
            "answer": result["content"],
            "explanation": (
                f"Analysis performed using {result['provider'].upper()} ({result['model']}). "
                f"Analyzed {len(data)} student records. "
                f"Input tokens: {result['token_count']}. "
                f"Context: {data_context}."
            ),
            "query_type": "analytical",
            "data": data,
            "model_info": model_info,
        }

    # Fallback to rule-based engine
    print(f"[WARN] LLM unavailable ({result.get('error', 'unknown')}), using rule-based fallback")
    fb = _rule_based_analysis(query, data, data_context)
    fb["model_info"] = {"provider": "fallback", "model": "rule-based", "token_count": result["token_count"]}
    return fb


def _llm_rag_response(query: str, passages: list[str]) -> dict:
    """
    Use LLM router to synthesize a natural answer from retrieved passages.
    Falls back to returning raw passages if no LLM is available.
    """
    context = context_engine.get_context_summary()
    combined_passages = "\n\n".join(passages)

    prompt = f"""You are an AI assistant for a college management system.

{context}

The following are relevant excerpts from official college documents:

{combined_passages}

User Question: {query}

Please provide a clear, helpful answer based on the above documents.
If the documents don't fully answer the question, say so."""

    messages = [
        {"role": "system", "content": "You are a helpful college information assistant."},
        {"role": "user", "content": prompt},
    ]

    result = llm_router.chat(messages, temperature=0.5, max_tokens=500)

    model_info = {
        "provider": result["provider"],
        "model": result["model"],
        "token_count": result["token_count"],
    }

    if result["content"]:
        return {
            "answer": result["content"],
            "explanation": (
                f"Answer synthesized from official college documents using "
                f"{result['provider'].upper()} ({result['model']}). "
                f"Found {len(passages)} relevant passage(s). "
                f"Input tokens: {result['token_count']}."
            ),
            "query_type": "knowledge",
            "data": [],
            "model_info": model_info,
        }

    # Fallback: return raw passages
    combined = "\n\n".join(passages)
    return {
        "answer": combined,
        "explanation": (
            "No LLM available for synthesis. "
            "Showing matched passages from college documents based on keyword relevance."
        ),
        "query_type": "knowledge",
        "data": [],
        "model_info": {"provider": "fallback", "model": "keyword-search", "token_count": result["token_count"]},
    }


def _rule_based_analysis(query: str, data: list, data_context: str) -> dict:
    """
    Rule-based fallback when OpenAI is not available.
    Provides structured analysis using predefined rules and thresholds.
    """
    query_lower = query.lower()
    insights = []
    flagged_students = []

    if not data:
        return {
            "answer": "No data available for analysis.",
            "explanation": "No student records matched the query criteria.",
            "query_type": "analytical",
            "data": []
        }

    # --- Weak student analysis ---
    if "weak" in query_lower or "improve" in query_lower or "suggest" in query_lower:
        weak = [s for s in data if s.get("attendance", 100) < 60 or s.get("avg_marks", 100) < 50]

        if weak:
            insights.append(f"[ANALYSIS] Found {len(weak)} students requiring attention:\n")
            for s in weak:
                reasons = []
                if s.get("attendance", 100) < 60:
                    reasons.append(f"attendance {s['attendance']}% < 60%")
                if s.get("avg_marks", 100) < 50:
                    reasons.append(f"avg marks {s['avg_marks']} < 50")

                flag_text = f"  [!] {s['name']} ({s['branch']} Year {s['year']})"
                flag_text += f"\n     Flagged because: {' AND '.join(reasons)}"
                flagged_students.append(flag_text)

            insights.extend(flagged_students)
            insights.append("\n[SUGGESTIONS] Suggestions for Improvement:")
            insights.append("  * Assign faculty mentors for personalized guidance")
            insights.append("  * Enroll in mandatory remedial classes (Saturdays 10 AM - 1 PM)")
            insights.append("  * Pair with high-performing peers for tutoring")
            insights.append("  * Schedule bi-weekly progress check-ins")
            insights.append("  * Encourage minimum 2 hours daily self-study")
        else:
            insights.append("[OK] No students are currently flagged as weak!")
            insights.append("All students have attendance >= 60% and average marks >= 50.")

    # --- Top performer analysis ---
    elif "top" in query_lower or "best" in query_lower or "performer" in query_lower:
        # Sort by avg_marks descending
        sorted_data = sorted(data, key=lambda x: x.get("avg_marks", 0), reverse=True)
        top = sorted_data[:5]

        insights.append(f"[TOP] Top {len(top)} Performers:\n")
        for i, s in enumerate(top, 1):
            insights.append(
                f"  {i}. {s['name']} ({s['branch']} Year {s['year']}) — "
                f"Avg Marks: {s.get('avg_marks', 'N/A')} | "
                f"Attendance: {s.get('attendance', 'N/A')}%"
            )

    # --- General performance analysis ---
    else:
        # Calculate statistics
        avg_marks_list = [s.get("avg_marks", 0) for s in data if s.get("avg_marks")]
        attendance_list = [s.get("attendance", 0) for s in data if s.get("attendance")]

        if avg_marks_list:
            overall_avg = round(sum(avg_marks_list) / len(avg_marks_list), 1)
            highest = max(avg_marks_list)
            lowest = min(avg_marks_list)

            insights.append(f"[ANALYSIS] Performance Analysis ({data_context}):\n")
            insights.append(f"  * Students analyzed: {len(data)}")
            insights.append(f"  * Average marks: {overall_avg}")
            insights.append(f"  * Highest avg: {highest}")
            insights.append(f"  * Lowest avg: {lowest}")

        if attendance_list:
            avg_attendance = round(sum(attendance_list) / len(attendance_list), 1)
            low_att = [s for s in data if s.get("attendance", 100) < 60]
            insights.append(f"  * Average attendance: {avg_attendance}%")
            insights.append(f"  * Students with attendance < 60%: {len(low_att)}")

        # Flag struggling students
        struggling = [s for s in data if s.get("avg_marks", 100) < 50 or s.get("attendance", 100) < 60]
        if struggling:
            insights.append(f"\n  [!] {len(struggling)} student(s) need attention:")
            for s in struggling:
                reasons = []
                if s.get("attendance", 100) < 60:
                    reasons.append(f"attendance {s['attendance']}%")
                if s.get("avg_marks", 100) < 50:
                    reasons.append(f"avg marks {s['avg_marks']}")
                insights.append(f"    - {s['name']}: {', '.join(reasons)}")

    answer = "\n".join(insights)

    return {
        "answer": answer,
        "explanation": (
            f"Analysis performed using rule-based engine. "
            f"Analyzed {len(data)} student records from: {data_context}. "
            f"Thresholds used: attendance < 60% (flagged), avg marks < 50 (flagged)."
        ),
        "query_type": "analytical",
        "data": data,
        "model_info": {"provider": "fallback", "model": "rule-based", "token_count": 0},
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. RAG SIMULATION — Knowledge Base Search
# ═══════════════════════════════════════════════════════════════════════════

def _search_knowledge_base(query: str) -> list[str]:
    """
    Search static documents in knowledge_base/ for passages matching
    the query keywords. Returns a list of relevant text passages.
    """
    kb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
    relevant_passages = []

    if not os.path.exists(kb_dir):
        return relevant_passages

    # Read all .txt files in knowledge_base/
    for filename in os.listdir(kb_dir):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(kb_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Split into sections (using numbered headers like "1.", "2.", etc.)
        sections = re.split(r'\n(?=\d+\.\s+[A-Z])', content)

        # Score each section by keyword overlap with the query
        query_words = set(query.lower().split())
        for section in sections:
            section_lower = section.lower()
            # Count how many query words appear in this section
            matches = sum(1 for word in query_words if word in section_lower)
            # Require at least 2 matching words (or 1 for short queries)
            threshold = 1 if len(query_words) <= 3 else 2
            if matches >= threshold:
                # Clean up the section text
                cleaned = section.strip()
                if cleaned and len(cleaned) > 20:
                    relevant_passages.append(cleaned)

    return relevant_passages


# ═══════════════════════════════════════════════════════════════════════════
# 6. MAIN PROCESSING FUNCTION — Entry point for all queries
# ═══════════════════════════════════════════════════════════════════════════

def process_query(
    query: str,
    role: str = "student",
    llm_config: Optional[dict] = None,
) -> dict:
    """
    Main entry point: process a natural language query through the full pipeline.

    Flow: Query -> Context Engine -> Decision Engine -> Handler -> Response

    Args:
        query:      Natural language query from the user
        role:       User role (student/teacher/admin)
        llm_config: Optional dict to override LLM router settings at runtime.
                    Keys: openai_api_key, ollama_url, ollama_model, strategy, token_threshold

    Returns:
        dict with keys: answer, explanation, query_type, data, model_info
    """
    global llm_router

    # Step 0: Apply runtime LLM config if provided
    if llm_config:
        llm_router.update_config(
            openai_api_key=llm_config.get("openai_api_key"),
            ollama_url=llm_config.get("ollama_url"),
            ollama_model=llm_config.get("ollama_model"),
            strategy=llm_config.get("strategy"),
            token_threshold=llm_config.get("token_threshold"),
        )

    # Step 1: Update context
    context_engine.set_role(role)

    # Step 2: Classify the query
    query_type = classify_query(query)

    # Step 3: Route to appropriate handler
    if query_type == "data":
        result = handle_data_query(query)
        # Data queries don't use LLM, add default model_info
        if "model_info" not in result:
            result["model_info"] = {"provider": "database", "model": "SQLite", "token_count": 0}
    elif query_type == "analytical":
        result = handle_analytical_query(query)
    elif query_type == "knowledge":
        result = handle_knowledge_query(query)
    else:
        result = {
            "answer": "I'm not sure how to handle that query. Please try rephrasing.",
            "explanation": "Query could not be classified into any known category.",
            "query_type": "unknown",
            "data": [],
            "model_info": {"provider": "none", "model": "none", "token_count": 0},
        }

    # Step 4: Save to session memory
    context_engine.add_to_memory(query, result["answer"])

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 7. UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _extract_number(text: str, default: float = 60.0) -> float:
    """Extract the first number from a text string."""
    numbers = re.findall(r'\d+\.?\d*', text)
    return float(numbers[0]) if numbers else default


def _extract_branch(text: str) -> Optional[str]:
    """Extract branch name from query text."""
    branches = {"cse": "CSE", "ece": "ECE", "me": "ME", "ce": "CE"}
    text_lower = text.lower()
    for key, value in branches.items():
        if key in text_lower:
            return value
    return None


def _extract_year(text: str) -> Optional[int]:
    """Extract year number from query text."""
    # Match patterns like "3rd year", "year 3", "2nd year"
    year_patterns = [
        r'(\d+)(?:st|nd|rd|th)\s*year',
        r'year\s*(\d+)',
        r'(\d+)\s*year',
    ]
    for pattern in year_patterns:
        match = re.search(pattern, text.lower())
        if match:
            year = int(match.group(1))
            if 1 <= year <= 4:
                return year
    return None


def _format_data_as_text(data: list) -> str:
    """Format a list of dicts into a readable text table."""
    if not data:
        return "No data found."

    lines = []
    for i, row in enumerate(data, 1):
        parts = []
        for key, value in row.items():
            # Make keys readable
            display_key = key.replace("_", " ").title()
            parts.append(f"{display_key}: {value}")
        lines.append(f"{i}. {' | '.join(parts)}")

    return "\n".join(lines)


def _format_data_for_llm(data: list) -> str:
    """Format data compactly for LLM consumption."""
    if not data:
        return "No data available."

    lines = []
    for row in data:
        parts = [f"{k}={v}" for k, v in row.items()]
        lines.append(", ".join(parts))

    return "\n".join(lines)
