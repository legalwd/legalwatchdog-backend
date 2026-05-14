import random


def generate_code() -> str:
    """
    Generate a 6-digit numeric OTP code.

    Returns:
        str: 6-digit OTP code

    Example:
        >>> OTP.generate_code()
        '842756'
    """
    return "".join([str(random.randint(0, 9)) for _ in range(6)])
