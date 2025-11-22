from fastapi import FastAPI
from app.api.v1 import chat
from app.api.v2 import chat_v2
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Include router
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["chat"])
app.include_router(chat_v2.router, prefix="/api/v2", tags=["Chat V2 (BGE-M3)"])


@app.get("/")
def root():
    return {"message": "Gym Food Recommendation API is running!"}
