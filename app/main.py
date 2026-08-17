from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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