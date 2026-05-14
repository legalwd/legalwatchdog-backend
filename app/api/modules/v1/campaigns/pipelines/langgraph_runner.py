"""LangGraph-backed campaign pipeline runner.

Delegates execution to a stateful, Redis-checkpointed LangGraph graph.
Implemented fully in Phase 5B (#542). This stub satisfies the interface
contract and will be replaced by the real implementation in that phase.
"""

from uuid import UUID

from app.api.modules.v1.campaigns.pipelines.base import CampaignPipelineRunner


class LangGraphPipelineRunner(CampaignPipelineRunner):
    """Campaign pipeline runner backed by a LangGraph stateful graph.

    This is the **target architecture**. Provides checkpoint-based resume,
    conditional retry edges, and deterministic LLM output via Instructor.
    The Celery runner (``CeleryPipelineRunner``) is the fallback MVP.
    Migration gate: end of Phase 5B validation (#542).
    """

    async def run(self, campaign_id: UUID, **kwargs) -> dict:
        """Launch the campaign pipeline as a LangGraph graph execution.

        Args:
            campaign_id (UUID): The campaign to execute.
            **kwargs: Passed through to the compiled graph invocation.

        Returns:
            dict: ``{"backend": "langgraph", "thread_id": str}``.

        Raises:
            NotImplementedError: Until Phase 5B is complete.
        """
        raise NotImplementedError("LangGraphPipelineRunner will be implemented in Phase 5B (#542)")

    async def get_status(self, campaign_id: UUID) -> dict:
        """Return LangGraph pipeline status loaded from the Redis checkpoint.

        Args:
            campaign_id (UUID): The campaign to query.

        Returns:
            dict: Phase breakdown and current graph state.

        Raises:
            NotImplementedError: Until Phase 5B is complete.
        """
        raise NotImplementedError("LangGraphPipelineRunner will be implemented in Phase 5B (#542)")

    async def pause(self, campaign_id: UUID) -> None:
        """Interrupt the LangGraph graph execution for the campaign.

        Args:
            campaign_id (UUID): The campaign to pause.

        Raises:
            NotImplementedError: Until Phase 5B is complete.
        """
        raise NotImplementedError("LangGraphPipelineRunner will be implemented in Phase 5B (#542)")

    async def resume(self, campaign_id: UUID) -> None:
        """Replay the LangGraph graph from the last Redis checkpoint.

        Args:
            campaign_id (UUID): The campaign to resume.

        Raises:
            NotImplementedError: Until Phase 5B is complete.
        """
        raise NotImplementedError("LangGraphPipelineRunner will be implemented in Phase 5B (#542)")

    async def cancel(self, campaign_id: UUID) -> None:
        """Interrupt the graph and mark the campaign CANCELLED.

        Args:
            campaign_id (UUID): The campaign to cancel.

        Raises:
            NotImplementedError: Until Phase 5B is complete.
        """
        raise NotImplementedError("LangGraphPipelineRunner will be implemented in Phase 5B (#542)")
