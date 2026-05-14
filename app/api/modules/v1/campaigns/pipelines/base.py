"""Abstract base class for campaign pipeline execution backends."""

from abc import ABC, abstractmethod
from uuid import UUID


class CampaignPipelineRunner(ABC):
    """Abstract interface that all campaign pipeline backends must implement.

    Both Celery and LangGraph orchestration services implement this contract.
    Routes and services depend only on this interface — never on a concrete
    backend class directly. Backend selection is delegated to the factory.

    Examples:
        >>> runner = get_pipeline_runner()   # from factory
        >>> result = await runner.run(campaign_id)
        >>> status = await runner.get_status(campaign_id)
    """

    @abstractmethod
    async def run(self, campaign_id: UUID, **kwargs) -> dict:
        """Launch the full campaign pipeline for the given campaign.

        Args:
            campaign_id (UUID): The campaign to execute.
            **kwargs: Backend-specific runtime options.

        Returns:
            dict: Execution metadata (e.g., ``{"backend": "celery", "task_id": "..."}``)

        Raises:
            PipelineExecutionError: If the pipeline cannot be started.
        """

    @abstractmethod
    async def get_status(self, campaign_id: UUID) -> dict:
        """Return the current execution status of a campaign pipeline.

        Args:
            campaign_id (UUID): The campaign to query.

        Returns:
            dict: Status payload with at minimum ``{"phase": str, "status": str}``.

        Raises:
            PipelineExecutionError: If status cannot be determined.
        """

    @abstractmethod
    async def pause(self, campaign_id: UUID) -> None:
        """Pause the running pipeline for a campaign.

        Sets campaign status to ``PAUSED``. Already-running tasks are not
        interrupted; only pending (queued) tasks are revoked.

        Args:
            campaign_id (UUID): The campaign to pause.

        Raises:
            PipelineExecutionError: If the campaign is not in a pauseable state.
        """

    @abstractmethod
    async def resume(self, campaign_id: UUID) -> None:
        """Resume a previously paused campaign pipeline.

        Continues execution from the last completed phase.

        Args:
            campaign_id (UUID): The campaign to resume.

        Raises:
            PipelineExecutionError: If the campaign is not in a resumeable state.
        """

    @abstractmethod
    async def cancel(self, campaign_id: UUID) -> None:
        """Cancel the pipeline and mark the campaign as CANCELLED.

        Revokes all pending tasks and sets ``Campaign.status = CANCELLED``.

        Args:
            campaign_id (UUID): The campaign to cancel.

        Raises:
            PipelineExecutionError: If cancellation fails.
        """
