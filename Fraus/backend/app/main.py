from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.mongo import close_mongo, connect_mongo
from app.routers.takeover import router as takeover_router
from app.routers.transcript import router as transcript_router
from app.routers.verification import router as verification_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_mongo()
    try:
        yield
    finally:
        await close_mongo()


app = FastAPI(title="Fraus Verification API", version="0.1.0", lifespan=lifespan)
app.include_router(verification_router)
app.include_router(takeover_router)
app.include_router(transcript_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
