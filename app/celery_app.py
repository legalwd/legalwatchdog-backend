from celery import Celery
from celery.schedules import crontab

from app.api.core.config import settings
from app.api.core.queues import PERSISTENCE_QUEUE, PROCESSING_QUEUE, SCRAPING_QUEUE

celery_app = Celery(
    "legal_watch_dog",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BACKEND_URL,
)

celery_app.set_default()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
    task_time_limit=600,
    task_soft_time_limit=550,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    imports=[
        "app.api.modules.v1.campaigns.tasks.campaign_tasks",
        "app.api.modules.v1.scraping.service.tasks",
        "app.api.modules.v1.notifications.service.revision_notification_task",
        "app.api.modules.v1.notifications.service.participant_notification_task",
        "app.api.modules.v1.api_access.service.rotation_tasks",
        # "app.api.modules.v1.billing.tasks",  # TODO: billing not yet implemented
        "app.api.modules.v1.jurisdictions.service.sitemap_tasks",
    ],
    task_routes={
        "app.api.modules.v1.scraping.service.tasks.scrape_source_stage1": {
            "queue": SCRAPING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.process_extraction_stage2": {
            "queue": PROCESSING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.persist_results_stage3": {
            "queue": PERSISTENCE_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources": {
            "queue": SCRAPING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.monitor_stalled_jobs": {
            "queue": SCRAPING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs": {
            "queue": SCRAPING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.detect_changes_and_notify_stage4": {
            "queue": PROCESSING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source": {
            "queue": SCRAPING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.dispatch_due_jurisdictions": {
            "queue": PROCESSING_QUEUE,
        },
        "app.api.modules.v1.scraping.service.tasks.consolidate_jurisdiction_content": {
            "queue": PROCESSING_QUEUE,
        },
        "app.api.modules.v1.api_access.service.rotation_tasks.rotate_due_keys": {
            "queue": PROCESSING_QUEUE,
        },
        "send_revision_notifications": {
            "queue": PROCESSING_QUEUE,
        },
        "send_internal_user_notification": {
            "queue": PROCESSING_QUEUE,
        },
        "send_external_participant_notification": {
            "queue": PROCESSING_QUEUE,
        },
        # TODO: billing not yet implemented — uncomment when ready
        # "billing.tasks.expire_trials": {
        #     "queue": PROCESSING_QUEUE,
        # },
        # "billing.tasks.update_billing_status": {
        #     "queue": PROCESSING_QUEUE,
        # },
        # "billing.tasks.send_trial_reminders": {
        #     "queue": PROCESSING_QUEUE,
        # },
        "sitemap_rebuild_debounced": {
            "queue": PROCESSING_QUEUE,
        },
    },
)


celery_app.conf.beat_schedule = {
    # "dispatch-due-sources-every-minute": {
    #     "task": "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources",
    #     "schedule": crontab(minute="*"),
    # },
    "monitor-stalled-jobs-every-5-minutes": {
        "task": "app.api.modules.v1.scraping.service.tasks.monitor_stalled_jobs",
        "schedule": crontab(minute="*/5"),
    },
    # "retry-stuck-jobs": {
    #     "task": "app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs",
    #     "schedule": crontab(minute="*/5"),
    # },
    "rotate-due-api-keys-every-hour": {
        "task": "app.api.modules.v1.api_access.service.rotation_tasks.rotate_due_keys",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "dispatch-due-jurisdictions-every-15-minutes": {
        "task": "app.api.modules.v1.scraping.service.tasks.dispatch_due_jurisdictions",
        "schedule": crontab(minute="*/15"),
    },
    "detect-zombie-campaigns-every-30-minutes": {
        "task": "app.api.modules.v1.campaigns.tasks.campaign_tasks.detect_zombie_campaigns",
        "schedule": crontab(minute="*/30"),
    },
    # TODO: billing not yet implemented — uncomment when ready
    # "expire-trials-every-hour": {
    #     "task": "billing.tasks.expire_trials",
    #     "schedule": crontab(minute=0, hour="*/1"),
    # },
    # "update-billing-status-every-6-hours": {
    #     "task": "billing.tasks.update_billing_status",
    #     "schedule": crontab(minute=0, hour="*/6"),
    # },
    # "send-trial-reminders-daily": {
    #     "task": "billing.tasks.send_trial_reminders",
    #     "schedule": crontab(minute=0, hour=9),
    # },
}
