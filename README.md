# 🎓 AI-Powered College Data Assistant

An AI-powered natural language interface for querying and analyzing college student data. Built with FastAPI, Streamlit, SQLite, and OpenAI (with rule-based fallback).

## 🏗️ Architecture

```
User Query → Context Engine → Decision Engine → Response
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              SQL Query      LLM Analysis     RAG Simulation
              (SQLite)       (OpenAI/FB)     (Static Docs)
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                          Structured Response
                     (Answer + Explanation + Data)
```

## 📁 Project Structure

| File | Description |
|------|-------------|
| `db.py` | Database schema, sample data (25 students), query helpers |
| `logic.py` | Context Engine + Decision Engine + LLM integration |
| `main.py` | FastAPI backend server |
| `app.py` | Streamlit chat UI |
| `knowledge_base/` | Static documents for RAG simulation |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Configure OpenAI API Key

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

> **Note:** The app works fully without an API key using a rule-based fallback engine.

### 3. Initialize the Database

```bash
python db.py
```

This creates `college.db` with 25 sample students, attendance records, and marks.

### 4. Start the FastAPI Backend

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
- Health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

### 5. Start the Streamlit Frontend

Open a new terminal and run:

```bash
streamlit run app.py
```

The UI will open at `http://localhost:8501`.

## 💬 Example Queries

| Query | Type | Engine |
|-------|------|--------|
| "Show students with attendance below 60%" | Data | SQL |
| "List all students in ECE branch" | Data | SQL |
| "Identify weak students and suggest improvements" | Analytical | LLM/Fallback |
| "Analyze performance of CSE 3rd year students" | Analytical | LLM/Fallback |
| "Who are the top performers?" | Analytical | LLM/Fallback |
| "What is the minimum attendance policy?" | Knowledge | RAG |

## 🧠 Key Features

- **Context Engine**: Tracks user role and maintains last 3 queries in memory
- **Decision Engine**: Classifies queries → routes to SQL / LLM / RAG handlers
- **Explainability**: Every response includes an explanation of *why* the result was generated
- **Weak Student Flagging**: "These students are flagged because attendance < 60% and marks < 50%"
- **Dual Mode**: Works with OpenAI API or fully offline with rule-based analysis

## 📊 Database Schema

```sql
students(id, name, branch, year)
attendance(student_id, percentage)
marks(student_id, subject, score)
```

Sample data includes students from CSE, ECE, ME, and CE branches across years 1-4.
