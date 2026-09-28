from fastapi import FastAPI

app = FastAPI(
    title="BankGuard API",
    description="Fraud detection and transaction risk management platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "application": "BankGuard",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }