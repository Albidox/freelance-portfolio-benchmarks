import psycopg2
import psycopg2.errors
import threading
import time
import os

DB_KWARGS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': '',
    'host': '127.0.0.1',
    'port': 5433
}

def create_output_dir():
    os.makedirs('output', exist_ok=True)

def worker_before(worker_id, first_product, second_product, results_out):
    try:
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = False
        cur = conn.cursor()
        
        start_time = time.perf_counter()
        
        # Set lock timeout for safety as instructed
        cur.execute("SET statement_timeout = '10s'; SET lock_timeout = '5s';")
        
        # Update first product
        cur.execute("UPDATE products SET stock_count = stock_count - 1 WHERE id = %s", (first_product,))
        time.sleep(0.2)
        
        # Update second product
        cur.execute("UPDATE products SET stock_count = stock_count - 1 WHERE id = %s", (second_product,))
        
        # Insert reservations
        cur.execute("INSERT INTO inventory_reservations (product_id, quantity, status) VALUES (%s, 1, 'CONFIRMED')", (first_product,))
        cur.execute("INSERT INTO inventory_reservations (product_id, quantity, status) VALUES (%s, 1, 'CONFIRMED')", (second_product,))
        
        conn.commit()
        
        elapsed = (time.perf_counter() - start_time) * 1000
        results_out.append({"worker": worker_id, "status": "success", "elapsed": elapsed, "error": None})
    except psycopg2.errors.DeadlockDetected as e:
        elapsed = (time.perf_counter() - start_time) * 1000
        results_out.append({"worker": worker_id, "status": "deadlock", "elapsed": elapsed, "error": str(e).strip()})
    except Exception as e:
        elapsed = (time.perf_counter() - start_time) * 1000
        results_out.append({"worker": worker_id, "status": "error", "elapsed": elapsed, "error": str(e).strip()})
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def run_before():
    create_output_dir()
    print("Running before deadlock reproduction...")
    results_out = []
    
    t1 = threading.Thread(target=worker_before, args=(1, 42, 84, results_out))
    t2 = threading.Thread(target=worker_before, args=(2, 84, 42, results_out))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    out_text = "Deadlock Reproduction Results:\n\n"
    for res in results_out:
        out_text += f"Worker {res['worker']}: {res['status'].upper()} in {res['elapsed']:.2f} ms\n"
        if res['error']:
            out_text += f"Error: {res['error']}\n"
        out_text += "\n"
        
    with open('output/deadlock_before.txt', 'w') as f:
        f.write(out_text)
    
    print(out_text)

if __name__ == '__main__':
    run_before()
