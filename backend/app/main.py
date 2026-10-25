from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.risk import router as risk_router
from backend.app.api.simulator import router as simulator_router
from backend.app.services.mlflow_manager import ensure_mlflow_running
from simulator.model_scoring import load_production_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MLflow and load the production model during startup."""

    print("Initializing BankGuard...")

    # Start MLflow if it is not already running.
    ensure_mlflow_running()

    # Load the production model once.
    print("Loading production fraud detection model...")
    model = load_production_model()
    app.state.fraud_model = model

    print("BankGuard is ready.")

    yield

    print("BankGuard application shutting down.")


app = FastAPI(
    title="BankGuard API",
    description="Fraud detection and transaction risk management platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(risk_router)
app.include_router(simulator_router)


@app.get("/")
def root():
    return {
        "application": "BankGuard",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}