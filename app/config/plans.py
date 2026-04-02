# app/config/plans.py

PLANS = {
    "starter_99": {
        "monthly_usage_baseline": 25,
        "features": {
            "pdf": True,
            "branding": False,
            "whitelabel": False,
        },
    },
    "pro_199": {
        # Unlimited offers across all plans; no volume-based differentiation.
        "monthly_usage_baseline": None,
        "features": {
            "pdf": True,
            "branding": True,
            "whitelabel": False,
        },
    },
    "business_399": {
        # Unlimited offers across all plans; no volume-based differentiation.
        "monthly_usage_baseline": None,
        "features": {
            "pdf": True,
            "branding": True,
            "whitelabel": True,
        },
    },
}
