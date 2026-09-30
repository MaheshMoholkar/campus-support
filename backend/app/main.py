from fastapi import FastAPI

from app.routers import auth, health

app = FastAPI(title="Campus Support API")
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
