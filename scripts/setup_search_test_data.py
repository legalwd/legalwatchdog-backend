"""Script to set up sample data for testing the search endpoint.

Run this after migrations are complete:
    python -m scripts.setup_search_test_data
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source


async def setup_test_data():
    """Create sample data for testing the search endpoint"""

    async with AsyncSessionLocal() as session:
        try:
            # Create organization
            org = Organization(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="Test Organization",
                description="For testing search functionality",
            )
            session.add(org)
            await session.flush()
            print("✓ Created test organization")

            # Create project
            project = Project(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                org_id=UUID("00000000-0000-0000-0000-000000000001"),
                title="Legal Watch Dog Test Project",
                description="Testing project for search endpoint",
            )
            session.add(project)
            await session.flush()
            print("✓ Created test project")

            # Create jurisdiction
            jurisdiction = Jurisdiction(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="Federal Law",
                description="US Federal Laws and Regulations",
                project_id=UUID("00000000-0000-0000-0000-000000000001"),
            )
            session.add(jurisdiction)
            await session.flush()
            print("✓ Created test jurisdiction")

            # Create source
            source = Source(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="Federal Register",
                url="https://www.federalregister.gov",
                jurisdiction_id=UUID("00000000-0000-0000-0000-000000000001"),
                source_type="WEB",
                scrape_frequency="DAILY",
            )
            session.add(source)
            await session.flush()
            print("✓ Created test source")

            # Create data revisions with searchable content
            # Using only the columns that exist in the actual database schema
            revisions = [
                DataRevision(
                    source_id=UUID("00000000-0000-0000-0000-000000000001"),
                    minio_object_key="federal_tax_regulations_2025.pdf",
                    ai_summary="This document discusses federal tax "
                    "regulations, corporate compliance"
                    "requirements, and new filing procedures"
                    "for businesses operating across state lines.",
                    scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    was_change_detected=True,
                    extracted_data={"document_type": "regulatory", "topic": "taxation"},
                ),
                DataRevision(
                    source_id=UUID("00000000-0000-0000-0000-000000000001"),
                    minio_object_key="environmental_protection_laws.pdf",
                    ai_summary="Environmental protection laws and climate change policies"
                    "for corporations. Includes carbon emission standards,"
                    "renewable energy requirements, and sustainability reporting"
                    "mandates.",
                    scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    was_change_detected=True,
                    extracted_data={"document_type": "environmental", "topic": "climate"},
                ),
                DataRevision(
                    source_id=UUID("00000000-0000-0000-0000-000000000001"),
                    minio_object_key="labor_law_updates.pdf",
                    ai_summary="Labor laws regarding employee rights,"
                    "workplace safety regulations, minimum wage updates,"
                    "and overtime compensation requirements for various industries.",
                    scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    was_change_detected=True,
                    extracted_data={"document_type": "labor", "topic": "employment"},
                ),
                DataRevision(
                    source_id=UUID("00000000-0000-0000-0000-000000000001"),
                    minio_object_key="data_privacy_regulations.pdf",
                    ai_summary="Data privacy regulations covering consumer"
                    "information protection, GDPR compliance,"
                    "cybersecurity requirements,"
                    "and breach notification procedures.",
                    scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    was_change_detected=True,
                    extracted_data={"document_type": "privacy", "topic": "data_protection"},
                ),
                DataRevision(
                    source_id=UUID("00000000-0000-0000-0000-000000000001"),
                    minio_object_key="healthcare_compliance.pdf",
                    ai_summary="Healthcare industry compliance"
                    "regulations including HIPAA requirements,"
                    "patient data security, insurance provider"
                    "obligations, and medical records management.",
                    scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    was_change_detected=True,
                    extracted_data={"document_type": "healthcare", "topic": "compliance"},
                ),
            ]

            for revision in revisions:
                session.add(revision)

            await session.flush()
            print(f"Created {len(revisions)} test data revisions")

            # Update search vectors for all revisions
            await session.execute(
                text("""
                    UPDATE data_revisions 
                    SET search_vector = to_tsvector('english', 
                        COALESCE(minio_object_key, '') || ' ' || 
                        COALESCE(ai_summary, '')
                    )
                    WHERE source_id = :source_id
                """),
                {"source_id": str(UUID("00000000-0000-0000-0000-000000000001"))},
            )

            await session.commit()
            print("✓ Updated search vectors")
            print("\nSample data setup complete!")
            print("\nYou can now test the search endpoint with queries like:")
            print("  - 'tax' (should find 1 result)")
            print("  - 'environment' (should find 1 result)")
            print("  - 'law' (should find 2 results)")
            print("  - 'regulations' (should find 4 results)")
            print("  - 'compliance' (should find 3 results)")

        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    print("Setting up sample data for search endpoint testing...\n")
    asyncio.run(setup_test_data())
