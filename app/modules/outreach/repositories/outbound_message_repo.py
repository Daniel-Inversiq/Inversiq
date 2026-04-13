from sqlalchemy.orm import Session

from app.modules.outreach.models.outbound_message import OutboundMessage


class OutboundMessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> OutboundMessage:
        record = OutboundMessage(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
