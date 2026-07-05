"""
Celery queue name constants resolved from application settings.

Import these constants throughout the codebase instead of using hardcoded
string literals to ensure every environment (dev / staging / prod) routes
tasks to the correct, isolated queues.

Usage::

    from app.api.core.queues import SCRAPING_QUEUE, PROCESSING_QUEUE, PERSISTENCE_QUEUE

    @celery_app.task(bind=True, queue=PROCESSING_QUEUE)
    def my_task(self): ...

    my_task.apply_async(args=[...], queue=SCRAPING_QUEUE)

Configuration (via .env)::

    CELERY_SCRAPING_QUEUE=scraping-staging
    CELERY_PROCESSING_QUEUE=processing-staging
    CELERY_PERSISTENCE_QUEUE=persistence-staging
"""

from app.api.core.config import settings

SCRAPING_QUEUE: str = settings.CELERY_SCRAPING_QUEUE
PROCESSING_QUEUE: str = settings.CELERY_PROCESSING_QUEUE
PERSISTENCE_QUEUE: str = settings.CELERY_PERSISTENCE_QUEUE
