import re

from pydantic import BaseModel, EmailStr, field_validator

# Common disposable/temporary email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "temp-mail.org",
    "throwaway.email",
    "maildrop.cc",
    "tempmail.com",
    "getnada.com",
    "trashmail.com",
    "sharklasers.com",
    "grr.la",
    "guerrillamailblock.com",
    "pokemail.net",
    "spam4.me",
    "mailnesia.com",
    "mailcatch.com",
    "yopmail.com",
    "fakeinbox.com",
    "throwawaymail.com",
    "mintemail.com",
}


class WaitlistSignup(BaseModel):
    organization_email: EmailStr
    organization_name: str

    @field_validator("organization_name")
    @classmethod
    def validate_organization_name(cls, value: str) -> str:
        """
        Validate that Name contains only letters, spaces, and common punctuation.
        Numbers are not allowed.
        """
        if not value or not value.strip():
            raise ValueError("Name cannot be empty")

        value = value.strip()

        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters long")

        if len(value) > 100:
            raise ValueError("Name cannot exceed 100 characters")

        if any(char.isdigit() for char in value):
            raise ValueError("Name cannot contain numbers")

        if not any(char.isalpha() for char in value):
            raise ValueError("Name must contain at least one letter")

        # Check for excessive consecutive spaces or punctuation
        if re.search(r"\s{2,}", value):
            raise ValueError("Name cannot contain excessive consecutive spaces")

        if re.search(r"[.,&\-']{2,}", value):
            raise ValueError("Name cannot contain consecutive punctuation marks")

        if re.match(r"^[.,&\-']", value):
            raise ValueError("Name cannot start with punctuation")

        if re.search(r"[.,&\-']$", value):
            raise ValueError("Name cannot end with punctuation")

        allowed_pattern = re.compile(r"^[a-zA-Z\s\-'.,&]+$")
        if not allowed_pattern.match(value):
            raise ValueError(
                "Name can only contain letters, spaces, and common punctuation (-, ', ., ,, &)"
            )

        return value

    @field_validator("organization_email")
    @classmethod
    def validate_organization_email(cls, value: EmailStr) -> EmailStr:
        """
        Additional validation for email to ensure it's not a dummy/invalid/disposable email.
        EmailStr already validates basic email format.
        """
        email_str = str(value).lower().strip()

        dummy_patterns = [
            r"^test@test\.",
            r"^dummy@",
            r"^fake@",
            r"^example@example\.",
            r"^noreply@noreply\.",
            r"@example\.com$",
            r"@test\.com$",
            r"@dummy\.com$",
        ]

        for pattern in dummy_patterns:
            if re.search(pattern, email_str):
                raise ValueError(
                    "Please provide a valid organization email address.\n"
                    "Test/dummy emails are not accepted."
                )

        domain = email_str.split("@")[1]
        if domain in DISPOSABLE_DOMAINS:
            raise ValueError(
                "Disposable or temporary email addresses are not accepted.\n"
                "Please use a valid organization email."
            )

        if len(email_str) > 254:
            raise ValueError("Email address is too long")

        if "@" not in email_str or email_str.count("@") != 1:
            raise ValueError("Email must contain exactly one @ symbol")

        local_part, domain_part = email_str.split("@")

        if not local_part or len(local_part) > 64:
            raise ValueError("Invalid email format")

        if not domain_part or len(domain_part) < 3 or "." not in domain_part:
            raise ValueError("Email must have a valid domain (e.g., company.com)")

        return value


class WaitlistResponse(BaseModel):
    organization_email: str
    organization_name: str
