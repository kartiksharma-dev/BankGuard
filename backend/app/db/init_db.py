from backend.app.db.session import Base, engine
from backend.app.models import (
    Alert,
    Customer,
    Investigation,
    Transaction,
)


def create_tables() -> None:
    """Create missing BankGuard database tables."""
    Base.metadata.create_all(bind=engine)
    print("BankGuard database tables created or already exist.")


if __name__ == "__main__":
    try:
        create_tables()
    finally:
        engine.dispose()