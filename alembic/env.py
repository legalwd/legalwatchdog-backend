from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.api.core.config import BASE_DIR, settings
from app.api.db.database import Base
from app.api.db.models.llm_usage import LLMUsageLog, LLMProviderStatus
from app.api.db.models.parallel_usage import ParallelUsageLog
from app.api.modules.v1.auth.models.otp_model import OTP
from app.api.modules.v1.auth.models.oauth_models import (
    RefreshTokenMetadata,
    OAuthLoginEvent,
)
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.models.invoice_history import InvoiceHistory
from app.api.modules.v1.billing.models.payment_method import PaymentMethod
from app.api.modules.v1.billing.models.billing_plan import BillingPlan
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import (
    UserOrganization,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.scraping.models.source_model import Source, SourceType
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.field_mapping import FieldMapping
from app.api.modules.v1.contact_us.models.contact_us_model import ContactUs
from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.notifications.models.revision_notification import Notification
from app.api.modules.v1.api_access.models.api_key_model import APIKey
from app.api.modules.v1.api_access.models.api_key_token import APIKeyOnboardingToken
from app.api.modules.v1.tickets.models.ticket_model import (
    Ticket,
    ExternalParticipant,
    TicketStatus,
)
from app.api.modules.v1.tickets.models.comment_model import Comment
from app.api.modules.v1.jurisdictions.models.jurisdiction_state import (
    JurisdictionState,
    JurisdictionStateHistory,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import (
    JurisdictionBlogPost,
    BlogPostToken
)
from app.api.modules.v1.jurisdictions.models.blog_generation_job import (
    BlogGenerationJob,
    BlogGenerationJobStatus,
)


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the URL from your application settings
# This ensures migrations use the same database as your application
if hasattr(settings, "DATABASE_URL") and settings.DATABASE_URL:
    db_url = settings.DATABASE_URL
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.split("?")[0]  # Strip query params to avoid configparser interpolation issues
elif settings.DB_TYPE == "postgresql":
    db_url = (
        f"postgresql://{settings.DB_USER}:{settings.DB_PASS}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
else:
    db_url = f"sqlite:///{BASE_DIR}/db.sqlite3"

# Override the URL in the Alembic config
config.set_main_option("sqlalchemy.url", db_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
