import psycopg2
import psycopg2.errors
import threading
import time
import os
import sys
from statistics import mean

DB_KWARGS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': '',
    'host': '127.0.0.1',
    'port': 5433
}

def create_output_dir():
    os.makedirs('output', exist_ok=True)

def worker_after(worker_id, loop_count, timings_out, errors_out):
    try:
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = False
        cur = conn.cursor()
        
        for _ in range(loop_count):
            start_time = time.perf_counter()
            
            # Start transaction
            cur.execute("SET LOCAL lock_timeout = '3s';")
            
            # Deterministic locking: order by id asc
            # Suppose we want to update products 42 and 84
            cur.execute("SELECT id, stock_count FROM products WHERE id IN (42, 84) ORDER BY id ASC FOR UPDATE")
            
            # Update products
            cur.execute("UPDATE products SET stock_count = stock_count - 1 WHERE id = 42")
            cur.execute("UPDATE products SET stock_count = stock_count - 2 WHERE id = 84")
            
            # Insert reservations
            cur.execute("INSERT INTO inventory_reservations (product_id, quantity, status) VALUES (42, 1, 'CONFIRMED'), (84, 2, 'CONFIRMED')")
            
            conn.commit()
            
            elapsed = (time.perf_counter() - start_time) * 1000
            timings_out.append(elapsed)
            
    except Exception as e:
        conn.rollback()
        errors_out.append(str(e))
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def run_remediation_test():
    create_output_dir()
    print("Running after deadlock remediation (500 concurrent transactions)...")
    
    num_threads = 10
    loops_per_thread = 50
    
    timings = []
    errors = []
    threads = []
    
    for i in range(num_threads):
        t = threading.Thread(target=worker_after, args=(i, loops_per_thread, timings, errors))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
        
    total_tx = len(timings)
    total_errs = len(errors)
    
    if timings:
        timings.sort()
        min_time = min(timings)
        max_time = max(timings)
        mean_time = mean(timings)
        p95_time = timings[int(len(timings) * 0.95)]
    else:
        min_time = max_time = mean_time = p95_time = 0.0

    out_text = f"{total_tx} concurrent transaction loops executed\n"
    out_text += f"{total_errs} Deadlocks detected ({100.0 if total_errs == 0 else (total_tx / (total_tx + total_errs) * 100):.1f}% success rate)\n"
    out_text += f"Execution Latencies (ms):\n"
    out_text += f"  Min: {min_time:.2f} ms\n"
    out_text += f"  Max: {max_time:.2f} ms\n"
    out_text += f"  Mean: {mean_time:.2f} ms\n"
    out_text += f"  p95: {p95_time:.2f} ms\n"
    
    with open('output/deadlock_after.txt', 'w') as f:
        f.write(out_text)
        
    print(out_text)
    if errors:
        print("Errors encountered:", errors)

if __name__ == '__main__':
    run_remediation_test()
