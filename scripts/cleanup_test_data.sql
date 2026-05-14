-- Cleanup script for ticket invitation test data
-- Run this with: psql -d your_database_name -f cleanup_test_data.sql

BEGIN;

-- Delete external participants for test tickets
DELETE FROM external_participants
WHERE ticket_id IN (
    SELECT id FROM tickets
    WHERE title = 'Legal Review Required for Contract Amendment'
    AND organization_id IN (
        SELECT id FROM organizations WHERE name = 'Test Legal Firm'
    )
);

-- Delete tickets
DELETE FROM tickets
WHERE title = 'Legal Review Required for Contract Amendment'
AND organization_id IN (
    SELECT id FROM organizations WHERE name = 'Test Legal Firm'
);

-- Delete projects
DELETE FROM projects
WHERE title = 'Contract Management System'
AND org_id IN (
    SELECT id FROM organizations WHERE name = 'Test Legal Firm'
);

-- Delete user organization memberships
DELETE FROM user_organizations
WHERE user_id IN (
    SELECT id FROM users WHERE email IN (
        'admin@testlegalfirm.com',
        'emaduilzjr1@gmail.com'
    )
);

-- Delete users
DELETE FROM users
WHERE email IN (
    'admin@testlegalfirm.com',
    'emaduilzjr1@gmail.com'
);

-- Delete organization
DELETE FROM organizations
WHERE name = 'Test Legal Firm';

COMMIT;

-- Verify cleanup
SELECT 'Cleanup complete! Remaining test data:' as status;
SELECT COUNT(*) as test_orgs FROM organizations WHERE name = 'Test Legal Firm';
SELECT COUNT(*) as test_users FROM users WHERE email LIKE '%testlegalfirm.com';
SELECT COUNT(*) as test_projects FROM projects WHERE title = 'Contract Management System';
