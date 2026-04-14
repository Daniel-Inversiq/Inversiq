from sqlalchemy.orm import Session

from app.modules.outreach.models.message_reply import MessageReply


class MessageReplyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> MessageReply:
        record = MessageReply(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def exists_by_gmail_message_id(self, gmail_message_id: str) -> bool:
        return (
            self.db.query(MessageReply)
            .filter(MessageReply.gmail_message_id == gmail_message_id)
            .first()
            is not None
        )
