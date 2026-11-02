from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.transactions import router as transactions_router
from backend.app.api.risk import router as risk_router
from backend.app.api.simulator import router as simulator_router
from backend.app.services.mlflow_manager import ensure_mlflow_running
from simulator.model_scoring import load_production_model
from backend.app.api.alerts import router as alerts_router
from backend.app.api.investigations import router as investigations_router
from backend.app.api.dashboard import router as dashboard_router

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

# Configure development CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk_router)
app.include_router(simulator_router)
app.include_router(transactions_router)
app.include_router(alerts_router)
app.include_router(investigations_router)
app.include_router(dashboard_router)


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
