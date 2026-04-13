import os
from datetime import datetime, timezone
from typing import Optional

import stripe

from app.core.settings import settings


STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


class StripeService:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or STRIPE_SECRET_KEY
        if not key:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured")
        stripe.api_key = key

    def create_customer(self, email: str) -> stripe.Customer:
        return stripe.Customer.create(email=email)

    def create_trial_subscription(
        self, customer_id: str, price_id: str, trial_days: int = 14
    ) -> stripe.Subscription:
        price = price_id
        if not price:
            raise RuntimeError("price_id is required to create a trial subscription")

        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price}],
            trial_period_days=trial_days,
        )

    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        return stripe.Subscription.retrieve(subscription_id)

    def customer_has_any_subscription(self, customer_id: str) -> bool:
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="all",
            limit=1,
        )
        return bool(getattr(subscriptions, "data", None))


def compute_trial_end(trial_end_timestamp: Optional[int]) -> Optional[datetime]:
    if not trial_end_timestamp:
        return None
    return datetime.fromtimestamp(trial_end_timestamp, tz=timezone.utc)

