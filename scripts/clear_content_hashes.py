"""Clear content_hash for campaign jurisdictions to force regeneration."""
import sys
import uuid

from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.jurisdictions.models import Jurisdiction, JurisdictionBlogPost
from sqlmodel import select


def clear_content_hashes(campaign_id: str) -> int:
    """Clear content_hash for all blog posts in a campaign."""
    campaign_uuid = uuid.UUID(campaign_id)
    count = 0

    with SyncSessionLocal() as db:
        # Get all jurisdiction IDs for the campaign
        jur_ids = db.exec(
            select(Jurisdiction.id).where(Jurisdiction.campaign_id == campaign_uuid)
        ).all()

        if not jur_ids:
            print(f"No jurisdictions found for campaign {campaign_id}")
            return 0

        print(f"Found {len(jur_ids)} jurisdictions for campaign {campaign_id}")

        # Clear content_hash for each jurisdiction's blog post
        for jur_id in jur_ids:
            blog = db.exec(
                select(JurisdictionBlogPost).where(
                    JurisdictionBlogPost.jurisdiction_id == jur_id
                )
            ).first()

            if blog and blog.content_hash:
                blog.content_hash = ""  # Empty string to force regeneration
                db.add(blog)
                count += 1
                print(f"Cleared content_hash for jurisdiction {jur_id}")

        db.commit()
        print(f"Cleared content_hash for {count} blog posts")

    return count


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clear_content_hashes.py <campaign_id>")
        sys.exit(1)

    campaign_id = sys.argv[1]
    clear_content_hashes(campaign_id)