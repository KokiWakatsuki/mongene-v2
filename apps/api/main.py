"""FastAPI エントリーポイント（§35.2）

起動方法:
    uvicorn apps.api.main:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()  # noqa: E402  load before importing modules that read env

from apps.api.src.domains.problems.router import router as problems_router  # noqa: E402
from apps.api.src.domains.teachers.router import router as teachers_router  # noqa: E402
from apps.api.src.domains.students.router import router as students_router  # noqa: E402
from apps.api.src.domains.learning.router import router as learning_router  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIAGRAM_DIR = REPO_ROOT / "master_data" / "cache" / "diagrams"
TEMPLATES_DIR = REPO_ROOT / "apps" / "api" / "templates"

app = FastAPI(
    title="mongene-v2",
    description="中学数学問題自動生成システム",
    version="0.1.0",
)

DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/diagrams", StaticFiles(directory=str(DIAGRAM_DIR)), name="diagrams")

app.include_router(problems_router)
app.include_router(teachers_router)
app.include_router(students_router)
app.include_router(learning_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/learn", include_in_schema=False)
def learn() -> FileResponse:
    """個別最適化・完全習得学習ループの体験 UI。"""
    return FileResponse(TEMPLATES_DIR / "learn.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
