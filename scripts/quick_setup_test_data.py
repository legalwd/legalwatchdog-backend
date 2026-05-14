"""
Complete test data setup for ticket endpoint - uses existing organization
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import text

from app.api.db.database import get_db
from app.api.utils.password import hash_password


async def setup_test_data():
    """Setup complete test data using existing organization."""

    async for db in get_db():
        try:
            print("\n" + "=" * 80)
            print("🚀 SETTING UP COMPLETE TEST DATA")
            print("=" * 80 + "\n")

            org_result = await db.execute(
                text(
                    "SELECT id, name FROM organizations "
                    "WHERE name = 'Test Organization for Tickets' LIMIT 1"
                )
            )
            org = org_result.fetchone()

            if not org:
                print("📝 Creating test organization...")
                org_id = "69762be1-207f-4a10-82b7-a19ff21b84bc"
                await db.execute(
                    text("""
                        INSERT INTO organizations (
                            id, name, is_active, created_at, updated_at
                        )
                        VALUES (:id, :name, true, :now, :now)
                    """),
                    {
                        "id": org_id,
                        "name": "Test Organization for Tickets",
                        "now": datetime.now(timezone.utc),
                    },
                )
                print("✅ Organization created: Test Organization for Tickets\n")
            else:
                org_id = org[0]
                print(f"✅ Using organization: {org[1]}")
                print(f"   ID: {org_id}\n")

            print("📝 Creating test user...")
            user_id = "894bd06f-e49a-4bad-b8ad-8522abdd0896"
            email = "ticket.test@example.com"
            password = "Test123!"
            hashed_pw = hash_password(password)

            # Delete in order to respect foreign key constraints
            await db.execute(
                text("DELETE FROM tickets WHERE created_by_user_id = :uid"), {"uid": user_id}
            )
            await db.execute(
                text("DELETE FROM project_users WHERE user_id = :uid"), {"uid": user_id}
            )
            await db.execute(
                text("DELETE FROM user_organizations WHERE user_id = :uid"), {"uid": user_id}
            )
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})

            await db.execute(
                text("""
                    INSERT INTO users (
                        id, email, hashed_password, auth_provider, name,
                        is_active, is_verified, created_at, updated_at
                    )
                    VALUES (
                        :id, :email, :password, 'local', 'Ticket Test User',
                        true, true, :now, :now
                    )
                """),
                {
                    "id": user_id,
                    "email": email,
                    "password": hashed_pw,
                    "now": datetime.now(timezone.utc),
                },
            )
            print(f"✅ User created: {email}\n")

            print("📝 Getting admin role...")
            role_result = await db.execute(
                text("""
                    SELECT id FROM roles
                    WHERE organization_id = :org_id AND name = 'Admin'
                    LIMIT 1
                """),
                {"org_id": org_id},
            )
            role = role_result.fetchone()

            if not role:
                role_id = "ec4d93d3-1408-425a-b759-dedb00f0e277"
                await db.execute(
                    text(
                        """
                        INSERT INTO roles (
                            id, organization_id, name, description,
                            permissions, created_at
                        )
                        VALUES (:id, :org_id, 'Admin', 'Administrator role', :perms, :now)
                        """
                    ),
                    {
                        "id": role_id,
                        "org_id": org_id,
                        "perms": '{"manage_all": true}',
                        "now": datetime.now(timezone.utc),
                    },
                )
                print("✅ Admin role created\n")
            else:
                role_id = role[0]
                print("✅ Using existing admin role\n")

            print("📝 Adding user to organization...")
            await db.execute(
                text("""
                    INSERT INTO user_organizations (
                        id, user_id, organization_id, role_id, is_active,
                        joined_at, created_at, updated_at, is_deleted
                    )
                    VALUES (
                        gen_random_uuid(), :user_id, :org_id, :role_id, true,
                        :now, :now, :now, false
                    )
                """),
                {
                    "user_id": user_id,
                    "org_id": org_id,
                    "role_id": role_id,
                    "now": datetime.now(timezone.utc),
                },
            )
            print("✅ User added to organization\n")

            print("📝 Creating billing account...")
            billing_check = await db.execute(
                text("SELECT id FROM billing_accounts WHERE organization_id = :org_id"),
                {"org_id": org_id},
            )
            if not billing_check.fetchone():
                await db.execute(
                    text("""
                        INSERT INTO billing_accounts (
                            id, organization_id, status, currency,
                            cancel_at_period_end, metadata,
                            created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), :org_id, 'ACTIVE', 'USD',
                            false, '{}',
                            :now, :now
                        )
                    """),
                    {"org_id": org_id, "now": datetime.now(timezone.utc)},
                )
                print("✅ Billing account created (ACTIVE, USD)\n")
            else:
                print("✅ Using existing billing account\n")

            print("📝 Getting project...")
            project_result = await db.execute(
                text("""
                    SELECT id, title FROM projects
                    WHERE org_id = :org_id AND is_deleted = false
                    LIMIT 1
                """),
                {"org_id": org_id},
            )
            project = project_result.fetchone()

            if not project:
                project_id = "a9a2d7b4-7b02-4276-b4b7-18125decd441"
                await db.execute(
                    text(
                        """
                        INSERT INTO projects (
                            id, org_id, title, description, is_deleted,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :org_id, 'Regulation Compliance Tracking',
                            'Test project for tickets', false, :now, :now
                        )
                        """
                    ),
                    {"id": project_id, "org_id": org_id, "now": datetime.now(timezone.utc)},
                )
                print("✅ Project created: Regulation Compliance Tracking\n")
            else:
                project_id = project[0]
                print(f"✅ Using existing project: {project[1]}\n")

            print("📝 Adding user to project...")
            check = await db.execute(
                text("SELECT 1 FROM project_users WHERE user_id = :uid AND project_id = :pid"),
                {"uid": user_id, "pid": project_id},
            )
            if not check.fetchone():
                await db.execute(
                    text("""
                        INSERT INTO project_users (user_id, project_id, created_at)
                        VALUES (:user_id, :project_id, :now)
                    """),
                    {
                        "user_id": user_id,
                        "project_id": project_id,
                        "now": datetime.now(timezone.utc),
                    },
                )
            print("✅ User added to project\n")

            print("📝 Creating mock ChangeDiff for testing...")

            diff_check = await db.execute(text("SELECT diff_id FROM change_diff LIMIT 1"))
            existing_diff = diff_check.fetchone()

            if existing_diff:
                change_diff_id = existing_diff[0]
                print(f"✅ Using existing ChangeDiff: {change_diff_id}\n")
            else:
                source_check = await db.execute(text("SELECT id FROM sources LIMIT 1"))
                source = source_check.fetchone()

                if source:
                    source_id = source[0]
                    old_revision_id = "11111111-1111-1111-1111-111111111111"
                    new_revision_id = "22222222-2222-2222-2222-222222222222"

                    await db.execute(
                        text("""
                            INSERT INTO data_revisions (
                                id, source_id, content_hash, extracted_data,
                                ai_summary, was_change_detected, is_baseline,
                                scraped_at, created_at, updated_at
                            )
                            VALUES (
                                :id, :source_id, 'old_hash', '{}',
                                'Initial baseline', false, true,
                                :now, :now, :now
                            )
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": old_revision_id,
                            "source_id": source_id,
                            "now": datetime.now(timezone.utc),
                        },
                    )

                    await db.execute(
                        text("""
                            INSERT INTO data_revisions (
                                id, source_id, content_hash, extracted_data,
                                ai_summary, was_change_detected, is_baseline,
                                scraped_at, created_at, updated_at
                            )
                            VALUES (
                                :id, :source_id, 'new_hash', '{}',
                                'Updated content with changes', true, false,
                                :now, :now, :now
                            )
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": new_revision_id,
                            "source_id": source_id,
                            "now": datetime.now(timezone.utc),
                        },
                    )

                    change_diff_id = "33333333-3333-3333-3333-333333333333"
                    await db.execute(
                        text("""
                            INSERT INTO change_diff (
                                diff_id, new_revision_id, old_revision_id,
                                diff_patch, ai_confidence
                            )
                            VALUES (
                                :diff_id, :new_id, :old_id,
                                :patch, 0.95
                            )
                            ON CONFLICT (diff_id) DO NOTHING
                        """),
                        {
                            "diff_id": change_diff_id,
                            "new_id": new_revision_id,
                            "old_id": old_revision_id,
                            "patch": (
                                '{"change_summary": "GDPR Compliance Update - '
                                'Article 13 modified", "risk_level": "HIGH"}'
                            ),
                        },
                    )
                    print(f"✅ Mock ChangeDiff created: {change_diff_id}\n")
                else:
                    change_diff_id = None
                    print("⚠️  No sources found, skipping ChangeDiff creation\n")

            await db.commit()

            print("=" * 80)
            print("✅ TEST DATA SETUP COMPLETE!")
            print("=" * 80 + "\n")

            print("📋 SWAGGER TEST CREDENTIALS:")
            print("-" * 80)
            print(f"Email: {email}")
            print(f"Password: {password}\n")

            print("📋 IDS FOR SWAGGER:")
            print("-" * 80)
            print(f"organization_id: {org_id}")
            print(f"project_id: {project_id}")
            print(f"user_id: {user_id}\n")

            print("🎯 SWAGGER ENDPOINT:")
            print("-" * 80)
            print(f"POST /v1/organizations/{org_id}/projects/{project_id}/tickets\n")

            print("📝 SAMPLE REQUEST BODIES:")
            print("-" * 80)
            print("\n1️⃣  CREATE FROM SCRATCH (Manual Entry):")
            print(
                """{
  "title": "New regulatory compliance issue",
  "description": "Section 4.2 amendment requires review",
  "content": {"details": "Detailed information about the change"},
  "priority": "high",
  "project_id": "%s"
}"""
                % project_id
            )

            if change_diff_id:
                print("\n\n2️⃣  CREATE FROM DETECTED CHANGE (Auto-populate from ChangeDiff):")
                print(
                    """{
  "change_diff_id": "%s",
  "priority": "high",
  "project_id": "%s"
}

Note: Title, description, and content will be auto-populated from the ChangeDiff!
"""
                    % (change_diff_id, project_id)
                )
                print(f"\n💡 ChangeDiff ID for testing: {change_diff_id}")

            print("\n" + "=" * 80 + "\n")

        except Exception as e:
            await db.rollback()
            print(f"\n❌ Error: {e}\n")
            raise


if __name__ == "__main__":
    asyncio.run(setup_test_data())
