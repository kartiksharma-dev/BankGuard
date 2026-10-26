from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.alert import Alert
    from backend.app.models.customer import Customer

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    customer_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("customers.customer_id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    merchant_category: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    payment_method: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(100), nullable=False)

    oldbalance_org: Mapped[float] = mapped_column(Float, nullable=False)
    newbalance_orig: Mapped[float] = mapped_column(Float, nullable=False)
    oldbalance_dest: Mapped[float] = mapped_column(Float, nullable=False)
    newbalance_dest: Mapped[float] = mapped_column(Float, nullable=False)

    step: Mapped[int] = mapped_column(Integer, nullable=False)

    fraud_prediction: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="transactions",
    )

    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="transaction",
    )