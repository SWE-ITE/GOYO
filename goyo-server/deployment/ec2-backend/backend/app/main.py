from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, devices, profile, home
from app.database import engine, Base
from app.services.mqtt_service import mqtt_service
import logging

# Logging 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GOYO Backend API",
    description="AI-Based Active Noise Control System",
    version="3.5.0"
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
app.include_router(home.router)

@app.get("/")
def root():
    return {
        "message": "GOYO Backend API",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_service.is_connected
    }


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 MQTT 서비스 연결"""
    logger.info("🚀 Starting GOYO Backend...")
    try:
        mqtt_service.connect()
        logger.info("✅ MQTT Service initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MQTT Service: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 MQTT 서비스 연결 해제"""
    logger.info("🛑 Shutting down GOYO Backend...")
    try:
        mqtt_service.disconnect()
        logger.info("✅ MQTT Service stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping MQTT Service: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)