from sqlalchemy.orm import Session

from app.modules.outreach.models.outbound_message import OutboundMessage


class UsedDomainsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _extract_domain(email: str | None) -> str | None:
        if not email:
            return None

        candidate = email.strip().lower()
        parts = candidate.split("@")
        if len(parts) != 2:
            return None

        local_part, domain = parts
        if not local_part or not domain or "." not in domain:
            return None

        return domain

    def get_used_domains(self) -> dict:
        recipient_rows = self.db.query(OutboundMessage.recipient_email).all()

        domains = {
            domain
            for (recipient_email,) in recipient_rows
            for domain in [self._extract_domain(recipient_email)]
            if domain
        }

        return {"domains": sorted(domains)}
