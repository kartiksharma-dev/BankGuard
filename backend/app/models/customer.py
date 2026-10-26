from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base 

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.transaction import Transaction

class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="customer",
    )