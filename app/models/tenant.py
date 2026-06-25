from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column, validates
from sqlalchemy.types import JSON
from app.db import Base

if TYPE_CHECKING:
    from app.core.contracts import VerticalAdapter
    from app.verticals.base import BaseVertical


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    pricing_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Workflow visibility: list of vertical_id strings this tenant has access to.
    # None → legacy / unset → treated as ["painting"] by the UI fallback.
    # Example: ["painting", "roofing"]
    enabled_verticals: Mapped[list | None] = mapped_column(JSON, nullable=True)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    welcome_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @validates("sector")
    def _validate_sector(self, _key: str, value: str | None) -> str | None:
        """
        Ensure sector contains a known vertical key.

        Validation accepts currently registered keys and a safe bootstrap set.
        """
        if value is None:
            return None

        normalized = value.strip().lower()
        if not normalized:
            return None

        from app.verticals.registry import VERTICALS

        known_keys = set(VERTICALS.keys())
        if normalized not in known_keys:
            choices = ", ".join(sorted(known_keys))
            raise ValueError(
                f"Invalid sector '{value}'. Expected one of: {choices}."
            )
        return normalized

    def get_vertical(self) -> "BaseVertical | VerticalAdapter":
        """
        Resolve the tenant vertical instance from registry.

        Falls back to the construction vertical when sector is unset.
        """
        from app.verticals.registry import get_vertical

        return get_vertical(self.sector or "construction")

    def __repr__(self) -> str:
        return f"<Tenant id={self.id!r} name={self.name!r}>"


def get_tenant_by_slug(db: Session, slug: str) -> "Tenant | None":
    """
    Small helper for public routing to keep slug lookups consistent.
    """
    if not slug:
        return None
    return db.query(Tenant).filter(Tenant.slug == slug).first()
