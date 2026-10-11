-- Deterministic Lock Acquisition Pattern
-- Always lock rows in identical canonical order (e.g. ORDER BY id ASC)

BEGIN;
SET LOCAL lock_timeout = '3s';

-- Step 1: Acquire row-level locks deterministically
SELECT id, stock_count 
FROM products 
WHERE id IN (42, 84) 
ORDER BY id ASC 
FOR UPDATE;

-- Step 2: Perform atomic inventory decrement
UPDATE products 
SET stock_count = stock_count - 1 
WHERE id = 42;

UPDATE products 
SET stock_count = stock_count - 2 
WHERE id = 84;

-- Step 3: Insert reservations
INSERT INTO inventory_reservations (product_id, quantity, status)
VALUES 
    (42, 1, 'CONFIRMED'),
    (84, 2, 'CONFIRMED');

COMMIT;
