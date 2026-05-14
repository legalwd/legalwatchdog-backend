"""Data normalization service for semantic field name matching.

This service normalizes extracted data structures to ensure consistent field
names across different LLM models, enabling accurate diff analysis that focuses
on factual changes rather than field name variations.

Example:
    Different models may extract the same data with different field names:
    - Model A: {"visa_price": "$500", "audit_deadline": "2024-12-31"}
    - Model B: {"price_visa": "$600", "audit_submission_deadline": "2024-12-31"}

    After normalization, both use canonical names:
    - Normalized: {"visa_price": "$600", "audit_deadline": "2024-12-31"}
"""

import difflib
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.scraping.models.field_mapping import FieldMapping

logger = logging.getLogger(__name__)


class DataNormalizationService:
    """Normalizes extracted data for consistent field naming across LLM models.

    Uses cached field mappings and fuzzy string matching to identify semantically
    equivalent field names and map them to canonical forms.
    """

    SIMILARITY_THRESHOLD = 0.75
    HIGH_CONFIDENCE_THRESHOLD = 0.90

    def __init__(self, db: Optional[Session | AsyncSession] = None):
        """Initialize normalization service.

        Args:
            db: Optional database session (sync or async). If not provided, creates its own.
        """
        self.db = db
        self._field_cache: Dict[str, Dict[str, str]] = {}
        self._is_async = isinstance(db, AsyncSession) if db else False

    def normalize_extracted_data(self, data: Dict[str, Any], source_id: str) -> Dict[str, Any]:
        """Normalize field names in extracted data to canonical forms.

        Args:
            data: Extracted data with potentially varied field names
            source_id: Source UUID for field mapping lookup

        Returns:
            Normalized data with canonical field names

        Example:
            >>> service = DataNormalizationService()
            >>> data = {"price_visa": "$600", "audit_submission_deadline": "2024-12-31"}
            >>> normalized = service.normalize_extracted_data(data, "source-uuid")
            >>> normalized
            {"visa_price": "$600", "audit_deadline": "2024-12-31"}
        """
        if not data:
            return data

        if "key_value_pairs" in data:
            kv_data = data.get("key_value_pairs", {})
        else:
            kv_data = data

        if not isinstance(kv_data, dict):
            logger.warning(f"Cannot normalize non-dict data: {type(kv_data)}")
            return data

        field_mappings = self._get_field_mappings(source_id)
        canonical_fields = self._get_canonical_fields(source_id)

        normalized_data = {}

        for original_field, value in kv_data.items():
            if original_field in field_mappings:
                canonical_name = field_mappings[original_field]
                logger.debug(f"Using cached mapping: {original_field} -> {canonical_name}")
            else:
                canonical_name, similarity = self._find_canonical_field_name(
                    original_field, canonical_fields
                )

                if canonical_name and similarity >= self.SIMILARITY_THRESHOLD:
                    self._store_field_mapping(
                        source_id=source_id,
                        original=original_field,
                        canonical=canonical_name,
                        similarity=similarity,
                    )
                    field_mappings[original_field] = canonical_name
                    logger.info(
                        f"Created new mapping: {original_field} -> {canonical_name} "
                        f"(similarity: {similarity:.2f})"
                    )
                else:
                    canonical_name = original_field
                    canonical_fields.append(canonical_name)
                    self._store_field_mapping(
                        source_id=source_id,
                        original=original_field,
                        canonical=canonical_name,
                        similarity=1.0,
                    )
                    field_mappings[original_field] = canonical_name
                    logger.info(f"New canonical field: {canonical_name}")

            normalized_data[canonical_name] = value

        if "key_value_pairs" in data:
            return {"key_value_pairs": normalized_data}

        return normalized_data

    def _get_field_mappings(self, source_id: str) -> Dict[str, str]:
        """Get cached field mappings for a source.

        Args:
            source_id: Source UUID

        Returns:
            Dictionary mapping original field names to canonical names
        """
        if source_id in self._field_cache:
            return self._field_cache[source_id]

        mappings = {}

        async def load_from_db_async(db: AsyncSession):
            stmt = select(FieldMapping).where(FieldMapping.source_id == UUID(source_id))
            result = await db.execute(stmt)
            results = result.scalars().all()

            for mapping in results:
                mappings[mapping.original_field_name] = mapping.canonical_field_name

        def load_from_db_sync(db: Session):
            stmt = select(FieldMapping).where(FieldMapping.source_id == UUID(source_id))
            results = db.exec(stmt).all()

            for mapping in results:
                mappings[mapping.original_field_name] = mapping.canonical_field_name

        if self.db:
            if self._is_async:
                # For async sessions, we can't use them in sync context
                # Skip database lookup and rely on cache only
                logger.warning(f"AsyncSession detected - using cache only for source {source_id}")
            else:
                load_from_db_sync(self.db)
        else:
            with SyncSessionLocal() as db:
                load_from_db_sync(db)

        self._field_cache[source_id] = mappings
        logger.debug(f"Loaded {len(mappings)} field mappings for source {source_id}")

        return mappings

    def _get_canonical_fields(self, source_id: str) -> List[str]:
        """Get list of canonical field names for a source.

        Args:
            source_id: Source UUID

        Returns:
            List of canonical field names
        """
        canonical_fields = []

        def load_from_db_sync(db: Session):
            stmt = (
                select(FieldMapping.canonical_field_name)
                .where(FieldMapping.source_id == UUID(source_id))
                .distinct()
            )
            results = db.exec(stmt).all()
            canonical_fields.extend(results)

        if self.db:
            if self._is_async:
                logger.warning("AsyncSession detected - using cache only for canonical fields")
            else:
                load_from_db_sync(self.db)
        else:
            with SyncSessionLocal() as db:
                load_from_db_sync(db)

        return canonical_fields

    def _find_canonical_field_name(
        self, field_name: str, existing_fields: List[str]
    ) -> Tuple[Optional[str], float]:
        """Find the best matching canonical field name using fuzzy matching.

        Args:
            field_name: Original field name to match
            existing_fields: List of existing canonical field names

        Returns:
            Tuple of (canonical_name, similarity_score)
            Returns (None, 0.0) if no good match found

        Example:
            >>> service = DataNormalizationService()
            >>> canonical, score = service._find_canonical_field_name(
            ...     "price_visa",
            ...     ["visa_price", "audit_deadline"]
            ... )
            >>> canonical
            'visa_price'
            >>> score > 0.9
            True
        """
        if not existing_fields:
            return None, 0.0

        similarities = [
            (existing, self._calculate_field_similarity(field_name, existing))
            for existing in existing_fields
        ]

        # Get best match
        best_match, best_score = max(similarities, key=lambda x: x[1])

        logger.debug(
            f"Best match for '{field_name}': '{best_match}' (similarity: {best_score:.2f})"
        )

        if best_score >= self.SIMILARITY_THRESHOLD:
            return best_match, best_score

        return None, 0.0

    def _calculate_field_similarity(self, field1: str, field2: str) -> float:
        """Calculate similarity between two field names.

        Uses multiple techniques:
        1. Exact match (1.0)
        2. Normalized match (case-insensitive, remove underscores) (0.95)
        3. Sequence matcher for fuzzy matching (0.0-1.0)
        4. Word overlap bonus

        Args:
            field1: First field name
            field2: Second field name

        Returns:
            Similarity score between 0.0 and 1.0

        Example:
            >>> service = DataNormalizationService()
            >>> service._calculate_field_similarity("visa_price", "price_visa")
            0.95
            >>> service._calculate_field_similarity("audit_deadline", "audit_submission_deadline")
            0.82
        """
        if field1 == field2:
            return 1.0

        norm1 = field1.lower().replace("_", "")
        norm2 = field2.lower().replace("_", "")

        if norm1 == norm2:
            return 0.95

        base_similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()

        words1 = set(field1.lower().split("_"))
        words2 = set(field2.lower().split("_"))

        if words1 and words2:
            word_overlap = len(words1 & words2) / len(words1 | words2)
            if word_overlap > 0.5:
                base_similarity = max(base_similarity, 0.7 + (word_overlap * 0.3))

        return base_similarity

    def _store_field_mapping(
        self, source_id: str, original: str, canonical: str, similarity: float
    ) -> None:
        """Store a field mapping in the database.

        Args:
            source_id: Source UUID
            original: Original field name
            canonical: Canonical field name
            similarity: Similarity score
        """

        def store_in_db_sync(db: Session):
            stmt = select(FieldMapping).where(
                FieldMapping.source_id == UUID(source_id),
                FieldMapping.original_field_name == original,
            )
            existing = db.exec(stmt).first()

            if existing:
                if similarity > existing.similarity_score:
                    existing.canonical_field_name = canonical
                    existing.similarity_score = similarity
                    existing.approved = similarity >= self.HIGH_CONFIDENCE_THRESHOLD
                    db.commit()
                    logger.debug(f"Updated mapping: {original} -> {canonical}")
                return

            mapping = FieldMapping(
                source_id=UUID(source_id),
                original_field_name=original,
                canonical_field_name=canonical,
                similarity_score=similarity,
                approved=similarity >= self.HIGH_CONFIDENCE_THRESHOLD,
            )
            db.add(mapping)
            db.commit()
            logger.debug(f"Stored new mapping: {original} -> {canonical}")

        if self.db:
            if self._is_async:
                logger.warning("AsyncSession detected - skipping field mapping storage")
            else:
                store_in_db_sync(self.db)
        else:
            with SyncSessionLocal() as db:
                store_in_db_sync(db)
