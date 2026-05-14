#!/usr/bin/env python3
"""
Render Jinja2 email templates locally for testing/preview.

Usage:
    python tools/render_email_template.py <template_filename> <output.html>

Example:
    python tools/render_email_template.py revision_notification.html out.html
    # Then open out.html in your browser
"""

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def make_env(templates_path: Path):
    """Create a Jinja2 environment configured for email templates."""
    from datetime import datetime

    loader = FileSystemLoader(str(templates_path))
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Set globals that templates expect
    # Adjust these URLs to match your deployment or testing needs
    env.globals["API_URL"] = "https://minio.legalwatch.dog/email-templates"
    env.globals["FRONTEND_URL"] = "https://staging.legalwatch.dog"
    # current_year is called as a function in templates
    env.globals["current_year"] = lambda: datetime.now().year

    return env


def sample_context():
    """
    Provide sample context data for template rendering.

    Adjust this dictionary to match the variables used in your templates.
    Check the template file to see what variables it expects.
    """
    return {
        # Common variables
        "username": "Alicia",
        "recipient_name": "John Doe",
        "user_name": "John Doe",
        "email": "test@example.com",
        "support_email": "support@legalwatchdog.com",
        # Project-related
        "project_name": "Sample Legal Project",
        "project_id": "123",
        # Revision notification specific
        "revision": {
            "id": "456",
            "title": "Important Policy Update",
            "summary": "This revision updates the terms of service to reflect new regulations.",
            "content": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "author_name": "Alice Smith",
            "created_at": "2026-01-07 10:30:00",
        },
        # Links and CTAs
        "cta_url": "https://staging.legalwatch.dog/projects/123/revisions/456",
        "dashboard_url": "https://staging.legalwatch.dog/app",
        "reset_link": "https://staging.legalwatch.dog/reset-password?token=sample_token",
        "verification_link": "https://staging.legalwatch.dog/verify?token=sample_token",
        # OTP
        "otp": "123456",
        # Invitation
        "organization_name": "Sample Legal Firm",
        "role_name": "Viewer",
        "inviter_name": "Bob Manager",
        # Contact/Support
        "subject": "Need help with my account",
        "message": "I'm having trouble accessing my dashboard.",
        "ticket_id": "TICKET-789",
        # Waitlist
        "position": 42,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    template_name = sys.argv[1]
    out_file = Path(sys.argv[2])

    # Find templates directory relative to this script
    repo_root = Path(__file__).resolve().parents[1]
    templates_dir = repo_root / "app" / "api" / "core" / "dependencies" / "email" / "templates"

    if not templates_dir.exists():
        print(f"Error: Templates directory not found at {templates_dir}")
        sys.exit(1)

    template_file = templates_dir / template_name
    if not template_file.exists():
        print(f"Error: Template '{template_name}' not found in {templates_dir}")
        print("\nAvailable templates:")
        for tmpl in sorted(templates_dir.glob("*.html")):
            print(f"  - {tmpl.name}")
        sys.exit(1)

    # Create Jinja environment and render
    env = make_env(templates_dir)
    ctx = sample_context()

    try:
        tmpl = env.get_template(template_name)
        rendered = tmpl.render(**ctx)

        out_file.write_text(rendered, encoding="utf-8")
        print(f"✓ Rendered template to: {out_file.absolute()}")
        print("\nOpen in browser:")
        print(f"  Windows: start {out_file.absolute()}")
        print(f"  macOS:   open {out_file.absolute()}")
        print(f"  Linux:   xdg-open {out_file.absolute()}")

    except Exception as e:
        print(f"Error rendering template: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
