# QA Copilot

Multi-source QA RAG app grounded in:

- Selenium Java automation code
- Playwright TypeScript automation code
- VWO manual test cases
- VWO PRD PDFs
- VWO Jira bug markdown exports

The backend follows the working `Chapter_09_Project_QACopilot` pipeline: query rewrite, intent routing, Qdrant hybrid dense+sparse search, RRF fusion, BGE rerank, Groq streaming answers, source citations, RAG explorer traces, and ingest controls.

## Run

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Configure secrets:

```bash
copy .env.example .env
```

Add `GROQ_API_KEY` to `.env`.

Start the backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Useful Commands

Check indexed collection counts:

```bash
python scripts/test_backend_core.py
```

Reingest all sources:

```bash
python -m backend.ingest.ingest_all --recreate
```

Build the frontend:

```bash
cd frontend
npm run build
```

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/explore`
- `POST /api/ingest/{selenium|playwright|testcases|pdfs|jira|all}`
- `GET /api/ingestion/status`
- `POST /api/ingestion/trigger`
