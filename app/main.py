import logging
import os
import traceback

# from app.utils.helper import CommonResponse
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from app.utils.helper import CommonResponse

import asyncio
# from app.utils.logger import schedule_daily_email

from app.api.places.router import router as places_router
from app.api.countries.router import router as country_router
from app.api.states.router import router as state_router
from app.api.cities.router import router as city_router
from app.api.restaurants.router import router as restaurant_router
# from app.models import *

from app.database.db import Base, engine  # Import Base and engine
from config import Config

# Initialize FastAPI app
app = FastAPI(
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    root_path="/api"
)

# Load configurations from custom class
app.state.config = Config

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files at /static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# STATIC_DIR = os.path.join(BASE_DIR, "../static")
# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
#app.mount("/static", StaticFiles(directory="static"), name="static")

# Register your routers
# app.include_router(bulk_router)
# app.include_router(benefits.router)
app.include_router(places_router)
app.include_router(country_router)
app.include_router(state_router)
app.include_router(city_router)
app.include_router(restaurant_router)
# app.include_router(article_router.router)

# Startup event: Create DB tables
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


# Middleware for closing DB session — optional depending on how you manage sessions

import time

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = await call_next(request)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print("inside http_exception_handler")
    # If the detail is already a CommonResponse-style dict, use it
    if isinstance(exc.detail, dict) and "is_success" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # Otherwise, wrap it
    return JSONResponse(
        status_code=exc.status_code,
        content=CommonResponse.response_handler(
            result=None,
            message=exc.detail if isinstance(exc.detail, str) else str(exc),
            status_code=exc.status_code,
            is_success=False,
        ).dict(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    print("inside request validation error handler")
    logging.warning(f"⚠️ Validation Error: {exc.errors()}")

    if exc.errors():
        first_error = exc.errors()[0]
        loc = ".".join(str(loc_part) for loc_part in first_error.get("loc", []) if loc_part != 'body')
        msg = first_error.get("msg", "Invalid input")
        error_message = f"{loc}: {msg}" if loc else msg
    else:
        error_message = "Invalid input"

    return JSONResponse(
        status_code=422,
        content=CommonResponse.response_handler(
            # result= exc.errors() if exc.errors() else {"detail": [str(err['msg']) for err in exc.errors()]} ,
            result=None,
            error=error_message,
            message="Validation failed",
            status_code=200,
            is_success=False,
        ).dict(),
    )



@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    print("inside pydantic validation error handler")
    logging.warning(f"📦 Pydantic Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content=CommonResponse.response_handler(
            result=exc.errors(),
            message="Pydantic validation failed",
            status_code=422,
            is_success=False,
        ).dict(),
    )

# check health
@app.get("/check-api-status")
async def check_api_status():
    return JSONResponse(status_code=200, content={"message": "API is running", "status": "ok"})

# Route placeholder for favicon
@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(status_code=404, content={})
