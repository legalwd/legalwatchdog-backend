-- Trigger function to update the search_vector column on insert or update
CREATE OR REPLACE FUNCTION update_data_revisions_search_vector
()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector
('english', 
        coalesce
(NEW.minio_object_key, '') || ' ' || 
        coalesce
(NEW.ai_summary, '')
    );
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function on insert or update
DROP TRIGGER IF EXISTS trg_update_data_revisions_search_vector
ON data_revisions;
CREATE TRIGGER trg_update_data_revisions_search_vector
    BEFORE
INSERT OR
UPDATE ON data_revisions
    FOR EACH ROW
EXECUTE FUNCTION update_data_revisions_search_vector
();
