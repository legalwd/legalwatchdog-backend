INSERT INTO organizations
    (id, name, is_active, settings, billing_info, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'Test Organization', true, '{}', '{}', NOW(), NOW());


INSERT INTO projects
    (id, org_id, title, description, is_deleted, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Legal Watch Dog Test Project', 'Testing project for search endpoint', false, NOW(), NOW());


INSERT INTO jurisdictions
    (id, project_id, name, description, scrape_output, created_at, is_deleted)
VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Federal Law', 'US Federal Laws and Regulations', 'null', NOW(), false);


INSERT INTO sources
    (id, jurisdiction_id, name, url, source_type, scrape_frequency, is_active, is_deleted, scraping_rules, created_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Federal Register', 'https://www.federalregister.gov', 'WEB', 'DAILY', true, false, '{}', NOW());


INSERT INTO data_revision
    (id, source_id, minio_object_key, extracted_data, ai_summary, scraped_at, was_change_detected)
VALUES
    ('d7972844-5562-41b8-a5dd-1cf4093df6dc', '00000000-0000-0000-0000-000000000001', 'federal_tax_regulations_2025.pdf', '{"document_type": "regulatory", "topic": "taxation"}', 'This document discusses federal tax regulations, corporate compliance requirements, and new filing procedures for businesses operating across state lines.', NOW(), true),
    ('462f852c-a784-4040-9436-bd929dd3b904', '00000000-0000-0000-0000-000000000001', 'environmental_protection_laws.pdf', '{"document_type": "environmental", "topic": "climate"}', 'Environmental protection laws and climate change policies for corporations. Includes carbon emission standards, renewable energy requirements, and sustainability reporting mandates.', NOW(), true),
    ('32be4376-38f9-43df-af14-1207fb7cd7c1', '00000000-0000-0000-0000-000000000001', 'labor_law_updates.pdf', '{"document_type": "labor", "topic": "employment"}', 'Labor laws regarding employee rights, workplace safety regulations, minimum wage updates, and overtime compensation requirements for various industries.', NOW(), true),
    ('a9ea3222-d0e9-431f-b36b-483f9762dce5', '00000000-0000-0000-0000-000000000001', 'data_privacy_regulations.pdf', '{"document_type": "privacy", "topic": "data_protection"}', 'Data privacy regulations covering consumer information protection, GDPR compliance, cybersecurity requirements, and breach notification procedures.', NOW(), true),
    ('07045366-5064-4ea6-86a8-dadb1b2f5250', '00000000-0000-0000-0000-000000000001', 'healthcare_compliance.pdf', '{"document_type": "healthcare", "topic": "compliance"}', 'Healthcare industry compliance regulations including HIPAA requirements, patient data security, insurance provider obligations, and medical records management.', NOW(), true);


SELECT ' Created 1 test organization' as status;
SELECT ' Created 1 test project' as status;
SELECT ' Created 1 test jurisdiction' as status;
SELECT ' Created 1 test source' as status;
SELECT ' Created ' || COUNT(*) || ' test data revisions' as status
FROM data_revision;


SELECT id, minio_object_key, search_vector
IS NOT NULL as has_search_vector FROM data_revision ORDER BY minio_object_key;
