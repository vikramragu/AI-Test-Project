import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.recommendations import router as recommendations_router
from data.loader import DatasetUnavailableError, load_restaurants
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.restaurants_df = load_restaurants()
    except DatasetUnavailableError:
        logger.exception("Startup failed: dataset could not be loaded")
        raise
    yield


app = FastAPI(title="Restaurant Recommendation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
