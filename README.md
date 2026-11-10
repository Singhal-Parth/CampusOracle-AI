# CampusOracle AI

A local college-data assistant built with **FastAPI, Streamlit, and SQLite**. Ask natural-language questions about 25 synthetic students, run deterministic attendance/performance analysis, or retrieve passages from sample policy documents. Optional Ollama, OpenAI, and Gemini providers can turn those results into prose.

This is a portfolio prototype, not an institutional deployment. Names and academic records are invented fixtures. Sample policies are illustrative, not official rules. The response-style selector is prompt context, not authentication or role-based access control.

## Demo and scope

[View the recorded offline demo](docs/demo.md), including requests and actual responses. No hosted public service is provided.

| Example question | Actual implementation |
|---|---|
| Show students with attendance below 60% | Predefined, parameterized SQLite query |
| List all students in ECE branch | Branch/year filtering |
| Identify weak students and suggest improvements | Attendance below 60% **or** average marks below 50%; deterministic advice or opt-in LLM |
| Analyze performance of CSE 3rd year students | Filtered database records with analysis |
| Who are the top performers? | Ranking by average marks |
| What is the minimum attendance policy? | Keyword matching over sample text, optionally synthesized by an LLM |

The project uses keyword classification and document retrieval. It does not implement vector search, autonomous multi-agent orchestration, unrestricted text-to-SQL, or institutional RBAC. See [architecture and limitations](docs/architecture.md).

## Run locally

Tested with Python 3.12 on Linux. Run commands from the repository root.

```bash
git clone https://github.com/Singhal-Parth/CampusOracle-AI.git
cd CampusOracle-AI
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python db.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal, activate the same environment, then run:

```bash
python -m streamlit run app.py --server.address 127.0.0.1
```

On Windows PowerShell, use `py -3.12 -m venv .venv`, `.venv\Scripts\Activate.ps1`, and `Copy-Item .env.example .env` in place of the corresponding shell commands.

Open `http://127.0.0.1:8501`. The backend also initializes the database on startup. `python db.py` is idempotent: it leaves an existing nonempty database intact. To restore the fixture, stop the backend, remove your local `college.db`, then rerun `python db.py`. Do not store real records here.

## Provider configuration and privacy

The UI starts in **Offline** mode. No API key or Ollama installation is required. Backend defaults are also offline. Tokens displayed by the router are character-based estimates, not billing measurements.

| Mode | Behavior |
|---|---|
| Offline | No provider calls; deterministic rules and document excerpts |
| Always Ollama | Only the operator-configured local Ollama endpoint; falls back to rules if unavailable |
| Always OpenAI / Always Gemini | Only the selected cloud provider; falls back to rules if unavailable or consent is absent |
| Auto | Below the estimated token threshold: Ollama → Gemini → OpenAI. Above it: Gemini → OpenAI → Ollama. Each permitted provider is attempted at most once. |

For Ollama, install it separately, pull the model you choose, configure `OLLAMA_URL`/`OLLAMA_MODEL` in `.env`, and select **Always Ollama** in the UI. The browser cannot override the provider's network address.

For cloud use:

1. Set `ALLOW_CLOUD_LLM=true` in the backend's `.env` and configure the desired key and model. Restart the backend after changes.
2. Open **LLM Configuration**, choose a cloud-capable mode, and explicitly check **Allow cloud processing for this session**. You may provide your own key in this session instead of the operator's key.
3. Queries, the last three exchanges, selected student records, and matched policy passages may then be sent to the selected provider. Do not enter private records or secrets in chat.

`GEMINI_MODEL` must be set to a model available to your Google project. Gemini uses the [official generateContent REST API](https://ai.google.dev/api/generate-content) through `requests`, with a request-local key; no Gemini SDK is required. OpenAI uses its Python client. Configured keys are not proof that a model is available or credentials are valid. Cloud providers have not been live-tested as part of the offline regression suite.

Never commit `.env`. If a key was previously published, **revoke/rotate it at the provider**, review usage, and follow [the incident cleanup instructions](docs/maintainer-cleanup.md). Removing a file does not revoke a key or erase old commits.

## Access and session boundaries

Conversation history lives in each Streamlit session and is explicitly passed with a request. There is no global conversation endpoint or shared mutable provider configuration. Closing or clearing the chat discards its local conversation; hosting platform memory and logs are outside that guarantee.

The backend accepts unauthenticated loopback connections only. If `CAMPUS_API_TOKEN` is set, every API request needs `Authorization: Bearer <token>`; the Streamlit server reads the same value from its environment. Non-loopback connections require that token. Do not run this sample on a shared host or expose Streamlit publicly: the shared API token is an operator boundary, not per-student authorization. Production use needs user authentication, server-enforced record permissions, TLS, session isolation at the host level, rate limits, and a data-handling review.

CORS is disabled because the Streamlit server calls the API directly. Interactive API docs are disabled. Responses do not expose raw exception text or request-validation inputs.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/scan_secrets.py
python check_backend.py
```

Tests use temporary databases and mocked providers. They cover all six example queries, idempotent fixture creation, concurrent history isolation, request-local keys, cloud consent, local-only routing, bounded retries, redacted errors, and API access controls. `check_backend.py` requires the backend to be running. `test_router.py` is a manual diagnostic, not the regression suite; it never receives environment keys.

Runtime and development dependency graphs are pinned in `requirements.txt` and `requirements-dev.txt`. To update them intentionally on Python 3.12:

```bash
python -m piptools compile --upgrade --output-file requirements.txt requirements.in
python -m piptools compile --upgrade --output-file requirements-dev.txt requirements-dev.in
```

## Repository map

| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface and client-owned history |
| `main.py` | Validated API, access checks, generic errors |
| `logic.py` | Keyword classification, predefined query handlers, analysis and retrieval |
| `llm_router.py` | Request-local, consent-aware provider routing |
| `db.py` | SQLite schema, invented fixtures, parameterized query helpers |
| `knowledge_base/` | Clearly labeled sample documents |
| `tests/` | Offline regression tests |
| `docs/` | Architecture, demo evidence, maintainer notes |
| `scripts/scan_secrets.py` | Basic tracked-file credential-pattern guard |

## License

[MIT](LICENSE). Third-party libraries retain their own licenses.
