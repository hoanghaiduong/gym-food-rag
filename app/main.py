import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.v2 import system
from app.core.config import settings
from app.core.exceptions import add_exception_handlers
from app.core.paths import LOG_FILE_PATH
from app.core.response import BaseResponse, success_response


LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("System starting up...")
    log_task = asyncio.create_task(system.watch_log_file())
    try:
        yield
    finally:
        logger.info("System shutting down...")
        log_task.cancel()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
add_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", response_model=BaseResponse[dict])
def root():
    return success_response(data={"service": settings.PROJECT_NAME}, message="API is running!")
