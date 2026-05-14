import asyncio
import datetime
import logging
import re
import time
import uuid
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import httpx
from parallel import AsyncParallel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ProcessingError,
)
from app.api.core.source_search_redis_utils import (
    cache_search_session,
    consume_search_session,
    get_search_session,
    get_search_session_expires_in,
)
from app.api.db.models.parallel_usage import ParallelUsageLog
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource
from app.api.modules.v1.scraping.schemas.source_service import SourceCreate
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.scraping.validators.exception import (
    DuplicateSourceError,
    ExternalSearchServiceError,
    InvalidSuggestionDataError,
)

logger = logging.getLogger(__name__)


class SourceDiscoveryService:
    """Simplified source discovery using Parallel.ai Search API.

    Parallel.ai is an AI-native search API built from the ground up for AI agents.
    It returns LLM-ready ranked URLs with extended webpage excerpts (500-2000 chars),
    eliminating the need for complex multi-step pipelines.

    Architecture:
    User Query → Parallel.ai Search → Display Results
    (No LLM filtering, no query generation, minimal validation)
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        """Initialize the SourceDiscoveryService with Parallel.ai client.

        Args:
            db_session: Optional database session for usage logging.

        Raises:
            ValueError: If PARALLEL_API_KEY is not set in the configuration.
        """
        self.db_session = db_session
        if not settings.PARALLEL_API_KEY:
            raise ValueError("PARALLEL_API_KEY is not set in configuration.")

        http_client = httpx.AsyncClient(timeout=10.0, trust_env=False)

        self.parallel = AsyncParallel(api_key=settings.PARALLEL_API_KEY, http_client=http_client)
        self.http_client = httpx.AsyncClient(timeout=10.0, trust_env=False)

    async def suggest_sources(
        self,
        search_query: str,
        jurisdiction_name: Optional[str] = None,
        max_results: int = 10,
        processor: str = "base",
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> List[SuggestedSource]:
        """Discover sources using Parallel.ai's AI-native search.

        Args:
            search_query: User's natural language search query
                (e.g., "Nigeria crypto licensing requirements 2024")
            jurisdiction_name: Optional jurisdiction context to scope the search
            max_results: Number of results to return (default: 10)
            processor: "base" for speed (<5s) or "pro" for quality (15-60s)
            user_id: User ID for usage tracking
            organization_id: Organization ID for usage tracking

        Returns:
            List[SuggestedSource]: High-quality sources with extended excerpts
        """
        start_time = time.time()
        success = False
        error_message = None
        cost = Decimal("0")

        try:
            objective = self._build_objective(search_query, jurisdiction_name)

            search_results = await self._execute_parallel_search(
                objective=objective,
                max_results=max_results,
                processor=processor,
            )

            suggested_sources = self._convert_to_suggested_sources(search_results)

            valid_sources = await self._validate_urls_quick(suggested_sources)

            cost = Decimal("0.005")

            success = True

            logger.info(
                f"Parallel.ai search returned {len(valid_sources)} sources "
                f"for query: '{search_query}'"
            )

            return valid_sources

        except ExternalSearchServiceError:
            raise
        except Exception as e:
            error_message = str(e)
            logger.error(f"Parallel.ai search failed: {error_message}")
            raise ProcessingError()

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            content_size_bytes = 0

            await self._log_usage(
                user_id=user_id,
                organization_id=organization_id,
                url_extracted=f"search:{search_query[:100]}",
                endpoint_name="parallel_search",
                success=success,
                cost=cost,
                latency_ms=latency_ms,
                content_size_bytes=content_size_bytes,
                error_message=error_message,
            )

    async def suggest_and_cache(
        self, db_session: Optional[AsyncSession], payload, current_user
    ) -> dict:
        """High-level helper: run suggestion, cache the session and return payload-ready dict.

        This moves the orchestration out of the route layer.
        """
        user_id = current_user.id

        organization_id = None
        try:
            if db_session is not None:
                result = await db_session.execute(
                    select(UserOrganization.organization_id)
                    .where(UserOrganization.user_id == user_id)
                    .where(UserOrganization.is_active)
                    .limit(1)
                )
                organization_id = result.scalar()
        except Exception:
            organization_id = None

        sources = await self.suggest_sources(
            search_query=payload.search_query,
            jurisdiction_name=payload.jurisdiction_name,
            max_results=payload.max_results,
            processor=payload.processor,
            user_id=user_id,
            organization_id=organization_id,
        )

        await self.close()

        timestamp = datetime.datetime.now(datetime.timezone.utc)
        session_id = await cache_search_session(
            user_id=user_id,
            search_data={
                "sources": [s.model_dump() for s in sources],
                "query": payload.search_query,
                "jurisdiction": payload.jurisdiction_name,
                "processor": payload.processor,
                "max_results": payload.max_results,
                "timestamp": timestamp.isoformat(),
                "count": len(sources),
            },
        )

        return {
            "session_id": session_id,
            "sources": [s.model_dump() for s in sources],
            "count": len(sources),
            "processor_used": payload.processor,
            "guidance": {
                "powered_by": "Parallel.ai - AI-native web search",
                "next_steps": [
                    "Review the sources and their extended excerpts",
                    "Check confidence_reason for each source",
                    "Accept relevant sources to start monitoring",
                ],
                "quality_indicators": [
                    "is_official indicates government/regulatory sources",
                    "Extended excerpts (500-2000 chars) for quality assessment",
                    "All sources validated as reachable",
                    "AI-native ranking prioritizes content relevance",
                ],
            },
        }

    async def accept_suggested_sources(
        self, db_session: AsyncSession, payload, session_id: Optional[str], current_user
    ) -> dict:
        """Accept suggested sources: consumes cached session if provided, creates sources in DB.

        Returns a dict suitable for returning to the API consumer.
        """
        try:
            user_id = current_user.id

            if session_id:
                accepted_urls = []
                for s in payload.suggested_sources:
                    url = s.get("url")
                    if url:
                        accepted_urls.append(url)

                cached_data = await consume_search_session(
                    user_id, session_id, accepted_urls=accepted_urls
                )
                if not cached_data:
                    raise NotFoundError("Search session expired or already consumed")
                suggested_sources_data = cached_data.get("sources", [])
            else:
                suggested_sources_data = payload.suggested_sources

            sources_to_create = []
            for suggested in suggested_sources_data:
                try:
                    source_create = SourceCreate(
                        jurisdiction_id=payload.jurisdiction_id,
                        name=suggested.get("title", ""),
                        url=suggested.get("url", ""),
                        source_type=payload.source_type,
                        scrape_frequency=payload.scrape_frequency,
                        scraping_rules=payload.scraping_rules,
                        auth_details=None,
                    )
                except Exception as e:
                    logger.info(
                        f"Invalid suggested source data for \
                            title={suggested.get('title')!r}, "
                        f"url={suggested.get('url')!r}: {str(e)}"
                    )
                    raise InvalidSuggestionDataError("Invalid suggested source data")

                sources_to_create.append(source_create)

            source_service = SourceService()
            sources = await source_service.bulk_create_sources(db_session, sources_to_create)

            return {
                "sources": [source.model_dump() for source in sources],
                "count": len(sources),
                "next_steps": [
                    "Sources will be scraped according to the specified frequency",
                    "Monitor scraping results in your dashboard",
                    "Adjust scraping_rules if needed based on actual content",
                    "Review Parallel.ai excerpts for content structure hints",
                ],
                "powered_by": "Parallel.ai source discovery",
            }

        except (NotFoundError, InvalidSuggestionDataError, DuplicateSourceError):
            raise
        except Exception as e:
            logger.exception("Failed to accept suggested sources: %s", e)
            raise ProcessingError("An unexpected error occured while accepting sources")

    async def get_cached_session_with_expiry(self, user_id: uuid.UUID, session_id: str) -> dict:
        """Retrieve cached session and its TTL. Raises NotFoundError if expired/missing."""

        cached_data = await get_search_session(user_id, session_id)
        if not cached_data:
            raise NotFoundError("Results expired")

        expires_in = await get_search_session_expires_in(user_id=user_id, session_id=session_id)
        if expires_in is None or expires_in <= 0:
            raise NotFoundError("Results expired")

        return {"sources": cached_data.get("sources", []), "expires_in": expires_in}

    def _build_objective(
        self,
        search_query: str,
        jurisdiction_name: Optional[str],
    ) -> str:
        """Build a targeted semantic search objective for Parallel.ai.

        Instructs Parallel.ai to find authoritative pages that contain specific,
        extractable data (rates, rules, thresholds, tables) rather than
        homepages or navigation-only pages. Deliberately domain-agnostic so the
        same logic works for tax, labour, environmental, financial, or any other
        regulatory topic.

        Args:
            search_query: User's natural language search query.
            jurisdiction_name: Optional jurisdiction context to scope results.

        Returns:
            str: Semantic objective string for the Parallel.ai Search API.

        Examples:
            >>> obj = service._build_objective("minimum wage 2025", "Nigeria")
            >>> assert "Nigeria" in obj
        """
        data_depth_hint = (
            "Prioritise pages that contain specific, actionable data: "
            "numeric rates, legal thresholds, procedural timelines, "
            "compliance tables, or rule-based requirements. "
            "Avoid generic homepages, pure navigation pages, and abstract "
            "overviews that do not contain verifiable factual content."
        )
        authority_hint = (
            "Preferred source types (in order): official government or regulatory "
            "body pages, intergovernmental organisation publications "
            "(e.g. ILO, OECD, World Bank), Big-4 professional services summaries "
            "(e.g. PwC Tax Summaries, Deloitte, EY, KPMG), established legal "
            "databases, and reputable sector-specialist publications."
        )
        if jurisdiction_name:
            return (
                f"Find authoritative sources about: {search_query}, "
                f"scoped specifically to: {jurisdiction_name}. "
                f"{authority_hint} "
                f"{data_depth_hint}"
            )
        return (
            f"Find authoritative sources about: {search_query}. {authority_hint} {data_depth_hint}"
        )

    async def _execute_parallel_search(
        self,
        objective: str,
        max_results: int,
        processor: str,
    ) -> dict:
        """Execute search using Parallel.ai API.

        Args:
            objective: Semantic search objective
            max_results: Number of results to return
            processor: "base" or "pro"

        Returns:
            dict: Search results from Parallel.ai

        Raises:
            Exception: If search fails
        """
        try:
            result = await self.parallel.beta.search(
                objective=objective,
                processor=processor,
                max_results=max_results,
                max_chars_per_result=1500,
            )

            logger.info(f"Parallel.ai search_id: {result.search_id}")
            return result.model_dump()

        except Exception as e:
            logger.error("Parallel.ai search failed", exc_info=e)
            raise ExternalSearchServiceError("Parallel.ai search failed") from e

    def _convert_to_suggested_sources(self, search_results: dict) -> List[SuggestedSource]:
        """Convert Parallel.ai search results to enriched SuggestedSource objects.

        For each result, classifies source authority, scores content depth from
        excerpts, derives an extraction suitability rating, and builds a
        transparent confidence explanation. Results are sorted by suitability
        (high first) then by content depth score descending, so the most
        useful sources always appear at the top regardless of domain.

        Parallel.ai result format::

            {
              "search_id": "...",
              "results": [
                {"url": "...", "title": "...", "excerpts": ["...", ...]}
              ]
            }

        Args:
            search_results: Raw dict response from Parallel.ai Search API.

        Returns:
            List[SuggestedSource]: Enriched, ranked list of suggested sources.
        """
        sources = []

        for result in search_results.get("results", []):
            url = result.get("url", "")
            title = result.get("title", "Untitled")
            excerpts = result.get("excerpts", [])

            combined_excerpts = " ".join(excerpts)
            snippet = (
                combined_excerpts[:500] + "..."
                if len(combined_excerpts) > 500
                else combined_excerpts
            )

            is_official = self._is_official_source(url)
            source_category = self._get_source_category(url)
            content_depth_score = self._assess_content_depth(excerpts, title)
            extraction_suitability = self._get_extraction_suitability(
                source_category, content_depth_score
            )
            confidence_reason = self._build_confidence_reason(
                title, url, excerpts, source_category, content_depth_score
            )

            sources.append(
                SuggestedSource(
                    title=title,
                    url=url,
                    snippet=snippet,
                    confidence_reason=confidence_reason,
                    is_official=is_official,
                    source_category=source_category,
                    content_depth_score=content_depth_score,
                    extraction_suitability=extraction_suitability,
                )
            )

        suitability_order = {"high": 0, "medium": 1, "low": 2}
        sources.sort(
            key=lambda s: (
                suitability_order.get(s.extraction_suitability, 3),
                -s.content_depth_score,
            )
        )
        return sources

    def _is_official_source(self, url: str) -> bool:
        """Determine whether a URL originates from an official government or regulatory body.

        Checks government TLD patterns for major jurisdictions worldwide and common
        subdomain / path patterns used by public institutions. Intentionally broad
        to cover African, Asian, European, and American government domains.

        Args:
            url: The full source URL to evaluate.

        Returns:
            bool: True if the URL matches a known official domain pattern.

        Examples:
            >>> service._is_official_source("https://labour.gov.ng/policies")
            True
            >>> service._is_official_source("https://example.com")
            False
        """
        url_lower = url.lower()

        official_patterns = [
            # Generic government TLDs
            ".gov/",
            ".gov.",
            ".gov.ng",
            ".gov.gh",
            ".gov.za",
            ".gov.ke",
            ".gov.et",
            ".gov.rw",
            ".gov.tz",
            ".gov.ug",
            ".gov.zm",
            ".gov.zw",
            ".gov.bw",
            ".gov.mw",
            ".gov.uk",
            ".gov.au",
            ".gov.nz",
            ".gov.in",
            ".gov.br",
            ".gov.sg",
            ".gov.my",
            ".gov.ph",
            ".gov.id",
            ".gov.jp",
            ".gov.eg",
            ".gov.ma",
            ".gov.dz",
            ".gov.tn",
            ".govt.nz",
            ".gc.ca",
            ".gouv.fr",
            ".gouv.sn",
            ".gouv.ci",
            ".gouv.cm",
            ".gouv.bj",
            ".gob.mx",
            ".gob.ar",
            ".gob.pe",
            ".gob.es",
            ".gob.cl",
            ".go.ke",
            ".go.tz",
            ".go.ug",
            ".go.rw",
            ".go.id",
            ".go.jp",
            # Supranational
            "europa.eu",
            "eur-lex.europa.eu",
            # Institutional keyword patterns
            "parliament.",
            "senate.",
            "congress.",
            "assembly.",
            "ministry",
            "federal",
            "regulatory",
            "regulator.",
            "centralbank",
            "central-bank",
            "reservebank",
            "revenueservice",
            "revenueauthority",
            "taxauthority",
            "customs.",
            "immigration.",
            "labor.gov",
            "labour.gov",
            "justice.gov",
            "treasury.gov",
            "finance.gov",
        ]

        return any(pattern in url_lower for pattern in official_patterns)

    def _build_confidence_reason(
        self,
        title: str,
        url: str,
        excerpts: List[str],
        source_category: str = "other",
        content_depth_score: int = 0,
    ) -> str:
        """Build a human-readable confidence explanation for a suggested source.

        Combines source authority category, content depth score, and URL/title
        signals to produce a short, transparent explanation shown to users.
        Domain-agnostic: works for any regulatory, legal, tax, or compliance topic.

        Args:
            title: Page title from Parallel.ai.
            url: Full source URL.
            excerpts: Content excerpts returned by Parallel.ai.
            source_category: Authority category from _get_source_category.
            content_depth_score: Depth score (0-100) from _assess_content_depth.

        Returns:
            str: Human-readable explanation of why this source was suggested.

        Examples:
            >>> service._build_confidence_reason(
            ...     "PwC Tax Summaries",
            ...     "https://taxsummaries.pwc.com/nigeria",
            ...     ["Employee rate: 8%, employer rate: 10%"],
            ...     "trusted_secondary",
            ...     72,
            ... )
        """
        category_labels = {
            "official_gov": "Official government / regulatory body",
            "intergovernmental": "Intergovernmental organisation",
            "trusted_secondary": "Trusted professional / legal reference",
            "news_media": "Recognised news outlet",
            "other": "General web source",
        }
        category_label = category_labels.get(source_category, "General web source")

        url_depth = url.count("/") - 2
        current_year = datetime.date.today().year
        recent_years = [str(current_year - 1), str(current_year)]
        has_recent_date = any(year in url or year in title for year in recent_years)

        signals = []
        if url_depth >= 3:
            signals.append("deep content page (not a homepage or index)")
        if has_recent_date:
            signals.append("includes recent date marker")
        if content_depth_score >= 60:
            signals.append(f"high factual density (score {content_depth_score}/100)")
        elif content_depth_score >= 30:
            signals.append(f"moderate factual content (score {content_depth_score}/100)")
        else:
            signals.append(
                f"low extractable content detected (score {content_depth_score}/100) — "
                "consider using a deeper sub-page"
            )

        signal_str = "; ".join(signals) if signals else "ranked by Parallel.ai token-relevance"
        return f"{category_label}. {signal_str}."

    def _is_trusted_secondary(self, url: str) -> bool:
        """Detect well-known trusted secondary or professional research sources.

        Covers Big-4 professional services, established legal databases,
        and specialist compliance research platforms. Domain-agnostic: no
        assumption about the topic being researched.

        Args:
            url: The full source URL to evaluate.

        Returns:
            bool: True if the URL belongs to a recognised trusted secondary source.

        Examples:
            >>> service._is_trusted_secondary("https://taxsummaries.pwc.com/nigeria")
            True
            >>> service._is_trusted_secondary("https://random-blog.com")
            False
        """
        url_lower = url.lower()
        trusted_patterns = [
            # Big 4 professional services
            "taxsummaries.pwc.com",
            "pwc.com/tax",
            "dits.deloitte.com",
            "deloitte.com/content/dam",
            "home.kpmg",
            "kpmg.com/xx",
            "ey.com/en_gl/tax",
            "ey.com/en_",
            # Established legal databases
            "legislation.gov.uk",
            "eur-lex.europa.eu",
            "nigerialii.org",
            "ghanalii.org",
            "saflii.org",
            "commonlii.org",
            "worldlii.org",
            "austlii.edu.au",
            "canlii.org",
            "loc.gov/law",
            # Law & compliance research platforms
            "lexology.com",
            "mondaq.com",
            "practicallaw.com",
            "legal500.com",
            "chambers.com",
            "iclg.com",
            "globallegalinsights.com",
            "ibfd.org",
            "taxnotes.com",
        ]
        return any(p in url_lower for p in trusted_patterns)

    def _get_source_category(self, url: str) -> str:
        """Classify a source URL into a broad authority category.

        Categories (highest to lowest trust order):

        - **official_gov**: Government or national regulatory body.
        - **intergovernmental**: International body (ILO, OECD, World Bank…).
        - **trusted_secondary**: Big-4, legal databases, specialist platforms.
        - **news_media**: Recognised news outlets.
        - **other**: Everything else.

        Args:
            url: The full source URL to classify.

        Returns:
            str: One of "official_gov", "intergovernmental", "trusted_secondary",
                "news_media", or "other".

        Examples:
            >>> service._get_source_category("https://ilo.org/employment-law")
            'intergovernmental'
            >>> service._get_source_category("https://labour.gov.ng")
            'official_gov'
        """
        url_lower = url.lower()
        intergovernmental_patterns = [
            "ilo.org",
            "oecd.org",
            "worldbank.org",
            "imf.org",
            "wto.org",
            "adb.org",
            "afdb.org",
            "ifc.org",
            "undp.org",
            "ohchr.org",
            "un.org",
            "europa.eu",
            "idb.org",
        ]
        if any(p in url_lower for p in intergovernmental_patterns):
            return "intergovernmental"
        if self._is_official_source(url):
            return "official_gov"
        if self._is_trusted_secondary(url):
            return "trusted_secondary"
        news_patterns = [
            "reuters.com",
            "bloomberg.com",
            "ft.com",
            "wsj.com",
            "apnews.com",
            "bbc.com",
            "bbc.co.uk",
            "cnbc.com",
            "theguardian.com",
            "businessday.ng",
            "thisdaylive.com",
            "punch.ng",
            "vanguardngr.com",
            "guardian.ng",
            "nairametrics.com",
        ]
        if any(p in url_lower for p in news_patterns):
            return "news_media"
        return "other"

    def _assess_content_depth(self, excerpts: List[str], title: str) -> int:
        """Score how much extractable factual content the excerpts contain (0-100).

        A higher score indicates the page likely contains specific data
        (rates, thresholds, rules, tables) rather than navigation chrome,
        promotional copy, or abstract overviews. Completely domain-agnostic.

        Positive signals: numeric values, percentages, currency amounts,
        legal/regulatory keywords, structural markers, multiple excerpt blocks.
        Negative signals: navigation-only phrases ("read more", "subscribe", etc.).

        Args:
            excerpts: List of content excerpts returned by Parallel.ai.
            title: Page title (used as a supplementary fallback signal).

        Returns:
            int: Content depth score in the range [0, 100].

        Examples:
            >>> service._assess_content_depth(
            ...     ["Minimum wage is ₦70,000 per month effective July 2024."],
            ...     "National Minimum Wage Act",
            ... )
            >>> # Returns a high score — currency figure + legal noun + date
        """
        if not excerpts:
            return 0

        combined = " ".join(excerpts).lower()
        total_chars = sum(len(e) for e in excerpts)
        score = 0

        numeric_hits = len(
            re.findall(
                r"\d+[\.\d]*\s*%"
                r"|₦\s*[\d,]+"
                r"|\$[\d,]+"
                r"|£[\d,]+"
                r"|€[\d,]+"
                r"|\b\d{4}\b"
                r"|\b\d+[\.,]\d+\b",
                combined,
            )
        )
        score += min(numeric_hits * 8, 30)

        rule_keywords = [
            "shall",
            "must",
            "required",
            "minimum",
            "maximum",
            "penalty",
            "deadline",
            "within",
            "days",
            "months",
            "entitled",
            "prohibited",
            "liable",
            "subject to",
            "pursuant to",
            "in accordance",
            "section",
            "article",
            "clause",
            "subsection",
            "regulation",
            "act ",
            "law ",
            "directive",
            "order",
            "circular",
        ]
        rule_hits = sum(1 for kw in rule_keywords if kw in combined)
        score += min(rule_hits * 3, 25)

        if total_chars >= 1500:
            score += 20
        elif total_chars >= 800:
            score += 13
        elif total_chars >= 300:
            score += 6

        if len(excerpts) >= 4:
            score += 10
        elif len(excerpts) >= 2:
            score += 5

        nav_phrases = [
            "click here",
            "read more",
            "learn more",
            "latest news",
            "subscribe",
            "contact us",
            "follow us",
            "sign up",
            "about us",
        ]
        nav_hits = sum(1 for kw in nav_phrases if kw in combined)
        score -= min(nav_hits * 7, 20)

        return max(0, min(score, 100))

    def _get_extraction_suitability(self, source_category: str, content_depth_score: int) -> str:
        """Derive an AI extraction suitability rating from category and depth score.

        Official and intergovernmental sources are granted a lower depth threshold
        because their content structure is inherently authoritative even when the
        available excerpt text is sparse. Unverified sources require higher depth
        evidence before being rated as high-suitability.

        Args:
            source_category: Authority category from _get_source_category.
            content_depth_score: Depth score (0-100) from _assess_content_depth.

        Returns:
            str: "high", "medium", or "low".

        Examples:
            >>> service._get_extraction_suitability("official_gov", 55)
            'high'
            >>> service._get_extraction_suitability("other", 10)
            'low'
        """
        if source_category in ("official_gov", "intergovernmental"):
            return "high" if content_depth_score >= 35 else "medium"
        if source_category == "trusted_secondary":
            return "high" if content_depth_score >= 30 else "medium"
        if content_depth_score >= 50:
            return "high"
        if content_depth_score >= 22:
            return "medium"
        return "low"

    async def _validate_urls_quick(
        self,
        sources: List[SuggestedSource],
    ) -> List[SuggestedSource]:
        """Quick validation to ensure URLs are reachable.

        Note: This is optional since Parallel.ai already returns quality URLs.
        Only does a quick HEAD check without extensive validation.

        Args:
            sources: List of sources to validate

        Returns:
            List[SuggestedSource]: Sources with reachable URLs
        """
        valid_sources = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if not sources:
            return valid_sources

        validation_concurrency = min(10, len(sources))
        semaphore = asyncio.Semaphore(validation_concurrency)

        async def _validate_source(source: SuggestedSource) -> Optional[SuggestedSource]:
            try:
                async with semaphore:
                    resp = await self.http_client.head(
                        source.url,
                        follow_redirects=True,
                        timeout=3.0,
                        headers=headers,
                    )

                if resp.status_code < 400:
                    return source

                logger.debug(f"Skipping {source.url} - HTTP {resp.status_code}")
                return None

            except Exception as e:
                logger.debug(f"Skipping {source.url} - {str(e)}")
                return None

        validation_results = await asyncio.gather(*(_validate_source(source) for source in sources))
        valid_sources = [source for source in validation_results if source is not None]

        logger.info(f"Validated {len(valid_sources)}/{len(sources)} URLs")
        return valid_sources

    async def _log_usage(
        self,
        user_id: Optional[UUID],
        organization_id: Optional[UUID],
        url_extracted: str,
        endpoint_name: str,
        success: bool,
        cost: Decimal,
        latency_ms: int,
        content_size_bytes: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Log Parallel.ai search usage to database for monitoring and billing.

        Records each search operation with cost, performance metrics, and error details.
        Logs are stored in the parallel_usage_logs table for comprehensive analytics.

        Args:
            user_id: User who initiated the search.
            organization_id: Organization context for the search.
            url_extracted: Search query (formatted as "search:<query>").
            endpoint_name: API endpoint name ("parallel_search").
            success: Whether the search succeeded.
            cost: Estimated API cost in USD.
            latency_ms: Search latency in milliseconds.
            content_size_bytes: Size of results (0 for search API).
            error_message: Error details if search failed.

        Examples:
            >>> await self._log_usage(
            ...     user_id=user.id,
            ...     organization_id=org.id,
            ...     url_extracted="search:crypto licensing",
            ...     endpoint_name="parallel_search",
            ...     success=True,
            ...     latency_ms=1200,
            ...     content_size_bytes=0,
            ...     cost=Decimal("0.001")
            ... )
        """
        if not self.db_session:
            logger.debug("Database session not provided, skipping usage logging")
            return

        try:
            usage_log = ParallelUsageLog(
                user_id=user_id,
                organization_id=organization_id,
                url_extracted=url_extracted[:2048],
                endpoint_name=endpoint_name,
                success=success,
                cost=cost,
                latency_ms=latency_ms,
                content_size_bytes=content_size_bytes,
                error_message=error_message[:1000] if error_message else None,
            )
            self.db_session.add(usage_log)
            try:
                await self.db_session.commit()
            except Exception as commit_error:
                logger.debug(
                    f"Commit failed during usage logging (this is non-critical): {commit_error}"
                )
                try:
                    await self.db_session.rollback()
                except Exception:
                    pass
                return

            logger.debug(
                f"Logged Parallel.ai usage: {endpoint_name} - "
                f"{'success' if success else 'failure'} - cost=${cost}"
            )
        except Exception as e:
            logger.debug(f"Failed to log Parallel.ai usage (non-critical): {e}")
            try:
                await self.db_session.rollback()
            except Exception:
                pass

    async def close(self):
        """Close HTTP client connections."""
        await self.http_client.aclose()

    async def retrieve_session(self, user_id: uuid.UUID, session_id: str) -> List[SuggestedSource]:
        """
        Retrieve and validate a cached search session.
        Returns the session data if valid, or raises an error response.
        """
        if not user_id:
            logger.warning(
                "User ID is empty when retrieving search session (session_id=%s)", session_id
            )
            return None

        logger.info(
            "Retrieving sources from cache for user %s with session_id %s", user_id, session_id
        )

        cached_data = await get_search_session(user_id, session_id)

        if not cached_data:
            logger.warning("Session %s not found or expired for user %s", session_id, user_id)
            return []

        sources = cached_data.get("sources")
        if not sources:
            logger.error("Cached session %s for user %s contains no sources", session_id, user_id)
            return []

        return sources
