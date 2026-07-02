import os
from pathlib import Path
from typing import Literal, Optional

from cryptography.fernet import Fernet
from decouple import Config, RepositoryEnv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "main.py").exists())
BASE_DIR = PROJECT_ROOT

NLTK_DATA_PATH = PROJECT_ROOT / "nltk_data"
NLTK_DATA_PATH.mkdir(exist_ok=True)

# Determine which env file to load
env_file = os.getenv("ENV_FILE", ".env")
env_path = PROJECT_ROOT / env_file

# Only use RepositoryEnv if the env file exists
if env_path.exists():
    config = Config(RepositoryEnv(env_path))
else:
    # fallback: read directly from os.environ using decouple's AutoConfig
    from decouple import AutoConfig

    config = AutoConfig(search_path=None)


class Settings(BaseSettings):
    # App general
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    APP_NAME: str = config("APP_NAME", default="LEGAL WATCH DOG")
    APP_VERSION: str = config("APP_VERSION", default="1.0.0")
    ENVIRONMENT: str = config("ENVIRONMENT", default="dev")
    APP_PORT: int = config("APP_PORT", default=8000, cast=int)
    SECRET_KEY: str = config("SECRET_KEY", default="your-secret-key-for-sessions")
    LEGAL_WATCH_DOG_BASE_URL: str = config(
        "LEGAL_WATCH_DOG_BASE_URL", default="https://api.legalwatchdog.com"
    )
    APP_URL: str = config("APP_URL", default="https://legalwatchdog.com")
    DEV_URL: str = config("DEV_URL", default="http://localhost:3000")
    ENABLE_REALTIME_WEBSOCKETS: bool = config(
        "ENABLE_REALTIME_WEBSOCKETS", default=False, cast=bool
    )
    REALTIME_WEBSOCKET_PATH: str = config("REALTIME_WEBSOCKET_PATH", default="/ws")
    REALTIME_NOTIFICATIONS_CHANNEL: str = config(
        "REALTIME_NOTIFICATIONS_CHANNEL", default="events:notifications"
    )
    REALTIME_SCRAPE_CHANNEL: str = config("REALTIME_SCRAPE_CHANNEL", default="events:scrape_jobs")
    REALTIME_HEARTBEAT_INTERVAL: int = config("REALTIME_HEARTBEAT_INTERVAL", default=30, cast=int)

    # Socials
    SOCIAL_FACEBOOK: str = config("SOCIAL_FACEBOOK", default="https://facebook.com")
    SOCIAL_TWITTER: str = config("SOCIAL_TWITTER", default="https://twitter.com")
    SOCIAL_INSTAGRAM: str = config("SOCIAL_INSTAGRAM", default="https://instagram.com")
    SOCIAL_LINKEDIN: str = config("SOCIAL_LINKEDIN", default="https://linkedin.com")
    SOCIAL_YOUTUBE: str = config("SOCIAL_YOUTUBE", default="https://youtube.com")

    # Database
    DB_TYPE: str = config("DB_TYPE", default="postgresql")
    DB_HOST: str = config("DB_HOST", default="localhost")
    DB_PORT: int = config("DB_PORT", default=5432, cast=int)
    DB_USER: str = config("DB_USER", default="user")
    DB_PASS: str = config("DB_PASS", default="password")
    DB_NAME: str = config("DB_NAME", default="dbname")
    DATABASE_URL: str = config(
        "DATABASE_URL", default="postgresql://user:password@localhost/dbname"
    )
    DB_SSL: bool = config("DB_SSL", default=True, cast=bool)
    # Database connection pool sizing (critical for shared RDS limits)
    DB_POOL_SIZE: int = config("DB_POOL_SIZE", default=5, cast=int)
    DB_MAX_OVERFLOW: int = config("DB_MAX_OVERFLOW", default=5, cast=int)
    DB_POOL_TIMEOUT: int = config("DB_POOL_TIMEOUT", default=30, cast=int)
    DB_POOL_RECYCLE: int = config("DB_POOL_RECYCLE", default=1800, cast=int)

    # Celery sync DB pool (separate from FastAPI async pool)
    CELERY_DB_POOL_SIZE: int = config("CELERY_DB_POOL_SIZE", default=5, cast=int)
    CELERY_DB_MAX_OVERFLOW: int = config("CELERY_DB_MAX_OVERFLOW", default=5, cast=int)
    CELERY_DB_POOL_TIMEOUT: int = config("CELERY_DB_POOL_TIMEOUT", default=30, cast=int)

    # Redis
    REDIS_URL: str = config("REDIS_URL", default="redis://localhost:6379/0")
    REDIS_RESEND_TTL: int = config("REDIS_RESEND_TTL", default=300, cast=int)
    REDIS_REGISTER_TTL: int = config("REDIS_REGISTER_TTL", default=86400, cast=int)
    REDIS_BROKER_URL: str = config("REDIS_BROKER_URL", default="redis://localhost:6379/0")
    REDIS_BACKEND_URL: str = config("REDIS_BACKEND_URL", default="redis://localhost:6379/1")

    SITEMAP_RELEASE_LOCK_AFTER_RUN: bool = config(
        "SITEMAP_RELEASE_LOCK_AFTER_RUN", default=False, cast=bool
    )

    # JWT Authentication
    JWT_SECRET: str = config("JWT_SECRET", default="your-super-secret-jwt-key-change-in-production")
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    JWT_EXPIRY_HOURS: int = config("JWT_EXPIRY_HOURS", default=24, cast=int)

    # Encryption
    ENCRYPTION_KEY: str = config("ENCRYPTION_KEY", default="YOUR_GENERATED_KEY_HERE")

    # Superadmin Credentials
    SUPERADMIN_EMAIL: str = config("SUPERADMIN_EMAIL", default="admin@example.com")
    SUPERADMIN_PASSWORD: str = config("SUPERADMIN_PASSWORD", default="")

    # Waitlist Email
    MAIL_USERNAME: str = config("MAIL_USERNAME", default="test_user")
    MAIL_PASSWORD: str = config("MAIL_PASSWORD", default="test_pass")
    EMAIL: str = config("EMAIL", default="test@example.com")
    SMTP_SERVER: str = config("SMTP_SERVER", default="smtp.test.com")
    SMTP_PORT: int = config("SMTP_PORT", default=1025, cast=int)
    MAIL_FROM_NAME: str = config("MAIL_FROM_NAME", default="Legal Watch Dog")
    SUPPORT_EMAIL: str = config("SUPPORT_EMAIL", default="hello@legalwatch.dog")

    # Email Verification
    ALLOW_TEST_EMAIL_PROVIDERS: bool = config("ALLOW_TEST_EMAIL_PROVIDERS", default=True, cast=bool)
    TEST_EMAIL_PROVIDERS: str = config("TEST_EMAIL_PROVIDERS", default="gmail.com")

    # Invitation
    INVITATION_TOKEN_EXPIRE_MINUTES: int = config(
        "INVITATION_TOKEN_EXPIRE_MINUTES", default=1440, cast=int
    )

    # MinIO
    # Scraping
    SCRAPE_MAX_RETRIES: int = config("SCRAPE_MAX_RETRIES", default=5, cast=int)
    SCRAPE_BASE_DELAY: int = config("SCRAPE_BASE_DELAY", default=60, cast=int)
    SCRAPE_MAX_DELAY: int = config("SCRAPE_MAX_DELAY", default=3600, cast=int)
    SCRAPE_DISPATCH_LOCK_TIMEOUT: int = config("SCRAPE_DISPATCH_LOCK_TIMEOUT", default=60, cast=int)
    SCRAPE_BATCH_SIZE: int = config("SCRAPE_BATCH_SIZE", default=1000, cast=int)
    SCRAPE_JOB_TIMEOUT_SECONDS: int = config("SCRAPE_JOB_TIMEOUT_SECONDS", default=3600, cast=int)
    JURISDICTION_JOB_TIMEOUT_SECONDS: int = config(
        "JURISDICTION_JOB_TIMEOUT_SECONDS", default=1800, cast=int
    )

    MINIO_ENDPOINT: str = config("MINIO_ENDPOINT", default="localhost:9000")
    MINIO_ACCESS_KEY: str = config("MINIO_ACCESS_KEY", default="lwd")
    MINIO_SECRET_KEY: str = config("MINIO_SECRET_KEY", default="lwd12345")
    MINIO_SECURE: bool = config("MINIO_SECURE", default=False, cast=bool)
    MINIO_USE_SSL: bool = False
    MINIO_PUBLIC_URL: Optional[str] = config("MINIO_PUBLIC_URL", default=None)

    # Main content bucket (environment-specific, private)
    MINIO_BUCKET_OVERRIDE: Optional[str] = config("MINIO_BUCKET_OVERRIDE", default=None)

    # Profile bucket (environment-specific, public)
    MINIO_PROFILE_BUCKET_OVERRIDE: Optional[str] = config(
        "MINIO_PROFILE_BUCKET_OVERRIDE", default=None
    )

    @property
    def MINIO_BUCKET(self) -> str:
        """Get main MinIO bucket name based on environment.

        Content is organized within the bucket using object key prefixes:
        - raw/{jurisdiction_id}/{source_id}/{timestamp}.html
        - clean/{source_id}/{timestamp}_{revision_id}.txt

        This bucket contains scraping content and is private.

        Returns:
            str: Environment-specific bucket name.

        Examples:
            >>> settings.ENVIRONMENT = "production"
            >>> settings.MINIO_BUCKET
            'legalwatch-prod'
            >>> settings.ENVIRONMENT = "staging"
            >>> settings.MINIO_BUCKET
            'legalwatch-staging'
            >>> settings.ENVIRONMENT = "dev"
            >>> settings.MINIO_BUCKET
            'legalwatch'
        """
        if self.MINIO_BUCKET_OVERRIDE:
            return self.MINIO_BUCKET_OVERRIDE
        if self.ENVIRONMENT == "dev":
            return "legalwatch"
        env = "prod" if self.ENVIRONMENT == "production" else self.ENVIRONMENT
        return f"legalwatch-{env}"

    @property
    def MINIO_PROFILE_BUCKET(self) -> str:
        """Get profile picture bucket name based on environment.

        Profile pictures are stored with object key format: profile-pictures/{user_id}/{uuid}.jpg
        This uses the same bucket as MINIO_BUCKET with a profile-pictures subfolder.

        Returns:
            str: Environment-specific bucket name (same as MINIO_BUCKET).

        Examples:
            >>> settings.ENVIRONMENT = "production"
            >>> settings.MINIO_PROFILE_BUCKET
            'legalwatch-prod'
            >>> settings.ENVIRONMENT = "staging"
            >>> settings.MINIO_PROFILE_BUCKET
            'legalwatch-staging'
            >>> settings.ENVIRONMENT = "dev"
            >>> settings.MINIO_PROFILE_BUCKET
            'legalwatch'
        """
        if self.MINIO_PROFILE_BUCKET_OVERRIDE:
            return self.MINIO_PROFILE_BUCKET_OVERRIDE
        return self.MINIO_BUCKET

    # gemini AI Service
    GEMINI_API_KEY: str = config("GEMINI_API_KEY", default="your-gemini-api-key")
    TAVILY_API_KEY: str = config("TAVILY_API_KEY", default="your-tavily-api-key")
    PARALLEL_API_KEY: str = config("PARALLEL_API_KEY", default="your-parallel-api-key")
    MODEL_NAME: str = config("MODEL_NAME", default="gemini-2.0-flash-lite")

    # LLM Configuration
    LLM_API_KEY: str = config("LLM_API_KEY", default="your-llm-api-key")
    LLM_MODEL: str = config("LLM_MODEL", default="gemini-2.0-flash")
    LLM_API_URL: str = config("LLM_API_URL", default="")
    LLM_PROVIDER: str = config("LLM_PROVIDER", default="gemini")
    LLM_TEMPERATURE: float = config("LLM_TEMPERATURE", default=0.1, cast=float)
    LLM_MAX_TOKENS: int = config("LLM_MAX_TOKENS", default=1000, cast=int)
    LLM_SYSTEM_PROMPT: str = config(
        "LLM_SYSTEM_PROMPT", default="You are a data extraction specialist..."
    )

    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = config("OPENROUTER_API_KEY", default="your-openrouter-api-key")
    OPENROUTER_DEFAULT_MODEL: str = config(
        "OPENROUTER_DEFAULT_MODEL", default="google/gemini-3-flash-preview"
    )
    OPENROUTER_FALLBACK_MODELS: str = config(
        "OPENROUTER_FALLBACK_MODELS",
        default="google/gemini-2.5-flash-lite,deepseek/deepseek-v3.2",
    )
    OPENROUTER_SITE_URL: str = config("OPENROUTER_SITE_URL", default="https://legalwatchdog.com")
    OPENROUTER_SITE_NAME: str = config("OPENROUTER_SITE_NAME", default="Legal Watch Dog")
    OPENROUTER_TIMEOUT: int = config("OPENROUTER_TIMEOUT", default=120, cast=int)
    OPENROUTER_ENABLE_ROUTING: bool = config("OPENROUTER_ENABLE_ROUTING", default=True, cast=bool)
    OPENROUTER_ENABLE_FALLBACK: bool = config("OPENROUTER_ENABLE_FALLBACK", default=True, cast=bool)
    OPENROUTER_ENABLE_USAGE_TRACKING: bool = config(
        "OPENROUTER_ENABLE_USAGE_TRACKING", default=True, cast=bool
    )

    # Dev environment auto-selection (free model)
    OPENROUTER_DEV_MODEL: str = config("OPENROUTER_DEV_MODEL", default="xiaomi/mimo-v2-flash")
    OPENROUTER_ENABLE_DEV_AUTO_FREE: bool = config(
        "OPENROUTER_ENABLE_DEV_AUTO_FREE", default=True, cast=bool
    )

    @property
    def OPENROUTER_FALLBACK_MODEL_LIST(self) -> list[str]:
        """Parse comma-separated fallback models into list.

        Returns:
            list[str]: List of fallback model identifiers.

        Examples:
            >>> settings.OPENROUTER_FALLBACK_MODEL_LIST
            ['meta-llama/llama-3.1-405b-instruct', 'mistralai/mistral-large-2407']
        """
        return [m.strip() for m in self.OPENROUTER_FALLBACK_MODELS.split(",") if m.strip()]

    # Stripe configuration
    STRIPE_SECRET_KEY: str = config("STRIPE_SECRET_KEY", default="sk_test_...")
    STRIPE_PUBLISHABLE_KEY: str = config("STRIPE_PUBLISHABLE_KEY", default="pk_test_...")
    STRIPE_WEBHOOK_SECRET: str = config("STRIPE_WEBHOOK_SECRET", default="whsec_...")
    STRIPE_API_TIMEOUT: int = config("STRIPE_API_TIMEOUT", default=30, cast=int)
    STRIPE_RETRY_COUNT: int = config("STRIPE_RETRY_COUNT", default=3, cast=int)
    STRIPE_RETRY_BACKOFF: float = config("STRIPE_RETRY_BACKOFF", default=0.5, cast=float)

    STRIPE_INVOICE_DURATION_DAYS: int = config("STRIPE_INVOICE_DURATION_DAYS", default=3, cast=int)
    STRIPE_CHECKOUT_SUCCESS_PATH: str = config(
        "STRIPE_CHECKOUT_SUCCESS_PATH", default="/billing/success"
    )
    STRIPE_CHECKOUT_CANCEL_PATH: str = config(
        "STRIPE_CHECKOUT_CANCEL_PATH", default="/billing/cancel"
    )

    # Stripe prices & product/price IDs
    ESSENTIAL_MONTHLY_PRICE_USD: int = config("ESSENTIAL_MONTHLY_PRICE_USD", default=2900, cast=int)
    ESSENTIAL_YEARLY_PRICE_USD: int = config("ESSENTIAL_YEARLY_PRICE_USD", default=27840, cast=int)

    PRO_MONTHLY_PRICE_USD: int = config("PRO_MONTHLY_PRICE_USD", default=7900, cast=int)
    PRO_YEARLY_PRICE_USD: int = config("PRO_YEARLY_PRICE_USD", default=75840, cast=int)

    ENTERPRISE_MONTHLY_PRICE_USD: int = config(
        "ENTERPRISE_MONTHLY_PRICE_USD", default=9900, cast=int
    )
    ENTERPRISE_YEARLY_PRICE_USD: int = config(
        "ENTERPRISE_YEARLY_PRICE_USD", default=95040, cast=int
    )

    STRIPE_ESSENTIAL_MONTHLY_PRODUCT_ID: str = config(
        "STRIPE_ESSENTIAL_MONTHLY_PRODUCT_ID", default="prod_monthly_123"
    )
    STRIPE_ESSENTIAL_MONTHLY_PRICE_ID: str = config(
        "STRIPE_ESSENTIAL_MONTHLY_PRICE_ID", default="price_monthly_id"
    )

    STRIPE_ESSENTIAL_YEARLY_PRODUCT_ID: str = config(
        "STRIPE_ESSENTIAL_YEARLY_PRODUCT_ID", default="prod_yearly_123"
    )
    STRIPE_ESSENTIAL_YEARLY_PRICE_ID: str = config(
        "STRIPE_ESSENTIAL_YEARLY_PRICE_ID", default="price_yearly_id"
    )

    STRIPE_PRO_MONTHLY_PRODUCT_ID: str = config(
        "STRIPE_PRO_MONTHLY_PRODUCT_ID", default="prod_pro_monthly_123"
    )
    STRIPE_PRO_MONTHLY_PRICE_ID: str = config(
        "STRIPE_PRO_MONTHLY_PRICE_ID", default="price_pro_monthly_id"
    )

    STRIPE_PRO_YEARLY_PRODUCT_ID: str = config(
        "STRIPE_PRO_YEARLY_PRODUCT_ID", default="prod_pro_yearly_123"
    )
    STRIPE_PRO_YEARLY_PRICE_ID: str = config(
        "STRIPE_PRO_YEARLY_PRICE_ID", default="price_pro_yearly_id"
    )

    STRIPE_ENTERPRISE_MONTHLY_PRODUCT_ID: str = config(
        "STRIPE_ENTERPRISE_MONTHLY_PRODUCT_ID", default="prod_enterprise_monthly_123"
    )
    STRIPE_ENTERPRISE_MONTHLY_PRICE_ID: str = config(
        "STRIPE_ENTERPRISE_MONTHLY_PRICE_ID", default="price_enterprise_monthly_id"
    )

    STRIPE_ENTERPRISE_YEARLY_PRODUCT_ID: str = config(
        "STRIPE_ENTERPRISE_YEARLY_PRODUCT_ID", default="prod_enterprise_yearly_123"
    )
    STRIPE_ENTERPRISE_YEARLY_PRICE_ID: str = config(
        "STRIPE_ENTERPRISE_YEARLY_PRICE_ID", default="price_enterprise_yearly_id"
    )

    # Blog artifact publishing
    BLOG_STATIC_DIR: str = config("BLOG_STATIC_DIR", default="/var/www/blog-static")
    BLOG_CSS_URL: str = config("BLOG_CSS_URL", default="/assets/blog/blog.v1.css")
    BLOG_SITE_NAME: str = config("BLOG_SITE_NAME", default="LegalWatch")
    BLOG_SITE_URL: str = config("BLOG_SITE_URL", default="https://legalwatch.dog")
    BLOG_PUBLISH_ARTIFACTS: bool = config("BLOG_PUBLISH_ARTIFACTS", default=True, cast=bool)

    # Frontend URL (for Stripe redirects and notifications)
    @property
    def FRONTEND_URL(self) -> str:
        frontend_url = config("FRONTEND_URL", default="")
        if frontend_url:
            return frontend_url
        return self.DEV_URL if self.DEBUG else self.APP_URL

    @property
    def STRIPE_CHECKOUT_SUCCESS_URL(self) -> str:
        return f"{self.FRONTEND_URL}{self.STRIPE_CHECKOUT_SUCCESS_PATH}"

    @property
    def STRIPE_CHECKOUT_CANCEL_URL(self) -> str:
        return f"{self.FRONTEND_URL}{self.STRIPE_CHECKOUT_CANCEL_PATH}"

    @property
    def REALTIME_CHANNEL_MAP(self) -> dict[str, str]:
        """Return topic to Redis channel mapping for realtime delivery.

        Returns:
            dict[str, str]: Mapping consumed by event publisher/subscribers.

        Examples:
            >>> settings.REALTIME_CHANNEL_MAP["notifications"]
            'events:notifications'
        """

        return {
            "notifications": self.REALTIME_NOTIFICATIONS_CHANNEL,
            "scrape_jobs": self.REALTIME_SCRAPE_CHANNEL,
        }

    # Billing Configuration
    TRIAL_DURATION_DAYS: int = config("TRIAL_DURATION_DAYS", default=14, cast=int)

    # Plan limits
    ESSENTIAL_MAX_PROJECTS: int = config("ESSENTIAL_MAX_PROJECTS", default=1, cast=int)
    ESSENTIAL_MAX_JURISDICTIONS: int = config("ESSENTIAL_MAX_JURISDICTIONS", default=2, cast=int)
    ESSENTIAL_MONTHLY_SCANS: int = config("ESSENTIAL_MONTHLY_SCANS", default=20, cast=int)

    PRO_MAX_PROJECTS: int = config("PRO_MAX_PROJECTS", default=20, cast=int)
    PRO_MAX_JURISDICTIONS: int = config("PRO_MAX_JURISDICTIONS", default=50, cast=int)
    PRO_MONTHLY_SCANS: int = config("PRO_MONTHLY_SCANS", default=-1, cast=int)

    ENTERPRISE_MAX_PROJECTS: int = config("ENTERPRISE_MAX_PROJECTS", default=-1, cast=int)
    ENTERPRISE_MAX_JURISDICTIONS: int = config("ENTERPRISE_MAX_JURISDICTIONS", default=-1, cast=int)
    ENTERPRISE_MONTHLY_SCANS: int = config("ENTERPRISE_MONTHLY_SCANS", default=-1, cast=int)

    MICROSOFT_REDIRECT_URI: str = config(
        "MICROSOFT_REDIRECT_URI", default="https://minamoto.emerj.net"
    )
    MICROSOFT_TENANT_ID: str = config("MICROSOFT_TENANT_ID", default="tenant-id")
    MICROSOFT_CLIENT_SECRET: str = config("MICROSOFT_CLIENT_SECRET", default="client-secret")
    MICROSOFT_CLIENT_ID: str = config("MICROSOFT_CLIENT_ID", default="client-id")
    MICROSOFT_USERINFO_ENDPOINT: str = config("MICROSOFT_USERINFO_ENDPOINT", default="user-info")

    MICROSOFT_SCOPES: list[str] = Field(
        default_factory=lambda: ["https://graph.microsoft.com/User.Read"]
    )

    MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL: str = config(
        "MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL", default="https://minamoto.emerj.net/app"
    )
    MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL: str = config(
        "MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL", default="https://minamoto.emerj.net/app"
    )
    MICROSOFT_OAUTH_STATE_TTL: int = config("MICROSOFT_OAUTH_STATE_TTL", default=900, cast=int)

    # Google OAuth
    GOOGLE_CLIENT_ID: str = config("GOOGLE_CLIENT_ID", default="your-google-client-id")
    GOOGLE_CLIENT_SECRET: str = config("GOOGLE_CLIENT_SECRET", default="your-google-client-secret")
    GOOGLE_REDIRECT_URI: str = config(
        "GOOGLE_REDIRECT_URI", default="https://minamoto.emerj.net/api/v1/oauth/google/callback"
    )

    ADMIN_EMAIL: str = config("ADMIN_EMAIL", default="user@organization.com")
    DEMO_REQUEST_NOTIFICATION_EMAIL: str = config(
        "DEMO_REQUEST_NOTIFICATION_EMAIL", default="hello@legalwatch.dog"
    )

    # Apple OAuth
    APPLE_TEAM_ID: str = config("APPLE_TEAM_ID", default="your-apple-developer-team-id")
    APPLE_CLIENT_ID: str = config("APPLE_CLIENT_ID", default="your-apple-developer-client-id")
    APPLE_KEY_ID: str = config("APPLE_KEY_ID", default="your-apple-developer-key-identifier")
    APPLE_PRIVATE_KEY: str = config(
        "APPLE_PRIVATE_KEY", default="your-app-private-key-apple-developer"
    )
    APPLE_CLIENT_SECRET_LIFETIME: int = config(
        "APPLE_CLIENT_SECRET_LIFETIME", default=21600, cast=int
    )
    APPLE_REDIRECT_URI: str = config(
        "APPLE_REDIRECT_URI", default="http://localhost:8000/auth/apple/callback"
    )

    # API_ACCESS_KEY
    API_KEY_MAX_EXPIRATION_DAYS: int = config("API_KEY_MAX_EXPIRATION_DAYS", default=60, cast=int)
    API_KEY_DEFAULT_EXPIRATION_DAYS: int = config(
        "API_KEY_DEFAULT_EXPIRATION_DAYS", default=15, cast=int
    )
    API_KEY_FRONTEND_URL: str = config("API_KEY_FRONTEND_URL", default="legalwatch.dog/keys/view")
    API_KEY_ROTATION_WINDOW_DAYS: int = config("API_KEY_ROTATION_WINDOW_DAYS", default=3, cast=int)
    WEB_SECRET_KEY: str = config("WEB_SECRET_KEY", default="your-web-header")

    # Automated Source search redis ttl
    SEARCH_SESSION_TTL: int = config("SEARCH_SESSION_TTL", default=1800, cast=int)

    # OAuth Configuration
    OAUTH_DEFAULT_CLIENT: str = config("OAUTH_DEFAULT_CLIENT", default="production")
    OAUTH_CLIENT_FRONTEND_MAP: dict[str, str] = {
        "local": config("OAUTH_FRONTEND_LOCAL_URL", default="http://localhost:3000"),
        "staging": config("OAUTH_FRONTEND_STAGING_URL", default="https://staging.legalwatch.dog"),
        "production": config("OAUTH_FRONTEND_PRODUCTION_URL", default="https://legalwatch.dog"),
    }

    @property
    def OAUTH_ALLOWED_CLIENTS(self) -> set[str]:
        return set(self.OAUTH_CLIENT_FRONTEND_MAP.keys())

    # Campaign Module
    CAMPAIGN_PIPELINE_BACKEND: Literal["celery", "langgraph"] = config(
        "CAMPAIGN_PIPELINE_BACKEND", default="celery"
    )  # type: ignore[assignment]
    CAMPAIGN_MAX_PIPELINE_HISTORY: int = config(
        "CAMPAIGN_MAX_PIPELINE_HISTORY", default=5, cast=int
    )
    CAMPAIGN_ZOMBIE_DETECTION_THRESHOLD_SECONDS: int = config(
        "CAMPAIGN_ZOMBIE_DETECTION_THRESHOLD_SECONDS", default=7200, cast=int
    )
    CAMPAIGN_AI_ROLLOUT_ENABLED: bool = config(
        "CAMPAIGN_AI_ROLLOUT_ENABLED", default=False, cast=bool
    )
    CAMPAIGN_AI_PLANNER_BACKEND: Literal["none", "shadow", "active"] = config(
        "CAMPAIGN_AI_PLANNER_BACKEND", default="none"
    )  # type: ignore[assignment]
    CAMPAIGN_AI_TOOL_POLICY_MODE: Literal["off", "allowlist", "strict"] = config(
        "CAMPAIGN_AI_TOOL_POLICY_MODE", default="off"
    )  # type: ignore[assignment]
    CAMPAIGN_AI_MAX_TOOL_CALLS_PER_JURISDICTION: int = config(
        "CAMPAIGN_AI_MAX_TOOL_CALLS_PER_JURISDICTION", default=3, cast=int
    )
    CAMPAIGN_AI_TOOL_CALL_TIMEOUT_SECONDS: int = config(
        "CAMPAIGN_AI_TOOL_CALL_TIMEOUT_SECONDS", default=20, cast=int
    )
    CAMPAIGN_SEARCH_RATE_LIMIT: int = config("CAMPAIGN_SEARCH_RATE_LIMIT", default=25, cast=int)
    CAMPAIGN_SOURCE_DISCOVERY_CONCURRENCY: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_CONCURRENCY", default=5, cast=int
    )
    CAMPAIGN_SOURCE_DISCOVERY_MAX_FALLBACK_QUERIES: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_MAX_FALLBACK_QUERIES", default=2, cast=int
    )
    CAMPAIGN_SOURCE_DISCOVERY_INTER_JURISDICTION_DELAY_SECONDS: float = config(
        "CAMPAIGN_SOURCE_DISCOVERY_INTER_JURISDICTION_DELAY_SECONDS",
        default=0.5,
        cast=float,
    )
    CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_RETRIES: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_RETRIES", default=3, cast=int
    )
    CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_BACKOFF_SECONDS: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_BACKOFF_SECONDS", default=8, cast=int
    )
    CAMPAIGN_SOURCE_DISCOVERY_SOFT_TIME_LIMIT_SECONDS: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_SOFT_TIME_LIMIT_SECONDS", default=5400, cast=int
    )
    CAMPAIGN_SOURCE_DISCOVERY_HARD_TIME_LIMIT_SECONDS: int = config(
        "CAMPAIGN_SOURCE_DISCOVERY_HARD_TIME_LIMIT_SECONDS", default=6000, cast=int
    )
    CAMPAIGN_TAXONOMY_SOFT_TIME_LIMIT_SECONDS: int = config(
        "CAMPAIGN_TAXONOMY_SOFT_TIME_LIMIT_SECONDS", default=1800, cast=int
    )
    CAMPAIGN_TAXONOMY_HARD_TIME_LIMIT_SECONDS: int = config(
        "CAMPAIGN_TAXONOMY_HARD_TIME_LIMIT_SECONDS", default=2100, cast=int
    )
    CAMPAIGN_FORCE_FAIL_AFTER_RETRIES: int = config(
        "CAMPAIGN_FORCE_FAIL_AFTER_RETRIES", default=60, cast=int
    )
    CAMPAIGN_TAXONOMY_MAX_TOKENS: int = config(
        "CAMPAIGN_TAXONOMY_MAX_TOKENS", default=24000, cast=int
    )
    CAMPAIGN_TAXONOMY_TEMPERATURE: float = config(
        "CAMPAIGN_TAXONOMY_TEMPERATURE", default=0.3, cast=float
    )
    CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE: bool = config(
        "CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE", default=True, cast=bool
    )
    CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY: int = config(
        "CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY", default=180, cast=int
    )
    CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE: int = config(
        "CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE", default=180, cast=int
    )
    CAMPAIGN_TAXONOMY_STRICT_TRUNCATION: bool = config(
        "CAMPAIGN_TAXONOMY_STRICT_TRUNCATION", default=True, cast=bool
    )
    CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES: bool = config(
        "CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES", default=True, cast=bool
    )
    CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES: bool = config(
        "CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES", default=True, cast=bool
    )
    CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH: str = config(
        "CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH", default=""
    )
    CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED: bool = config(
        "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED", default=False, cast=bool
    )
    CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH: str = config(
        "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH", default=""
    )
    CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES: str = config(
        "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES",
        default=(
            "state,province,region,county,district,governorate,prefecture,"
            "municipality,canton,department,territory,union territory"
        ),
    )
    CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED: bool = config(
        "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED", default=False, cast=bool
    )
    CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH: str = config(
        "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH", default=""
    )
    CAMPAIGN_TAXONOMY_EXPANSION_ENABLED: bool = config(
        "CAMPAIGN_TAXONOMY_EXPANSION_ENABLED", default=True, cast=bool
    )
    CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES: int = config(
        "CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES", default=2, cast=int
    )
    CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE: int = config(
        "CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE", default=40, cast=int
    )
    CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS: int = config(
        "CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS", default=12000, cast=int
    )

    # Scraping concurrency
    CONSOLIDATION_MINIO_FETCH_CONCURRENCY: int = config(
        "CONSOLIDATION_MINIO_FETCH_CONCURRENCY", default=5, cast=int
    )
    CONSOLIDATION_LLM_FILTER_CONCURRENCY: int = config(
        "CONSOLIDATION_LLM_FILTER_CONCURRENCY", default=3, cast=int
    )

    # SITEMAP
    MAX_URLS_PER_SITEMAP: int = config("MAX_URLS_PER_SITEMAP", default=50_000)

    model_config = SettingsConfigDict(extra="allow")


settings = Settings()


# Lazy load encryption cipher suite to avoid import-time initialization
def get_cipher_suite():
    return Fernet(settings.ENCRYPTION_KEY)


# For backward compatibility, provide cipher_suite as a module-level variable
# This will be initialized on first access
cipher_suite = None
