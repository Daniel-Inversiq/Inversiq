import logging
from typing import Literal

from openai import OpenAI

from app.core.settings import settings

logger = logging.getLogger(__name__)

ClassificationLabel = Literal[
    "positive",
    "not_now",
    "no_fit",
    "unsubscribe",
    "objection",
    "other",
]

_VALID_LABELS: set[str] = {
    "positive",
    "not_now",
    "no_fit",
    "unsubscribe",
    "objection",
    "other",
}

_SYSTEM_PROMPT = """
You classify sales outreach reply emails into exactly one category.

Categories:
- positive    : interested, wants to meet, asks for more info, open to a call
- not_now     : not the right time, maybe later, currently busy
- no_fit      : wrong person, wrong company, not relevant
- unsubscribe : wants to be removed from the list, stop emailing me
- objection   : has a specific concern or objection (price, trust, competitor)
- other       : anything that does not fit the above

Reply with ONLY the category label, nothing else.
""".strip()


class ReplyClassifier:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def classify(self, text: str) -> str:
        """
        Classify a reply email body and return one of:
        positive, not_now, no_fit, unsubscribe, objection, other
        """
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set — defaulting classification to 'other'")
            return "other"

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text[:2000]},  # guard against huge bodies
                ],
                max_tokens=10,
                temperature=0,
            )
            label = response.choices[0].message.content.strip().lower()
        except Exception:
            logger.exception("ReplyClassifier API call failed — defaulting to 'other'")
            return "other"

        if label not in _VALID_LABELS:
            logger.warning("Unexpected classification label %r — defaulting to 'other'", label)
            return "other"

        return label
