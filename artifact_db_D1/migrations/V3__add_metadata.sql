-- V3: Alter orders table to add metadata JSONB column
-- Author: Eric (Ashfaq Lead Software Engineering Specialist)
-- Modifed post-deployment by developer without migration discipline:
-- Added documentation comment directly to migration script.

ALTER TABLE orders
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN orders.metadata IS 'Dynamic order metadata payload in JSONB';
