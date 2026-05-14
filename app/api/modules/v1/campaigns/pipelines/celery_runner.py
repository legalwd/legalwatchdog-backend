"""Celery-backed campaign pipeline runner.

Delegates execution to ``CampaignOrchestrationService`` which builds a
Celery chain of tasks for the full campaign pipeline.
"""

from uuid import UUID

from app.api.modules.v1.campaigns.pipelines.base import CampaignPipelineRunner


class CeleryPipelineRunner(CampaignPipelineRunner):
    """Campaign pipeline runner backed by Celery task chains.

    This is the **primary / default** backend. Implemented fully in
    Phase 5A (#541). This stub satisfies the interface and will be replaced
    by the real implementation in that phase.
    """

    async def run(self, campaign_id: UUID, **kwargs) -> dict:
        """Launch the campaign pipeline as a Celery chain.

        Args:
            campaign_id (UUID): The campaign to execute.
            **kwargs: Passed through to ``CampaignOrchestrationService.launch_campaign``.

        Returns:
            dict: ``{"backend": "celery", "task_id": str}``.

        Raises:
            NotImplementedError: Until Phase 5A is complete.
        """
        raise NotImplementedError("CeleryPipelineRunner will be implemented in Phase 5A (#541)")

    async def get_status(self, campaign_id: UUID) -> dict:
        """Return Celery pipeline status for a campaign.

        Args:
            campaign_id (UUID): The campaign to query.

        Returns:
            dict: Phase breakdown and current status.

        Raises:
            NotImplementedError: Until Phase 5A is complete.
        """
        raise NotImplementedError("CeleryPipelineRunner will be implemented in Phase 5A (#541)")

    async def pause(self, campaign_id: UUID) -> None:
        """Pause pending Celery tasks for the campaign.

        Args:
            campaign_id (UUID): The campaign to pause.

        Raises:
            NotImplementedError: Until Phase 5A is complete.
        """
        raise NotImplementedError("CeleryPipelineRunner will be implemented in Phase 5A (#541)")

    async def resume(self, campaign_id: UUID) -> None:
        """Resume a paused Celery pipeline from the last completed phase.

        Args:
            campaign_id (UUID): The campaign to resume.

        Raises:
            NotImplementedError: Until Phase 5A is complete.
        """
        raise NotImplementedError("CeleryPipelineRunner will be implemented in Phase 5A (#541)")

    async def cancel(self, campaign_id: UUID) -> None:
        """Cancel all pending Celery tasks and mark the campaign CANCELLED.

        Args:
            campaign_id (UUID): The campaign to cancel.

        Raises:
            NotImplementedError: Until Phase 5A is complete.
        """
        raise NotImplementedError("CeleryPipelineRunner will be implemented in Phase 5A (#541)")
