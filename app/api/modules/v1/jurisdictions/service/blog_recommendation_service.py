"""Blog recommendation service for geopolitical and thematic comparisons.

This service implements the BlogRecommendationEngine which populates the 6 comparison
slots for the interactive blog guide:
1. Subdivision Finder (sibling/child jurisdictions with published posts)
2. Geopolitical Bordering Neighbors (countries in the same subregion from countries.csv)
3. Reference Frameworks (anchor jurisdictions like EU or US Federal)
4. Comparable Laws (similar frameworks matching by topic keyword tags)
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.core.config import settings
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.blog_schema import RelatedJurisdictionResponse
from app.api.modules.v1.jurisdictions.service.blog_artifact_service import build_public_resource_url
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize a geographic or jurisdiction name for robust matching."""
    return " ".join(name.strip().lower().split())


class BlogRecommendationEngine:
    """Computes dynamic related jurisdiction recommendations to fill comparison slots."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the recommendation engine.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_recommendations(
        self,
        post: JurisdictionBlogPost,
    ) -> List[RelatedJurisdictionResponse]:
        """Compute up to 6 related jurisdictions for the given blog post.

        Args:
            post: The source blog post to generate recommendations for.

        Returns:
            List[RelatedJurisdictionResponse]: List of up to 6 unique recommendation cards.
        """
        recommendations: List[RelatedJurisdictionResponse] = []
        seen_slugs: Set[str] = {post.slug}

        # 1. Fetch the jurisdiction of the current post
        jurisdiction_stmt = (
            select(Jurisdiction)
            .options(selectinload(Jurisdiction.parent))
            .where(Jurisdiction.id == post.jurisdiction_id)
        )
        jurisdiction_result = await self.db.execute(jurisdiction_stmt)
        current_jur = jurisdiction_result.scalar_one_or_none()
        if not current_jur:
            return []

        # Step 1: Subdivisions
        subdivisions = await self._get_subdivisions(current_jur, seen_slugs)
        recommendations.extend(subdivisions)
        if len(recommendations) >= 6:
            return recommendations[:6]

        # Step 2: Geopolitical Neighbors
        neighbors = await self._get_neighbors(current_jur, seen_slugs)
        recommendations.extend(neighbors)
        if len(recommendations) >= 6:
            return recommendations[:6]

        # Step 3: Reference Frameworks
        reference_frameworks = await self._get_reference_frameworks(current_jur, seen_slugs)
        recommendations.extend(reference_frameworks)
        if len(recommendations) >= 6:
            return recommendations[:6]

        # Step 4: Comparable Laws (Similar Frameworks)
        comparable_laws = await self._get_comparable_laws(post, current_jur, seen_slugs)
        recommendations.extend(comparable_laws)

        return recommendations[:6]

    async def _get_subdivisions(
        self,
        current_jur: Jurisdiction,
        seen_slugs: Set[str],
    ) -> List[RelatedJurisdictionResponse]:
        """Fetch sibling or child jurisdictions under the same hierarchy branch."""
        subdivisions: List[RelatedJurisdictionResponse] = []

        stmt = select(JurisdictionBlogPost, Jurisdiction).join(
            Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id
        )

        if current_jur.parent_id is not None:
            # Sibling search (share same parent_id)
            stmt = stmt.where(
                Jurisdiction.parent_id == current_jur.parent_id,
                Jurisdiction.id != current_jur.id,
                JurisdictionBlogPost.is_published.is_(True),
            )
        else:
            # Children search (parent_id matches current_jur.id)
            stmt = stmt.where(
                Jurisdiction.parent_id == current_jur.id,
                JurisdictionBlogPost.is_published.is_(True),
            )

        result = await self.db.execute(stmt)
        rows = result.all()

        parent_name = current_jur.parent.name if current_jur.parent else current_jur.name

        for p, j in rows:
            if p.slug in seen_slugs:
                continue
            seen_slugs.add(p.slug)

            resource_path = await BlogGenerationService._build_public_resource_path(self.db, j, p)
            url = build_public_resource_url(resource_path)

            subdivisions.append(
                RelatedJurisdictionResponse(
                    type="Subdivision",
                    name=j.name,
                    region=parent_name,
                    url=url,
                )
            )

        return subdivisions

    async def _get_neighbors(
        self,
        current_jur: Jurisdiction,
        seen_slugs: Set[str],
    ) -> List[RelatedJurisdictionResponse]:
        """Fetch bordering/neighboring countries in the same subregion from countries.csv."""
        neighbors: List[RelatedJurisdictionResponse] = []

        # Find the root country ancestor
        root_jur = current_jur
        visited: Set[UUID] = {root_jur.id}
        while root_jur.parent_id is not None:
            if root_jur.parent_id in visited:
                break
            visited.add(root_jur.parent_id)
            parent = await self.db.get(Jurisdiction, root_jur.parent_id)
            if not parent:
                break
            root_jur = parent

        normalized_root_name = _normalize_name(root_jur.name)

        # Load CSV and find subregion
        csv_path = settings.CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH or "dataset/countries.csv"
        resolved_path = self._resolve_csv_path(csv_path)
        if not resolved_path:
            logger.warning("countries.csv could not be resolved for neighbors search.")
            return []

        subregion: Optional[str] = None
        neighbor_country_names: Set[str] = set()

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Find subregion of our current country
                for row in rows:
                    name_in_csv = row.get("name") or ""
                    if _normalize_name(name_in_csv) == normalized_root_name:
                        subregion = row.get("subregion")
                        break

                # Get all other countries in same subregion
                if subregion:
                    for row in rows:
                        name_in_csv = row.get("name") or ""
                        if (
                            row.get("subregion") == subregion
                            and _normalize_name(name_in_csv) != normalized_root_name
                        ):
                            neighbor_country_names.add(_normalize_name(name_in_csv))
        except Exception as e:
            logger.error(f"Error parsing countries.csv for neighbors: {e}", exc_info=True)
            return []

        if not neighbor_country_names:
            return []

        # Query database for published blog posts belonging to these neighboring countries
        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(
                Jurisdiction.parent_id.is_(None),  # Must be top-level countries
                JurisdictionBlogPost.is_published.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        for p, j in rows:
            if _normalize_name(j.name) in neighbor_country_names:
                if p.slug in seen_slugs:
                    continue
                seen_slugs.add(p.slug)

                resource_path = await BlogGenerationService._build_public_resource_path(
                    self.db, j, p
                )
                url = build_public_resource_url(resource_path)

                neighbors.append(
                    RelatedJurisdictionResponse(
                        type="Neighboring Country",
                        name=j.name,
                        region=subregion or "Global",
                        url=url,
                    )
                )

        return neighbors

    async def _get_reference_frameworks(
        self,
        current_jur: Jurisdiction,
        seen_slugs: Set[str],
    ) -> List[RelatedJurisdictionResponse]:
        """Fetch general baseline anchor frameworks like US Federal or EU."""
        frameworks: List[RelatedJurisdictionResponse] = []

        # Find top-level published blog posts matching key names or containing 'Federal' or 'Union'
        anchor_terms = ["federal", "union", "united states", "united kingdom", "european union", "eu"]

        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(
                JurisdictionBlogPost.is_published.is_(True),
                Jurisdiction.id != current_jur.id,
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        for p, j in rows:
            normalized_name = _normalize_name(j.name)
            # Check if name is in anchors or contains 'federal' / 'union' / 'eu'
            is_anchor = any(term in normalized_name for term in anchor_terms)
            if is_anchor:
                if p.slug in seen_slugs:
                    continue
                seen_slugs.add(p.slug)

                resource_path = await BlogGenerationService._build_public_resource_path(
                    self.db, j, p
                )
                url = build_public_resource_url(resource_path)

                # Determine continent/region name
                region_name = "Global"
                if "united states" in normalized_name or "federal" in normalized_name:
                    region_name = "North America"
                elif "union" in normalized_name or "uk" in normalized_name or "united kingdom" in normalized_name:
                    region_name = "Europe"

                frameworks.append(
                    RelatedJurisdictionResponse(
                        type="Reference Framework",
                        name=j.name,
                        region=region_name,
                        url=url,
                    )
                )

        return frameworks

    async def _get_comparable_laws(
        self,
        post: JurisdictionBlogPost,
        current_jur: Jurisdiction,
        seen_slugs: Set[str],
    ) -> List[RelatedJurisdictionResponse]:
        """Fetch similar frameworks matching topic keywords/tags."""
        comparable: List[RelatedJurisdictionResponse] = []
        if not post.keywords:
            return []

        # Normalize keywords to lowercase
        keywords_lower = [kw.strip().lower() for kw in post.keywords if kw.strip()]
        if not keywords_lower:
            return []

        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(
                JurisdictionBlogPost.is_published.is_(True),
                Jurisdiction.id != current_jur.id,
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        for p, j in rows:
            if p.slug in seen_slugs:
                continue

            # Check overlap in keywords
            other_kws = [okw.strip().lower() for okw in p.keywords] if p.keywords else []
            overlap = set(keywords_lower).intersection(other_kws)

            if overlap:
                seen_slugs.add(p.slug)
                resource_path = await BlogGenerationService._build_public_resource_path(
                    self.db, j, p
                )
                url = build_public_resource_url(resource_path)

                # Region name
                region_name = "Global"
                if j.parent_id is not None:
                    parent = await self.db.get(Jurisdiction, j.parent_id)
                    if parent:
                        region_name = parent.name
                else:
                    region_name = j.name

                comparable.append(
                    RelatedJurisdictionResponse(
                        type="Similar Framework",
                        name=j.name,
                        region=region_name,
                        url=url,
                    )
                )

        return comparable

    def _resolve_csv_path(self, csv_path: str) -> Optional[Path]:
        """Resolve CSV path across absolute and repo-relative forms."""
        if not csv_path:
            return None

        raw_path = Path(csv_path)
        candidates: List[Path] = [raw_path]

        trimmed = csv_path.lstrip("/\\")
        if trimmed and trimmed != csv_path:
            candidates.append(Path.cwd() / trimmed)

        if not raw_path.is_absolute():
            candidates.append(Path.cwd() / raw_path)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None
