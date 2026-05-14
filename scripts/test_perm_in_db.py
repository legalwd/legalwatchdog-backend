import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.role_template_service import RoleTemplateCRUD

# Your database URL
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:1000/db_name"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_template_loading():
    """Test 1: Verify templates exist in database"""
    print("\n" + "=" * 60)
    print("TEST 1: Verify Role Templates in Database")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        templates = await RoleTemplateCRUD.get_all_templates(db)

        print(f"\nFound {len(templates)} templates:")
        for template in templates:
            print(f"\n {template.name.upper()}")
            print(f"     Display Name: {template.display_name}")
            print(f"     Hierarchy Level: {template.hierarchy_level}")
            print(f"     System Role: {template.is_system}")
            print(f"     Permissions: {len(template.permissions)} permissions")

        assert len(templates) == 4, "Should have 4 templates"
        print("\n✅ All templates found!")


async def test_role_creation():
    """Test 2: Create roles from templates"""
    print("\n" + "=" * 60)
    print("TEST 2: Create Roles from Templates")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        timestamp = datetime.now(timezone.utc)
        org_name = f"Test Organization {timestamp}"
        print("\n0. Creating test organization...")
        org = Organization(name=org_name, industry="Technology")
        db.add(org)
        await db.flush()  # Get the org ID
        await db.refresh(org)

        print(f"   ✅ Organization created: {org.id}")
        print(f"      Name: {org.name}")

        # Now create roles for this REAL organization
        print("\n1. Creating Owner role...")
        owner_role = await RoleCRUD.create_owner_role(
            db=db,
            organization_id=org.id,  # Use real org ID
            role_name="Owner",
        )
        print(f"   ✅ Created: {owner_role.name}")
        print(f"      - ID: {owner_role.id}")
        print(f"      - Hierarchy: {owner_role.hierarchy_level}")
        print(f"      - Template: {owner_role.template_name}")
        print(
            f"      - Has delete_organization: {owner_role.permissions.get('delete_organization')}"
        )

        # Create Admin role
        print("\n2. Creating Admin role...")
        admin_role = await RoleCRUD.create_admin_role(
            db=db, organization_id=org.id, role_name="Admin"
        )
        print(f"   ✅ Created: {admin_role.name}")
        print(f"      - Hierarchy: {admin_role.hierarchy_level}")
        print(
            f"      - Has manage_organization: {admin_role.permissions.get('manage_organization')}"
        )
        print(
            f"      - Has delete_organization: {admin_role.permissions.get('delete_organization')}"
        )

        # Create Manager role
        print("\n3. Creating Manager role...")
        manager_role = await RoleCRUD.create_manager_role(
            db=db, organization_id=org.id, role_name="Manager"
        )
        print(f"   ✅ Created: {manager_role.name}")
        print(f"      - Hierarchy: {manager_role.hierarchy_level}")

        # Create Member role
        print("\n4. Creating Member role...")
        member_role = await RoleCRUD.get_default_user_role(
            db=db, organization_id=org.id, role_name="Member"
        )
        print(f"   ✅ Created: {member_role.name}")
        print(f"      - Hierarchy: {member_role.hierarchy_level}")

        # Commit everything
        await db.commit()

        # Verify hierarchy
        print("\n" + "-" * 60)
        print("Hierarchy Verification:")
        print(
            f"  Owner (4)   > Admin (3)   = {
                owner_role.hierarchy_level > admin_role.hierarchy_level
            }"
        )
        print(
            f"  Admin (3)   > Manager (2) = {
                admin_role.hierarchy_level > manager_role.hierarchy_level
            }"
        )
        print(
            f"  Manager (2) > Member (1)  = {
                manager_role.hierarchy_level > member_role.hierarchy_level
            }"
        )

        print("\n✅ All roles created successfully!")


async def test_permission_verification():
    """Test 3: Verify specific permissions"""
    print("\n" + "=" * 60)
    print("TEST 3: Verify Role Permissions")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Create organization first
        unique_id = str(uuid.uuid4())[:8]  # First 8 chars of UUID
        org_name = f"Test Permissions Org {unique_id}"
        org = Organization(name=org_name, industry="Tech")
        db.add(org)
        await db.flush()
        await db.refresh(org)

        owner_role = await RoleCRUD.create_owner_role(db, org.id)
        admin_role = await RoleCRUD.create_admin_role(db, org.id)
        manager_role = await RoleCRUD.create_manager_role(db, org.id)
        member_role = await RoleCRUD.get_default_user_role(db, org.id)

        await db.commit()

        # Test specific permissions
        tests = [
            ("Owner", owner_role, "delete_organization", True),
            ("Admin", admin_role, "delete_organization", None),
            ("Admin", admin_role, "manage_organization", True),
            ("Manager", manager_role, "create_projects", True),
            ("Manager", manager_role, "delete_organization", None),
            ("Member", member_role, "view_projects", True),
            ("Member", member_role, "delete_projects", None),
        ]

        for role_name, role, permission, expected in tests:
            actual = role.permissions.get(permission)
            status = "✅" if actual == expected else "❌"
            print(f"{status} {role_name:8} - {permission:25} = {actual} (expected: {expected})")

        print("\n✅ Permission verification complete!")


async def test_hierarchy_validation():
    """Test 4: Test role hierarchy rules"""
    print("\n" + "=" * 60)
    print("TEST 4: Test Role Hierarchy Rules")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Create organization
        unique_id = str(uuid.uuid4())[:8]  # First 8 chars of UUID
        org_name = f"Test Permissions Org {unique_id}"
        org = Organization(name=org_name, industry="Tech")
        db.add(org)
        await db.flush()
        await db.refresh(org)

        owner = await RoleCRUD.create_owner_role(db, org.id)
        admin = await RoleCRUD.create_admin_role(db, org.id)
        manager = await RoleCRUD.create_manager_role(db, org.id)
        member = await RoleCRUD.get_default_user_role(db, org.id)

        await db.commit()

        from app.api.utils.role_hierarchy import RoleHierarchy

        tests = [
            ("Owner can manage Admin", owner.hierarchy_level, admin.hierarchy_level, True),
            ("Admin can manage Manager", admin.hierarchy_level, manager.hierarchy_level, True),
            ("Manager can manage Member", manager.hierarchy_level, member.hierarchy_level, True),
            ("Admin CANNOT manage Owner", admin.hierarchy_level, owner.hierarchy_level, False),
            ("Manager CANNOT manage Admin", manager.hierarchy_level, admin.hierarchy_level, False),
            (
                "Member CANNOT manage Manager",
                member.hierarchy_level,
                manager.hierarchy_level,
                False,
            ),
        ]

        for description, user_level, target_level, expected in tests:
            result = RoleHierarchy.can_manage_role(user_level, target_level)
            status = "✅" if result == expected else "❌"
            print(f"{status} {description:40} = {result} (expected: {expected})")

        print("\n✅ Hierarchy validation complete!")


async def cleanup_test_data():
    """Clean up test organizations and roles"""
    print("\n" + "=" * 60)
    print("CLEANUP: Removing Test Data")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete

        # Delete test organizations (roles will cascade delete)
        await db.execute(delete(Organization).where(Organization.name.like("Test%")))
        await db.commit()
        print("✅ Cleanup complete!")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 STARTING ROLE SYSTEM TESTS")
    print("=" * 60)

    try:
        await test_template_loading()
        await test_role_creation()
        await test_permission_verification()
        await test_hierarchy_validation()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

        # Optional: Clean up test data
        response = input("\nClean up test data? (y/n): ")
        if response.lower() == "y":
            await cleanup_test_data()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
