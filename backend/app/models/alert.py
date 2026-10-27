from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.transaction import Transaction
    from backend.app.models.investigation import Investigation



class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    transaction_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("transactions.transaction_id"),
        nullable=False,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
        server_default="OPEN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    transaction: Mapped["Transaction"] = relationship(
        back_populates="alerts",
    )

    investigation: Mapped["Investigation | None"] = relationship(
        back_populates="alert",
        uselist=False,
    )