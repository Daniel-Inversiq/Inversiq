import base64
from datetime import datetime
from email.mime.text import MIMEText

from googleapiclient.discovery import Resource


class GmailProvider:
    """Sends emails via the Gmail API."""

    def __init__(self, service: Resource) -> None:
        self.service = service

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        """
        Send an email via Gmail API.

        Returns:
            dict with keys: gmail_message_id, gmail_thread_id, sent_at
        """
        mime_message = MIMEText(body, "plain")
        mime_message["to"] = to_email
        mime_message["subject"] = subject

        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

        response = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        return {
            "gmail_message_id": response["id"],
            "gmail_thread_id": response.get("threadId"),
            "sent_at": datetime.utcnow(),
        }

    def create_draft(self, to_email: str, subject: str, body: str) -> dict:
        """
        Create an email draft via Gmail API without sending it.

        Returns:
            dict with keys: gmail_draft_id, gmail_message_id, gmail_thread_id, created_at
        """
        mime_message = MIMEText(body, "plain")
        mime_message["to"] = to_email
        mime_message["subject"] = subject

        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

        response = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )

        message = response.get("message", {})
        return {
            "gmail_draft_id": response["id"],
            "gmail_message_id": message.get("id"),
            "gmail_thread_id": message.get("threadId"),
            "created_at": datetime.utcnow(),
        }
