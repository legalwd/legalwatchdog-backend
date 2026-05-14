from celery import Celery
from celery.schedules import crontab

from app.api.core.config import settings

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
            "queue": "scraping",
        },
        "app.api.modules.v1.scraping.service.tasks.process_extraction_stage2": {
            "queue": "processing",
        },
        "app.api.modules.v1.scraping.service.tasks.persist_results_stage3": {
            "queue": "persistence",
        },
        "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources": {
            "queue": "scraping",
        },
        "app.api.modules.v1.scraping.service.tasks.monitor_stalled_jobs": {
            "queue": "scraping",
        },
        "app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs": {
            "queue": "scraping",
        },
        "app.api.modules.v1.scraping.service.tasks.detect_changes_and_notify_stage4": {
            "queue": "processing",
        },
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source": {
            "queue": "scraping",
        },
        "app.api.modules.v1.scraping.service.tasks.dispatch_due_jurisdictions": {
            "queue": "processing",
        },
        "app.api.modules.v1.scraping.service.tasks.consolidate_jurisdiction_content": {
            "queue": "processing",
        },
        "app.api.modules.v1.api_access.service.rotation_tasks.rotate_due_keys": {
            "queue": "processing",
        },
        "send_revision_notifications": {
            "queue": "processing",
        },
        "send_internal_user_notification": {
            "queue": "processing",
        },
        "send_external_participant_notification": {
            "queue": "processing",
        },
        # TODO: billing not yet implemented — uncomment when ready
        # "billing.tasks.expire_trials": {
        #     "queue": "processing",
        # },
        # "billing.tasks.update_billing_status": {
        #     "queue": "processing",
        # },
        # "billing.tasks.send_trial_reminders": {
        #     "queue": "processing",
        # },
        "sitemap_rebuild_debounced": {
            "queue": "processing",
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
