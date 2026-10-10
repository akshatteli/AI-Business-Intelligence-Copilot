from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import io, os, uuid
from datetime import datetime

app = FastAPI(title="AI Business Intelligence Co-Pilot API", version="1.0.0")
origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATASETS = {}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AI Business Intelligence Co-Pilot API"}

def json_safe(value):
    if pd.isna(value): return None
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)): return value.isoformat()
    return value

def serialize_df(df, limit=100):
    safe = df.head(limit).copy()
    safe = safe.replace({np.nan: None})
    return safe.to_dict(orient="records")

def get_dataset(dataset_id):
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found. Upload a dataset first.")
    return DATASETS[dataset_id]["df"]

@app.post("/api/datasets")
async def upload_dataset(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Please upload a CSV or Excel file.")
    max_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
    raw = await file.read()
    if len(raw) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds the {max_mb} MB upload limit.")
    try:
        df = pd.read_csv(io.BytesIO(raw)) if name.endswith(".csv") else pd.read_excel(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this file. Check that it is a valid CSV or Excel workbook.")
    if df.empty or len(df.columns) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file has no usable rows or columns.")
    df.columns = [str(c).strip() or f"column_{i+1}" for i, c in enumerate(df.columns)]
    did = str(uuid.uuid4())
    DATASETS[did] = {"name": file.filename, "df": df, "uploaded_at": datetime.utcnow().isoformat()}
    return {"id": did, "name": file.filename, "rows": int(df.shape[0]), "columns": int(df.shape[1]), "uploaded_at": DATASETS[did]["uploaded_at"]}

@app.get("/api/datasets")
def list_datasets():
    return [{"id": k, "name": v["name"], "rows": int(v["df"].shape[0]), "columns": int(v["df"].shape[1]), "uploaded_at": v["uploaded_at"]} for k,v in DATASETS.items()]

@app.get("/api/datasets/{dataset_id}/preview")
def preview(dataset_id: str, page: int = 1, page_size: int = 10, search: Optional[str] = None):
    df = get_dataset(dataset_id)
    page_size = max(1, min(page_size, 100))
    filtered = df
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        filtered = df[mask]
    start = max(0, page-1) * page_size
    return {"columns": list(df.columns), "rows": serialize_df(filtered.iloc[start:start+page_size], page_size), "total": int(len(filtered)), "page": page, "page_size": page_size}

@app.get("/api/datasets/{dataset_id}/profile")
def profile(dataset_id: str):
    df = get_dataset(dataset_id)
    numeric = df.select_dtypes(include=np.number)
    columns = []
    for c in df.columns:
        s = df[c]
        item = {"name": str(c), "dtype": str(s.dtype), "missing": int(s.isna().sum()), "missing_pct": round(float(s.isna().mean()*100), 2), "unique": int(s.nunique(dropna=True))}
        if pd.api.types.is_numeric_dtype(s):
            vals = s.dropna()
            item["stats"] = {"min": json_safe(vals.min()) if len(vals) else None, "max": json_safe(vals.max()) if len(vals) else None, "mean": json_safe(vals.mean()) if len(vals) else None, "median": json_safe(vals.median()) if len(vals) else None, "std": json_safe(vals.std()) if len(vals) > 1 else None}
        columns.append(item)
    return {"rows": int(len(df)), "column_count": int(len(df.columns)), "duplicate_rows": int(df.duplicated().sum()), "columns": columns, "numeric_columns": list(numeric.columns)}

def find_column(df, words, numeric_only=False):
    for c in df.columns:
        if any(w in str(c).lower() for w in words) and (not numeric_only or pd.api.types.is_numeric_dtype(df[c])):
            return c
    return None

@app.get("/api/datasets/{dataset_id}/analytics")
def analytics(dataset_id: str):
    df = get_dataset(dataset_id)
    num = df.select_dtypes(include=np.number)
    revenue_col = find_column(df, ["revenue", "sales", "amount", "income", "value", "total"], True)
    expense_col = find_column(df, ["expense", "cost", "spend"], True)
    profit_col = find_column(df, ["profit", "margin"], True)
    revenue = float(df[revenue_col].sum()) if revenue_col else None
    expense = float(df[expense_col].sum()) if expense_col else None
    profit = float(df[profit_col].sum()) if profit_col else (revenue-expense if revenue is not None and expense is not None else None)
    category_col = find_column(df, ["category", "product", "segment", "department", "type"])
    date_col = find_column(df, ["date", "time", "day", "month"])
    trend = []
    if date_col and revenue_col:
        tmp = df[[date_col, revenue_col]].copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
        tmp = tmp.dropna().sort_values(date_col)
        if len(tmp):
            tmp["period"] = tmp[date_col].dt.strftime("%Y-%m-%d")
            trend = [{"date": str(k), "value": float(v)} for k,v in tmp.groupby("period")[revenue_col].sum().tail(30).items()]
    category = []
    if category_col and revenue_col:
        tmp = df.groupby(category_col, dropna=False)[revenue_col].sum().sort_values(ascending=False).head(8)
        category = [{"name": str(k) if pd.notna(k) else "Missing", "value": float(v)} for k,v in tmp.items()]
    recent = serialize_df(df.tail(8).iloc[::-1], 8)
    insights = []
    if revenue_col:
        insights.append({"title": f"{revenue_col} summary", "finding": f"Total across {len(df):,} rows is {revenue:,.2f}.", "basis": f"Calculated from the '{revenue_col}' column.", "action": "Compare periods and segments before making decisions."})
    missing = int(df.isna().sum().sum())
    if missing:
        insights.append({"title": "Data completeness", "finding": f"{missing:,} missing cells were found.", "basis": "Computed across all columns.", "action": "Review missing values before interpreting results."})
    return {"rows": int(len(df)), "columns": int(len(df.columns)), "revenue": revenue, "expenses": expense, "profit": profit, "transaction_count": int(len(df)), "revenue_column": str(revenue_col) if revenue_col else None, "expense_column": str(expense_col) if expense_col else None, "profit_column": str(profit_col) if profit_col else None, "trend": trend, "category": category, "recent": recent, "insights": insights, "date_column": str(date_col) if date_col else None, "category_column": str(category_col) if category_col else None}

@app.post("/api/datasets/{dataset_id}/anomalies")
def anomalies(dataset_id: str):
    df = get_dataset(dataset_id)
    numeric = df.select_dtypes(include=np.number).replace([np.inf, -np.inf], np.nan)
    if len(numeric.columns) < 1 or len(df) < 10:
        raise HTTPException(status_code=422, detail="Anomaly detection needs at least 10 rows and one numeric column.")
    numeric = numeric.fillna(numeric.median()).fillna(0)
    from sklearn.ensemble import IsolationForest
    model = IsolationForest(contamination="auto", random_state=42)
    flags = model.fit_predict(numeric)
    scores = model.decision_function(numeric)
    idx = np.where(flags == -1)[0][:100]
    records = []
    for i in idx:
        row = {k: json_safe(v) for k,v in df.iloc[int(i)].to_dict().items()}
        row["_row"] = int(i+1)
        row["_score"] = round(float(scores[i]), 4)
        records.append(row)
    return {"method": "Isolation Forest", "flagged_count": int((flags == -1).sum()), "rows": records, "note": "Anomalies are investigation signals, not proof of fraud."}

@app.post("/api/datasets/{dataset_id}/forecast")
def forecast(dataset_id: str, date_column: str, target_column: str, horizon: int = 7):
    df = get_dataset(dataset_id)
    if date_column not in df.columns or target_column not in df.columns:
        raise HTTPException(status_code=400, detail="Choose valid date and target columns.")
    dates = pd.to_datetime(df[date_column], errors="coerce")
    vals = pd.to_numeric(df[target_column], errors="coerce")
    tmp = pd.DataFrame({"date": dates, "value": vals}).dropna().sort_values("date")
    if len(tmp) < 5:
        raise HTTPException(status_code=422, detail="Forecasting needs at least five valid date/value observations.")
    daily = tmp.groupby(tmp["date"].dt.floor("D"))["value"].mean().reset_index()
    if len(daily) < 5:
        raise HTTPException(status_code=422, detail="Forecasting needs at least five distinct dates.")
    x = np.arange(len(daily))
    slope, intercept = np.polyfit(x, daily["value"].to_numpy(), 1)
    horizon = max(1, min(int(horizon), 30))
    last = daily["date"].iloc[-1]
    future = [{"date": (last + pd.Timedelta(days=i)).strftime("%Y-%m-%d"), "value": round(float(intercept+slope*(len(daily)-1+i)), 2), "kind": "forecast"} for i in range(1, horizon+1)]
    history = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2), "kind": "actual"} for d,v in zip(daily["date"].tail(30), daily["value"].tail(30))]
    return {"history": history, "forecast": future, "method": "Linear trend baseline", "note": "A simple baseline estimate; not a guarantee. Validate against holdout data before business use."}

@app.get("/api/datasets/{dataset_id}/export")
def export(dataset_id: str):
    df = get_dataset(dataset_id)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="dataset-export.csv"'})

class ChatRequest(BaseModel):
    message: str

@app.post("/api/datasets/{dataset_id}/copilot")
def copilot(dataset_id: str, request: ChatRequest):
    df = get_dataset(dataset_id)
    stats = {"rows": len(df), "columns": len(df.columns), "missing_cells": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum()), "numeric_columns": list(df.select_dtypes(include=np.number).columns)}
    return {"mode": "insights-only", "answer": "I can summarize verified dataset facts, but a live LLM provider is not configured. " + f"This dataset has {stats['rows']:,} rows, {stats['columns']} columns, {stats['missing_cells']:,} missing cells, and {stats['duplicate_rows']:,} duplicate rows. Numeric columns: {', '.join(map(str, stats['numeric_columns'])) or 'none detected'}. Treat this as a data summary, not an AI-generated causal explanation.", "stats": stats}
