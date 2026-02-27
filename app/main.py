from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.routers import auth, properties, verification
from fastapi.staticfiles import StaticFiles
import os
from app.routers import admin_auth

app = FastAPI(
    title="Nigeria Property App",
    description="Direct property listing platform",
    version="1.0.0"
)

# Mount static media folder — images stored here after upload
os.makedirs("media/properties", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(properties.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(admin_auth.router, prefix="/api/v1/admin")

@app.get("/")
def root():
    return {
        "message": "🏠 Nigeria Property App API",
        "version": "1.0.0",
        "status": "active",
        "documentation": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Nigeria Property App",
        "timestamp": datetime.utcnow()
    }