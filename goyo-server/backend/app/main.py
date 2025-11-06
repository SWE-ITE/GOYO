from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, devices, profile, audio
from app.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GOYO Backend API",
    description="AI-Based Active Noise Control System",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(profile.router)
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])

@app.get("/")
def root():
    return {
        "message": "GOYO Backend API",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)