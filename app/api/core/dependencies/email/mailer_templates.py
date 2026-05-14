from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.api.core.config import BASE_DIR, settings

TEMPLATE_DIR = Path(BASE_DIR) / "app/api/core/dependencies/email/templates"
email_templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

email_templates.env.globals["SOCIAL_FACEBOOK"] = settings.SOCIAL_FACEBOOK
email_templates.env.globals["SOCIAL_TWITTER"] = settings.SOCIAL_TWITTER
email_templates.env.globals["SOCIAL_INSTAGRAM"] = settings.SOCIAL_INSTAGRAM
email_templates.env.globals["SOCIAL_LINKEDIN"] = settings.SOCIAL_LINKEDIN
email_templates.env.globals["SOCIAL_YOUTUBE"] = settings.SOCIAL_YOUTUBE
email_templates.env.globals["current_year"] = lambda: datetime.now().year
email_templates.env.globals["APP_URL"] = settings.APP_URL
email_templates.env.globals["APP_NAME"] = settings.APP_NAME
