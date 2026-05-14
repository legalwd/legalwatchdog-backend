import asyncio
import logging
import sys
from pathlib import Path

import pytest

from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_discovery_agent():
    """
    Runs a manual test of the SourceDiscoveryService.
    This hits the REAL Gemini and Tavily APIs, so it consumes credits.
    """
    print("=" * 80)
    print("TEST: Source Discovery Agent (Live Web Search)")
    print("=" * 80)

    # Test Case: Finding official sources for UK Minimum Wage
    # Using broader descriptions simulating the Project/Jurisdiction models
    jurisdiction_name = "United Kingdom"
    jurisdiction_description = "UK minimum wage regulations"
    jurisdiction_prompt = "Focus on age category breakdown and effective dates for wage rates"

    # Detailed project description (similar to Project.master_prompt)
    project_description = (
        "Extract the current National Minimum Wage and National Living Wage rates per hour. "
        "Group the rates by age category (e.g., '21 and over', '18 to 20'). "
        "Identify the 'Effective Date' for these rates."
    )

    print("\n[INPUT PARAMETERS]")
    print(f"  Jurisdiction Name: {jurisdiction_name}")
    print(f"  Jurisdiction Desc: {jurisdiction_description}")
    print(f"  Jurisdiction Prompt: {jurisdiction_prompt}")
    print(f"  Goal: {project_description}")

    try:
        print("\n[1] Initializing Service...")
        service = SourceDiscoveryService()

        print("[2] Running Agentic Search (Query Generation -> Search -> Filter -> Validate)...")
        # This calls the exact logic used by your API endpoint
        sources = await service.suggest_sources(
            search_query=jurisdiction_prompt,
            jurisdiction_name=jurisdiction_name,
        )

        print("\n" + "=" * 80)
        print(f"[RESULTS] Found {len(sources)} Valid Official Sources")
        print("=" * 80)

        if not sources:
            print("[WARN] No sources found. Check your Tavily/Gemini quotas or search terms.")

        for i, source in enumerate(sources, 1):
            print(f"\nSource #{i}")
            print(f"  Title:    {source.title}")
            print(f"  URL:      {source.url}")
            print(f"  Official: {'✅ Yes' if source.is_official else '❌ No'}")
            print(f"  Reason:   {source.confidence_reason}")
            print(f"  Snippet:  {source.snippet[:150]}...")  # Truncate for display

    except ValueError as ve:
        print(f"\n[CONFIGURATION ERROR] {ve}")
        print("Ensure 'TAVILY_API_KEY' and 'GOOGLE_API_KEY' are set in your .env file.")
    except Exception as e:
        print(f"\n[ERROR] Test Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_discovery_agent())
