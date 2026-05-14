# QA Copilot - Project Guidelines

## Run Commands
- **Install Backend Deps**: `pip install -r backend/requirements.txt`
- **Master Ingestion**: `python -m backend.ingest.ingest_all`
- **Start Backend**: `uvicorn backend.main:app --reload --port 8000`
- **Start Frontend**: `cd frontend && npm install && npm run dev`
- **Single Source Ingest**: `python -m backend.ingest.ingest_testcases` (and others)

## Architecture
- **Vector DB**: 5-collection Qdrant store (Local File Mode).
- **Retrieval Pipeline**: 
  1. `Query Rewriter` (Groq) - Condenses follow-ups.
  2. `LLM Router` (Groq) - Selects 1-2 relevant collections.
  3. `Hybrid Search` (BGE-M3) - Dense + Sparse fusion via RRF.
  4. `Reranker` (BGE-Reranker-v2-M3) - Cross-Encoder for top-4.
- **Frontend**: Vite + React + Tailwind + SSE Streaming.

## Key Data Shapes
| Collection | Source | Metadata |
|---|---|---|
| `selenium_code` | .java | class, method, annotations |
| `playwright_code` | .ts/.js | file, test_title |
| `vwo_testcases` | .csv | tc_id, jira_id, steps |
| `vwo_docs` | .pdf | page, doc_title |
| `vwo_bugs` | .md | jira_id, status, summary |

## Common Pitfalls
- **Qdrant Lock**: Cannot run ingestion while the backend server is active in local storage mode. Stop the server before re-ingesting.
- **Model Size**: BGE-M3 is ~2GB. Ensure sufficient disk space and stable internet on first run.
- **Node Modules**: Ensure `frontend/node_modules` is not indexed by ingestion.
