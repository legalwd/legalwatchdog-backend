class SubscriptionAlreadyCanceledError(Exception):
    """Raised when trying to modify a canceled Stripe subscription."""

    pass
