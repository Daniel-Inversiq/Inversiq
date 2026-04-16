import base64
import html
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import Resource


class GmailProvider:
    """Sends emails via the Gmail API."""

    def __init__(
        self,
        service: Resource,
        *,
        signature_enabled: bool = True,
        signature_signoff: str = "Met vriendelijke groet,",
        signature_name: str = "",
        signature_company: str = "Inversiq",
        signature_website: str = "",
        signature_phone: str = "",
    ) -> None:
        self.service = service
        self.signature_enabled = bool(signature_enabled)
        self.signature_signoff = (signature_signoff or "").strip()
        self.signature_name = (signature_name or "").strip()
        self.signature_company = (signature_company or "").strip()
        self.signature_website = (signature_website or "").strip()
        self.signature_phone = (signature_phone or "").strip()

    @staticmethod
    def _body_to_html(body: str) -> str:
        """
        Convert plain text body to safe, readable HTML.
        - Escapes user-provided content.
        - Preserves paragraph boundaries and line breaks.
        """
        normalized = (body or "").replace("\r\n", "\n").replace("\r", "\n")
        if not normalized.strip():
            return "<html><body><p></p></body></html>"

        # Treat exactly 2+ consecutive newlines as paragraph separators.
        # Single newlines inside a paragraph remain line breaks.
        paragraphs = [
            p.strip() for p in re.split(r"\n{2,}", normalized.strip()) if p.strip()
        ]
        rendered = []
        for p in paragraphs:
            escaped = html.escape(p)
            rendered.append(
                f"<p style=\"margin:0 0 14px 0; line-height:1.6;\">{escaped.replace(chr(10), '<br>')}</p>"
            )

        # Avoid extra trailing space after the final paragraph.
        if rendered:
            rendered[-1] = rendered[-1].replace("margin:0 0 12px 0;", "margin:0;", 1)

        return '<html><body style="font-family:Arial, sans-serif; font-size:15px; color:#111827;">{}</body></html>'.format(
            "".join(rendered)
        )

    def _build_mime_message(self, to_email: str, subject: str, body: str):
        msg = MIMEMultipart("alternative")
        msg["to"] = to_email
        msg["subject"] = subject
        text_body = body or ""
        html_body = self._body_to_html(body)

        if self.signature_enabled:
            text_signature = self._build_text_signature()
            html_signature = self._build_html_signature()
            if text_signature:
                text_body = f"{text_body.rstrip()}\n\n{text_signature}"
            if html_signature:
                html_body = self._append_html_signature(html_body, html_signature)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def _build_text_signature(self) -> str:
        lines = []
        if self.signature_signoff:
            lines.append(self.signature_signoff)
        if self.signature_name:
            lines.append(self.signature_name)
        if self.signature_company:
            lines.append(self.signature_company)
        if self.signature_website:
            lines.append(self.signature_website)
        if self.signature_phone:
            lines.append(self.signature_phone)
        return "\n".join(lines).strip()

    def _build_html_signature(self) -> str:
        lines = []
        if self.signature_signoff:
            lines.append(f"<div>{html.escape(self.signature_signoff)}</div>")
        if self.signature_name:
            lines.append(f"<div>{html.escape(self.signature_name)}</div>")
        if self.signature_company:
            lines.append(f"<div>{html.escape(self.signature_company)}</div>")
        if self.signature_website:
            website = self.signature_website.strip()
            href = (
                website
                if website.startswith(("http://", "https://"))
                else f"https://{website}"
            )
            lines.append(
                f'<div><a href="{html.escape(href, quote=True)}">{html.escape(website)}</a></div>'
            )
        if self.signature_phone:
            lines.append(f"<div>{html.escape(self.signature_phone)}</div>")
        if not lines:
            return ""
        return (
            '<div style="margin-top:16px;padding-top:12px;border-top:1px solid #e5e7eb;'
            'color:#374151;font-size:14px;line-height:1.5;">'
            f"{''.join(lines)}"
            "</div>"
        )

    @staticmethod
    def _append_html_signature(html_body: str, signature_html: str) -> str:
        if not signature_html:
            return html_body
        if "</body>" in html_body:
            return html_body.replace("</body>", f"{signature_html}</body>", 1)
        return f"{html_body}{signature_html}"

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        """
        Send an email via Gmail API.

        Returns:
            dict with keys: gmail_message_id, gmail_thread_id, sent_at
        """
        mime_message = self._build_mime_message(
            to_email=to_email,
            subject=subject,
            body=body,
        )

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
        mime_message = self._build_mime_message(
            to_email=to_email,
            subject=subject,
            body=body,
        )

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
