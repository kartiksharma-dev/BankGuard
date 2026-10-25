import logging
import os
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

MLFLOW_HOST = "127.0.0.1"
MLFLOW_PORT = 5000
MLFLOW_URL = f"http://{MLFLOW_HOST}:{MLFLOW_PORT}"
MLFLOW_HEALTH_URL = f"{MLFLOW_URL}/health"

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../..")
)

logger = logging.getLogger(__name__)

_mlflow_process = None


def is_mlflow_running() -> bool:
    """Check whether the MLflow server is responding."""
    try:
        with urlopen(MLFLOW_HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def ensure_mlflow_running(timeout_seconds: int = 60) -> None:
    """Start MLflow if necessary and wait until its health check succeeds."""
    global _mlflow_process

    if is_mlflow_running():
        logger.info("MLflow is already running.")
        return

    logger.info("MLflow is not running. Starting MLflow server...")

    database_path = os.path.join(PROJECT_ROOT, "mlflow.db").replace("\\", "/")
    artifact_path = os.path.join(PROJECT_ROOT, "mlartifacts").replace("\\", "/")

    command = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--backend-store-uri",
        f"sqlite:///{database_path}",
        "--default-artifact-root",
        f"file:///{artifact_path}",
        "--host",
        MLFLOW_HOST,
        "--port",
        str(MLFLOW_PORT),
    ]

    _mlflow_process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if _mlflow_process.poll() is not None:
            raise RuntimeError(
                "MLflow server exited before becoming ready. "
                "Run MLflow manually to inspect its error output."
            )

        if is_mlflow_running():
            logger.info("MLflow server is ready.")
            return

        time.sleep(1)

    raise TimeoutError(
        f"MLflow did not become ready within {timeout_seconds} seconds."
    )