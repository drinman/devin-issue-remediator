from fastapi import FastAPI

from app.config import settings


app = FastAPI(title="Devin Issue Remediator")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Devin Issue Remediator is running.",
        "mode": settings.app_mode,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
