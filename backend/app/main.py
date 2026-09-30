from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import DomainError
from app.routers import auth, health, lookups, tickets

app = FastAPI(title="Campus Support API")


@app.exception_handler(DomainError)
def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for module in (health, auth, tickets, lookups):
    app.include_router(module.router, prefix="/api/v1")
