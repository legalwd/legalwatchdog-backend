import re

from app.api.utils.generate_otp import generate_code


def test_generate_code_length():
    """OTP must always be 6 characters long."""
    code = generate_code()
    assert len(code) == 6


def test_generate_code_digits_only():
    """OTP must contain digits only."""
    code = generate_code()
    assert code.isdigit()


def test_generate_code_format():
    """OTP must match a 6-digit regex pattern."""
    code = generate_code()
    assert re.fullmatch(r"\d{6}", code)


def test_generate_code_randomness():
    """Two consecutive OTPs should not be the same."""
    code1 = generate_code()
    code2 = generate_code()
    assert code1 != code2


def test_generate_code_type():
    """Function must return string."""
    code = generate_code()
    assert isinstance(code, str)
