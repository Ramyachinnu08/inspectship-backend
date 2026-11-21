from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .routers import auth, admin, inspector, ai, rag

app = FastAPI(
    title="InspectShip API",
    description="Backend for InspectShip - Maritime Vessel Inspection Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(inspector.router)
app.include_router(ai.router)
app.include_router(rag.router)

@app.get("/")
def root():
    return {"message": "Welcome to InspectShip API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}

# Serves the on-device AI model file for the mobile app:
#   put gemma-3-1b-it-int4.task inside  app/static/models/
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(_static_dir, "models"), exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")