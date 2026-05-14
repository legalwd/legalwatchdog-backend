"""Factory for campaign pipeline backend selection.

Reads ``CAMPAIGN_PIPELINE_BACKEND`` from app config and returns the
appropriate ``CampaignPipelineRunner`` implementation.  All routes and
services must obtain their runner through this factory — never by
instantiating a concrete runner class directly.

Examples:
    >>> from app.api.modules.v1.campaigns.pipelines.factory import get_pipeline_runner
    >>> runner = get_pipeline_runner()
    >>> result = await runner.run(campaign_id)
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.pipelines.base import CampaignPipelineRunner


def get_pipeline_runner(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignPipelineRunner:
    """Return the configured campaign pipeline runner backend.

    Reads ``settings.CAMPAIGN_PIPELINE_BACKEND`` and returns the matching
    concrete implementation. Imports are deferred to avoid loading heavy
    dependencies (e.g., langgraph) when the other backend is configured.

    Returns:
        CampaignPipelineRunner: The active backend implementation.

    Raises:
        ValueError: If ``CAMPAIGN_PIPELINE_BACKEND`` is not ``"celery"`` or
            ``"langgraph"``.
    """
    match settings.CAMPAIGN_PIPELINE_BACKEND:
        case "celery":
            from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
                CampaignOrchestrationService,
            )

            return CampaignOrchestrationService(db=db)
        case "langgraph":
            from app.api.modules.v1.campaigns.pipelines.langgraph_runner import (
                LangGraphPipelineRunner,
            )

            return LangGraphPipelineRunner()
        case _:
            raise ValueError(
                f"Unknown CAMPAIGN_PIPELINE_BACKEND: '{settings.CAMPAIGN_PIPELINE_BACKEND}'. "
                f"Expected 'celery' or 'langgraph'."
            )
