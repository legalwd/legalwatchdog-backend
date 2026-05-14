"""Test email sending directly."""

import asyncio

from app.api.core.dependencies.send_mail import send_email


async def test_email():
    print("🔧 Testing email sending...")
    print()

    try:
        await send_email(
            template_name="internal_user_ticket_notification.html",
            subject="Test: Ticket Invitation",
            recipient="oshinsamuel0@gmail.com",
            context={
                "recipient_name": "Test User",
                "invited_by_name": "Admin User",
                "organization_name": "Test Organization",
                "ticket_title": "Test Ticket",
                "ticket_description": "This is a test ticket invitation",
                "ticket_priority": "high",
                "ticket_status": "open",
                "project_name": "Test Project",
                "ticket_link": "http://localhost:3000/tickets/test-123",
                "is_internal": True,
            },
        )
        print("✅ Email sent successfully!")
        print("Check your inbox at: oshinsamuel0@gmail.com")
        print("(Also check spam folder)")

    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_email())
