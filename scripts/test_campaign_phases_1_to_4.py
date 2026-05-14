"""E2E test script for Campaign Phases 1–4: CRUD, Taxonomy, Hydration, Source Discovery.

Exercises the full Campaign lifecycle from creation through taxonomy
generation (real LLM call), hydration into Project + Jurisdiction
records, and discovering sources.

Prerequisites:
    - Server running at ``http://localhost:8000``
    - Superadmin user exists (``python scripts/create_superadmin.py``)
    - ``.env`` contains ``SUPERADMIN_EMAIL``, ``SUPERADMIN_PASSWORD``, 
      ``OPENROUTER_API_KEY``, ``PARALLEL_API_KEY``

Usage::

    python scripts/test_campaign_phases_1_to_4.py
    python scripts/test_campaign_phases_1_to_4.py --cleanup   # delete created entities at end
    python scripts/test_campaign_phases_1_to_4.py --max-jurisdictions 20  # smaller test
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.core.config import settings  # noqa: E402
from app.api.db.database import AsyncSessionLocal  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("campaign_e2e")

BASE_URL = f"http://localhost:{settings.APP_PORT}/api/v1"
TIMEOUT = httpx.Timeout(180.0, connect=10.0)


class PhaseResult:
    """Tracks the outcome of a single test phase."""

    def __init__(self, phase: str):
        self.phase = phase
        self.passed = False
        self.details: str = ""
        self.duration: float = 0.0
        self.data: Dict[str, Any] = {}


class CampaignE2ERunner:
    """Orchestrates the Phase 1–4 E2E test flow.

    Attributes:
        client: Async HTTP client for API calls.
        token: JWT access token.
        org_id: Organization UUID.
        campaign_id: Campaign UUID.
        results: List of PhaseResult outcomes.
    """

    def __init__(self, max_jurisdictions: int = 50, cleanup: bool = False):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
        self.token: Optional[str] = None
        self.org_id: Optional[UUID] = None
        self.campaign_id: Optional[UUID] = None
        self.project_id: Optional[UUID] = None
        self.jurisdiction_ids: List[UUID] = []
        self.max_jurisdictions = max_jurisdictions
        self.cleanup = cleanup
        self.results: List[PhaseResult] = []

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def run(self):
        """Execute all phases sequentially."""
        logger.info("=" * 70)
        logger.info("Campaign Phases 1-4 E2E Test")
        logger.info("=" * 70)
        logger.info("Base URL:           %s", BASE_URL)
        logger.info("Superadmin email:   %s", settings.SUPERADMIN_EMAIL)
        logger.info("Max jurisdictions:  %d", self.max_jurisdictions)
        logger.info("Cleanup on finish:  %s", self.cleanup)
        logger.info("=" * 70)

        try:
            await self._step_health_check()
            await self._step_login()
            await self._step_create_or_get_org()

            await self._phase1_campaign_crud()
            await self._phase2_taxonomy()
            await self._phase3_hydration()
            await self._phase4_source_discovery()
            await self._verify_hydration_results()
            await self._verify_source_discovery_results()

            if self.cleanup:
                await self._cleanup()

        except Exception as exc:
            logger.error("FATAL: %s", exc, exc_info=True)
        finally:
            await self.client.aclose()
            self._print_summary()

    async def _step_health_check(self):
        """Verify the server is reachable."""
        logger.info("[SETUP] Checking server health...")
        try:
            resp = await self.client.get(
                "/",
                timeout=httpx.Timeout(10.0),
            )
            _ = await self.client.get(
                f"http://localhost:{settings.APP_PORT}/health",
                timeout=httpx.Timeout(10.0),
            )
        except httpx.ConnectError:
            logger.error(
                "Cannot connect to %s — is the server running?",
                BASE_URL,
            )
            sys.exit(1)
        logger.info("[SETUP] Server is reachable (status %d)", resp.status_code)

    async def _step_login(self):
        """Authenticate as superadmin and obtain JWT token."""
        logger.info("[SETUP] Logging in as superadmin (%s)...", settings.SUPERADMIN_EMAIL)
        resp = await self.client.post(
            "/auth/login",
            json={
                "email": settings.SUPERADMIN_EMAIL,
                "password": settings.SUPERADMIN_PASSWORD,
            },
        )
        if resp.status_code != 200:
            logger.error("Login failed: %d %s", resp.status_code, resp.text)
            sys.exit(1)

        body = resp.json()
        self.token = body["data"]["access_token"]
        logger.info("[SETUP] Login successful — token acquired")

    async def _step_create_or_get_org(self):
        """Create a test organization or reuse an existing one."""
        logger.info("[SETUP] Creating test organization...")
        resp = await self.client.post(
            "/organizations",
            json={
                "name": f"Campaign E2E Test Org {int(time.time())}",
                "industry": "EOR",
            },
            headers=self._headers(),
        )
        if resp.status_code == 201:
            body = resp.json()
            self.org_id = UUID(body["data"]["organization_id"])
            logger.info("[SETUP] Organization created: %s", self.org_id)
        elif resp.status_code in (409, 400):
            logger.info("[SETUP] Org creation returned %d — will reuse", resp.status_code)
            self.org_id = await self._find_existing_org()
            if not self.org_id:
                logger.error("Cannot find or create an organization")
                sys.exit(1)
            logger.info("[SETUP] Reusing org: %s", self.org_id)
        else:
            logger.error(
                "Unexpected org creation response: %d %s",
                resp.status_code,
                resp.text,
            )
            sys.exit(1)

    async def _find_existing_org(self) -> Optional[UUID]:
        """Fall back to finding an org the user belongs to via the campaign list."""
        from sqlalchemy import select as sa_select

        from app.api.modules.v1.organization.models.organization_model import Organization

        async with AsyncSessionLocal() as db:
            stmt = sa_select(Organization).limit(1)
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()
            if org:
                return org.id
        return None

    # ------------------------------------------------------------------
    # Phase 1 — Campaign CRUD
    # ------------------------------------------------------------------

    async def _phase1_campaign_crud(self):
        """Phase 1: Create, read, update, list campaigns."""
        r = PhaseResult("Phase 1 — Campaign CRUD")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("PHASE 1: Campaign CRUD")
            logger.info("-" * 60)

            campaign = await self._create_campaign()
            self.campaign_id = UUID(campaign["id"])
            logger.info(
                "  [1.1] Created campaign: %s (status=%s)",
                self.campaign_id,
                campaign["status"],
            )
            assert campaign["status"] == "DRAFT", (
                f"Expected DRAFT, got {campaign['status']}"
            )

            fetched = await self._get_campaign(self.campaign_id)
            logger.info(
                "  [1.2] GET campaign: name=%s, industry=%s",
                fetched["name"],
                fetched["industry"],
            )
            assert fetched["id"] == str(self.campaign_id)

            updated = await self._update_campaign(
                self.campaign_id,
                {"domain_description": "Updated EOR domain description for testing"},
            )
            logger.info(
                "  [1.3] PATCH campaign: domain_description updated = %s",
                bool(updated.get("domain_description")),
            )

            campaigns_list = await self._list_campaigns()
            found = any(c["id"] == str(self.campaign_id) for c in campaigns_list)
            logger.info(
                "  [1.4] LIST campaigns: total in list=%d, ours found=%s",
                len(campaigns_list),
                found,
            )
            assert found, "Campaign not found in list"

            r.passed = True
            r.details = f"Campaign {self.campaign_id} created and verified"
            r.data = {"campaign_id": str(self.campaign_id)}

        except Exception as exc:
            r.details = str(exc)
            logger.error("Phase 1 FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    async def _create_campaign(self) -> Dict[str, Any]:
        resp = await self.client.post(
            "/campaigns",
            json={
                "organization_id": str(self.org_id),
                "name": f"EOR E2E Test Campaign {int(time.time())}",
                "industry": "EOR",
                "domain_description": (
                    "Employer of Record employment regulations covering "
                    "hiring, payroll, termination, and benefits across "
                    "multiple jurisdictions."
                ),
                "target_depth": "STATE",
                "monitor_backend": "CELERY_BEAT",
                "monitor_cadence": "weekly",
                "sources_per_jurisdiction": 3,
                "max_jurisdictions": self.max_jurisdictions,
            },
            headers=self._headers(),
        )
        assert resp.status_code == 201, (
            f"Campaign create failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    async def _get_campaign(self, campaign_id: UUID) -> Dict[str, Any]:
        resp = await self.client.get(
            f"/campaigns/{campaign_id}",
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Campaign GET failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    async def _update_campaign(
        self, campaign_id: UUID, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        resp = await self.client.patch(
            f"/campaigns/{campaign_id}",
            json=payload,
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Campaign PATCH failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    async def _list_campaigns(self) -> List[Dict[str, Any]]:
        resp = await self.client.get(
            "/campaigns",
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Campaign LIST failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]["campaigns"]

    # ------------------------------------------------------------------
    # Phase 2 — Taxonomy Generation + Geo Validation + Approval
    # ------------------------------------------------------------------

    async def _phase2_taxonomy(self):
        """Phase 2: Generate taxonomy via LLM, preview, approve."""
        r = PhaseResult("Phase 2 — Taxonomy + Geo Validation")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("PHASE 2: Taxonomy Generation + Geo Validation")
            logger.info("-" * 60)

            logger.info(
                "  [2.1] Generating taxonomy via LLM (this may take 30-60s)..."
            )
            gen_resp = await self._generate_taxonomy(self.campaign_id)
            logger.info("  [2.1] Taxonomy generation triggered — status: %s", gen_resp.get("status"))
            status = gen_resp.get("status")

            if status == "GENERATING_TAXONOMY":
                logger.info("  [2.1] Polling for TAXONOMY_READY...")
                for _ in range(30):
                    await asyncio.sleep(5)
                    poll_resp = await self._get_campaign(self.campaign_id)
                    status = poll_resp.get("status")
                    if status == "TAXONOMY_READY":
                        break
                    elif status == "FAILED":
                        raise Exception("Taxonomy generation failed!")
                    logger.info("        ... still %s", status)

            assert status == "TAXONOMY_READY", f"Expected TAXONOMY_READY, got {status}"

            logger.info("  [2.2] Fetching taxonomy preview...")
            taxonomy_detail = await self._get_taxonomy(self.campaign_id)
            nodes = taxonomy_detail.get("taxonomy", [])
            warnings = taxonomy_detail.get("warnings", [])
            preview = taxonomy_detail.get("preview_stats", {})
            logger.info(
                "  [2.2] Taxonomy preview:"
            )
            logger.info(
                "         Total nodes:    %d", preview.get("total_nodes", 0)
            )
            logger.info(
                "         Countries:      %d", preview.get("countries", 0)
            )
            logger.info(
                "         States:         %d", preview.get("states", 0)
            )
            logger.info(
                "         Geo warnings:   %d", len(warnings)
            )
            assert preview.get("total_nodes", 0) > 0, "No taxonomy nodes generated"

            top_countries = [n["name"] for n in nodes[:10]]
            logger.info("  [2.2] Top countries:   %s", ", ".join(top_countries))

            if warnings:
                for w in warnings[:5]:
                    logger.info(
                        "         WARNING: %s — %s",
                        w.get("node_name"),
                        w.get("issue"),
                    )

            iso_count = sum(1 for n in nodes if n.get("iso_code"))
            logger.info(
                "  [2.2] ISO codes attached: %d/%d top-level nodes",
                iso_count,
                len(nodes),
            )

            logger.info("  [2.3] Approving taxonomy...")
            approval = await self._approve_taxonomy(self.campaign_id)
            logger.info(
                "  [2.3] Taxonomy approved by %s at %s",
                approval.get("taxonomy_approved_by"),
                approval.get("taxonomy_approved_at"),
            )

            r.passed = True
            r.details = (
                f"{preview.get('total_nodes', 0)} nodes, "
                f"{preview.get('countries', 0)} countries, "
                f"{preview.get('states', 0)} states, "
                f"{len(warnings)} geo warnings"
            )
            r.data = {
                "total_nodes": preview.get("total_nodes", 0),
                "countries": preview.get("countries", 0),
                "states": preview.get("states", 0),
                "warnings": len(warnings),
            }

        except Exception as exc:
            r.details = str(exc)
            logger.error("Phase 2 FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    async def _generate_taxonomy(self, campaign_id: UUID) -> Dict[str, Any]:
        resp = await self.client.post(
            f"/campaigns/{campaign_id}/generate-taxonomy",
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Taxonomy generate failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    async def _get_taxonomy(self, campaign_id: UUID) -> Dict[str, Any]:
        resp = await self.client.get(
            f"/campaigns/{campaign_id}/taxonomy",
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Taxonomy GET failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    async def _approve_taxonomy(self, campaign_id: UUID) -> Dict[str, Any]:
        resp = await self.client.post(
            f"/campaigns/{campaign_id}/approve-taxonomy",
            headers=self._headers(),
        )
        assert resp.status_code == 200, (
            f"Taxonomy approve failed: {resp.status_code} {resp.text}"
        )
        return resp.json()["data"]

    # ------------------------------------------------------------------
    # Phase 3 — Hydration (direct service call)
    # ------------------------------------------------------------------

    async def _phase3_hydration(self):
        """Phase 3: Hydrate taxonomy into Project + Jurisdiction records."""
        r = PhaseResult("Phase 3 — Hydration")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("PHASE 3: Hydration (direct service call)")
            logger.info("-" * 60)

            from app.api.modules.v1.campaigns.service.campaign_hydration_service import (
                CampaignHydrationService,
            )

            logger.info("  [3.1] Running CampaignHydrationService.hydrate()...")
            async with AsyncSessionLocal() as db:
                service = CampaignHydrationService(db)
                self.jurisdiction_ids = await service.hydrate(self.campaign_id)

            logger.info(
                "  [3.1] Hydration complete — %d jurisdictions created",
                len(self.jurisdiction_ids),
            )

            r.passed = True
            r.details = f"{len(self.jurisdiction_ids)} jurisdictions created"
            r.data = {"jurisdiction_count": len(self.jurisdiction_ids)}

        except Exception as exc:
            r.details = str(exc)
            logger.error("Phase 3 FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    # ------------------------------------------------------------------
    # Phase 4 — Source Discovery
    # ------------------------------------------------------------------

    async def _phase4_source_discovery(self):
        """Phase 4: Discover sources for jurisdictions."""
        r = PhaseResult("Phase 4 — Source Discovery")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("PHASE 4: Source Discovery (direct service call)")
            logger.info("-" * 60)

            from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
                CampaignSourceDiscoveryService,
            )
            from app.api.core.dependencies.redis_service import get_redis_client

            logger.info("  [4.1] Running CampaignSourceDiscoveryService.discover_all()...")
            redis_client = await get_redis_client()
            async with AsyncSessionLocal() as db:
                service = CampaignSourceDiscoveryService(db=db, redis_client=redis_client)
                result = await service.discover_all(self.campaign_id)

            logger.info(
                "  [4.1] Discovery complete — %d sources created, %d errors, %d skipped",
                result.get("sources_created", 0),
                result.get("failed", 0),
                result.get("skipped_duplicate", 0),
            )

            r.passed = True
            r.details = f"{result.get('sources_created', 0)} sources created"
            r.data = result

        except Exception as exc:
            r.details = str(exc)
            logger.error("Phase 4 FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    # ------------------------------------------------------------------
    # Verification (post-hydration)
    # ------------------------------------------------------------------

    async def _verify_hydration_results(self):
        """Verify hydration created correct DB records."""
        r = PhaseResult("Verification — Hydration Results")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("VERIFICATION: Hydration Results")
            logger.info("-" * 60)

            from sqlalchemy import func
            from sqlmodel import select

            from app.api.modules.v1.campaigns.models.campaign_model import Campaign
            from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
                Jurisdiction,
            )
            from app.api.modules.v1.projects.models.project_model import Project

            async with AsyncSessionLocal() as db:
                campaign = await db.get(Campaign, self.campaign_id)
                assert campaign is not None, "Campaign not found in DB"
                logger.info(
                    "  [V.1] Campaign status: %s", campaign.status.value
                )
                logger.info(
                    "  [V.1] Campaign project_id: %s", campaign.project_id
                )
                self.project_id = campaign.project_id

                if campaign.project_id:
                    project = await db.get(Project, campaign.project_id)
                    assert project is not None, "Project not found"
                    logger.info(
                        "  [V.2] Project title: %s", project.title
                    )
                    logger.info(
                        "  [V.2] Project org_id: %s", project.org_id
                    )
                    assert project.org_id == self.org_id, (
                        f"Project org mismatch: {project.org_id} != {self.org_id}"
                    )

                count_stmt = (
                    select(func.count(Jurisdiction.id))
                    .where(Jurisdiction.campaign_id == self.campaign_id)
                )
                total_jurisdictions = await db.scalar(count_stmt)
                logger.info(
                    "  [V.3] Total jurisdictions with campaign_id: %d",
                    total_jurisdictions,
                )

                top_level_stmt = (
                    select(func.count(Jurisdiction.id))
                    .where(
                        Jurisdiction.campaign_id == self.campaign_id,
                        Jurisdiction.parent_id.is_(None),
                    )
                )
                top_level_count = await db.scalar(top_level_stmt)
                logger.info(
                    "  [V.3] Top-level (countries): %d", top_level_count
                )

                child_stmt = (
                    select(func.count(Jurisdiction.id))
                    .where(
                        Jurisdiction.campaign_id == self.campaign_id,
                        Jurisdiction.parent_id.isnot(None),
                    )
                )
                child_count = await db.scalar(child_stmt)
                logger.info(
                    "  [V.3] Children (states/topics): %d", child_count
                )

                sample_stmt = (
                    select(Jurisdiction)
                    .where(Jurisdiction.campaign_id == self.campaign_id)
                    .limit(5)
                )
                sample_result = await db.execute(sample_stmt)
                samples = sample_result.scalars().all()

                all_auto_accept = all(j.auto_accept_changes for j in samples)
                logger.info(
                    "  [V.4] auto_accept_changes=True on sample: %s",
                    all_auto_accept,
                )
                assert all_auto_accept, (
                    "Some jurisdictions have auto_accept_changes=False"
                )

                all_auto_scrape = all(j.enable_auto_scrape for j in samples)
                logger.info(
                    "  [V.4] enable_auto_scrape=True on sample: %s",
                    all_auto_scrape,
                )

                some_names = [j.name for j in samples]
                logger.info(
                    "  [V.5] Sample jurisdiction names: %s",
                    ", ".join(some_names),
                )

                stats = campaign.stats or {}
                logger.info(
                    "  [V.6] Campaign stats: %s",
                    json.dumps(stats, indent=2, default=str),
                )

            campaign_resp = await self._get_campaign(self.campaign_id)
            logger.info(
                "  [V.7] Campaign via API — status: %s, project_id: %s",
                campaign_resp.get("status"),
                campaign_resp.get("project_id"),
            )

            r.passed = True
            r.details = (
                f"{total_jurisdictions} jurisdictions "
                f"({top_level_count} countries, {child_count} children)"
            )
            r.data = {
                "total_jurisdictions": total_jurisdictions,
                "top_level": top_level_count,
                "children": child_count,
                "auto_accept": all_auto_accept,
            }

        except Exception as exc:
            r.details = str(exc)
            logger.error("Verification FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    async def _verify_source_discovery_results(self):
        """Verify source discovery created DB records."""
        r = PhaseResult("Verification — Source Discovery Results")
        start = time.monotonic()

        try:
            logger.info("")
            logger.info("-" * 60)
            logger.info("VERIFICATION: Source Discovery Results")
            logger.info("-" * 60)

            from sqlalchemy import func
            from sqlmodel import select

            from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
            from app.api.modules.v1.scraping.models.source_model import Source

            async with AsyncSessionLocal() as db:
                count_stmt = (
                    select(func.count(Source.id))
                    .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
                    .where(Jurisdiction.campaign_id == self.campaign_id)
                )
                total_sources = await db.scalar(count_stmt)
                logger.info(
                    "  [V.8] Total sources for campaign jurisdictions: %d",
                    total_sources,
                )

            campaign_resp = await self._get_campaign(self.campaign_id)
            logger.info(
                "  [V.9] Campaign via API — status: %s",
                campaign_resp.get("status"),
            )

            r.passed = True
            r.details = f"{total_sources} sources verified"
            r.data = {
                "total_sources": total_sources,
            }

        except Exception as exc:
            r.details = str(exc)
            logger.error("Verification FAILED: %s", exc, exc_info=True)

        r.duration = time.monotonic() - start
        self.results.append(r)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup(self):
        """Delete entities created during the test run."""
        logger.info("")
        logger.info("-" * 60)
        logger.info("CLEANUP")
        logger.info("-" * 60)

        from sqlmodel import select

        from app.api.modules.v1.campaigns.models.campaign_model import (
            Campaign,
            CampaignExecutionLog,
            CampaignStatus,
        )
        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
            Jurisdiction,
        )
        from app.api.modules.v1.projects.models.project_model import Project
        from app.api.modules.v1.scraping.models.source_model import Source

        async with AsyncSessionLocal() as db:
            try:
                jur_stmt = select(Jurisdiction).where(
                    Jurisdiction.campaign_id == self.campaign_id
                )
                jur_result = await db.execute(jur_stmt)
                jurisdictions = jur_result.scalars().all()
                jur_ids = [j.id for j in jurisdictions]

                if jur_ids:
                    src_stmt = select(Source).where(Source.jurisdiction_id.in_(jur_ids))
                    src_result = await db.execute(src_stmt)
                    sources = src_result.scalars().all()
                    for s in sources:
                        await db.delete(s)
                    logger.info("  Deleted %d sources", len(sources))

                for j in jurisdictions:
                    await db.delete(j)
                logger.info(
                    "  Deleted %d jurisdictions", len(jurisdictions)
                )

                log_stmt = select(CampaignExecutionLog).where(
                    CampaignExecutionLog.campaign_id == self.campaign_id
                )
                log_result = await db.execute(log_stmt)
                logs = log_result.scalars().all()
                for log in logs:
                    await db.delete(log)
                logger.info("  Deleted %d execution logs", len(logs))

                campaign = await db.get(Campaign, self.campaign_id)
                if campaign:
                    campaign.status = CampaignStatus.DRAFT
                    campaign.project_id = None
                    db.add(campaign)
                    await db.flush()
                    await db.delete(campaign)
                    logger.info("  Deleted campaign %s", self.campaign_id)

                if self.project_id:
                    project = await db.get(Project, self.project_id)
                    if project:
                        await db.delete(project)
                        logger.info("  Deleted project %s", self.project_id)

                await db.commit()
                logger.info("  Cleanup committed successfully")

            except Exception as exc:
                await db.rollback()
                logger.error("  Cleanup failed: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self):
        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(
            "%-45s %-8s %8s  %s",
            "Phase", "Status", "Duration", "Details",
        )
        logger.info("-" * 100)

        all_passed = True
        for r in self.results:
            status_str = "PASS" if r.passed else "FAIL"
            if not r.passed:
                all_passed = False
            logger.info(
                "%-45s %-8s %7.1fs  %s",
                r.phase,
                status_str,
                r.duration,
                r.details,
            )

        logger.info("-" * 100)
        total_time = sum(r.duration for r in self.results)
        logger.info(
            "%-45s %-8s %7.1fs",
            "TOTAL",
            "PASS" if all_passed else "FAIL",
            total_time,
        )
        logger.info("=" * 70)

        if self.campaign_id:
            logger.info("")
            logger.info("Created entities:")
            logger.info("  Campaign ID:    %s", self.campaign_id)
            if self.project_id:
                logger.info("  Project ID:     %s", self.project_id)
            logger.info(
                "  Jurisdictions:  %d", len(self.jurisdiction_ids)
            )
            if not self.cleanup:
                logger.info("")
                logger.info(
                    "Tip: Re-run with --cleanup to delete test entities, or"
                )
                logger.info(
                    "     inspect via Swagger: GET /api/v1/campaigns/%s",
                    self.campaign_id,
                )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="E2E test for Campaign Phases 1-4",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all created test entities after the run",
    )
    parser.add_argument(
        "--max-jurisdictions",
        type=int,
        default=50,
        help="Max jurisdictions cap for the test campaign (default: 50)",
    )
    return parser.parse_args()


async def main():
    """Entry point."""
    args = parse_args()
    runner = CampaignE2ERunner(
        max_jurisdictions=args.max_jurisdictions,
        cleanup=args.cleanup,
    )
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
