#!/usr/bin/env bash
# Run with your own authenticated GitHub CLI account (repository administration permission).
set -euo pipefail
repo='Singhal-Parth/CampusOracle-AI'
gh auth status
gh repo edit "$repo" \
  --description 'Local college-data assistant with FastAPI, Streamlit, SQLite, offline analytics and opt-in LLM routing.' \
  --homepage 'https://github.com/Singhal-Parth/CampusOracle-AI#readme' \
  --add-topic python --add-topic fastapi --add-topic streamlit --add-topic sqlite \
  --add-topic ollama --add-topic llm --add-topic portfolio-project
