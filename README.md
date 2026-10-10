# AI Business Intelligence Co-Pilot

A responsive React + Vite dashboard with a FastAPI backend for uploading CSV/Excel datasets, profiling data, calculating schema-aware KPIs, charting numeric trends, detecting unusual rows, and exporting data.

## Requirements
- Node.js 18+
- Python 3.10+

## Start the backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Backend: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs

## Start the frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open the local URL shown by Vite (usually http://localhost:5173).

## Features
- Premium dark-navy sidebar and light analytics workspace
- Responsive navigation and overview dashboard
- CSV and Excel upload, dataset selection, preview, and download
- Data profile: rows, columns, missing values, duplicates, numerical summaries
- Schema-aware KPI estimates based on detected numeric/date/category columns
- Interactive charts and searchable records table
- Basic Isolation Forest anomaly detection when enough numeric data is available
- Baseline trend forecast when a suitable date/numeric pair exists
- CSV report/export
- API health endpoint and input validation

## Important limitations
- Data is processed in memory for this starter; uploaded datasets are not persisted after the backend restarts.
- The AI Copilot UI explains that an LLM provider is not configured. It does not pretend to be live AI.
- KPI labels are inferred from column names. Review the selected columns before relying on business interpretations.
- Anomaly detection flags records for investigation; it does not establish fraud.
- Forecasts are simple linear baselines, not guarantees. They are unavailable when data is unsuitable.
- This project is a runnable foundation, not a security-audited production deployment.

## Environment
Copy `backend/.env.example` to `backend/.env` if desired. No API key is required for the core features.
