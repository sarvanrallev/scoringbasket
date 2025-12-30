"""
FastAPI main application for Scoring Basket
Initializes the app, middleware, WebSocket, and routes
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import os
from dotenv import load_dotenv
from starlette.routing import Mount

from .routes import router
from .routes_auth import router as auth_router
from .routes_games import router as games_router
from .routes_websocket import router as websocket_router
from .websocket import get_socket_app
from .websocket import get_socket_app
from .database import init_db, verify_db_connection

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Scoring Basket",
    description="Real-time basketball game scoring with WebSocket updates",
    version="0.1.0",
)

# Add CORS middleware FIRST - must be before routes
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8081,http://localhost:8000,http://127.0.0.1:8081,http://127.0.0.1:8000,http://172.20.10.8:8000").split(",")
# Clean up whitespace
cors_origins = [origin.strip() for origin in cors_origins]
print(f"✅ CORS Origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

# Initialize database
try:
    init_db()
    db_connected = verify_db_connection()
    if db_connected:
        print("✅ Database connected successfully")
    else:
        print("⚠️  Database connection check failed")
except Exception as e:
    print(f"❌ Database initialization error: {e}")

# Include routes
# app.include_router(router)  # Commented out - conflicting with games_router
app.include_router(auth_router)
app.include_router(games_router)
app.include_router(websocket_router)


# Mount Socket.IO app
socket_app = Mount("/ws", get_socket_app())
app.routes.append(socket_app)


# ==================== STARTUP/SHUTDOWN EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("🚀 Scoring Basket starting...")
    print(f"✅ Database: {os.getenv('DATABASE_URL')}")
    print("✅ API ready at /docs")
    print("✅ WebSocket ready at /ws")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("🛑 Scoring Basket shutting down...")


# ==================== ERROR HANDLERS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed information"""
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
            "error_type": "RequestValidationError"
        }
    )

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions"""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


# ==================== ROOT ENDPOINT ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Scoring Basket",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


# ==================== ADDITIONAL INFO ====================

@app.get("/info")
async def info():
    """Get app information"""
    return {
        "app": "Scoring Basket",
        "version": "0.1.0",
        "environment": os.getenv("DEBUG", "False"),
        "database": os.getenv("DATABASE_URL", "sqlite"),
        "websocket": "/ws"
    }
