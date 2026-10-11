import psycopg2
import time
import threading
import subprocess

DB_KWARGS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': '',
    'host': '127.0.0.1',
    'port': 5433
}

def blocker():
    try:
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = False
        cur = conn.cursor()
        # Ensure the row exists
        cur.execute("INSERT INTO products (id, name, stock_count, price_cents) VALUES (42, 'Test Product', 100, 1000) ON CONFLICT DO NOTHING")
        conn.commit()
        
        cur.execute("UPDATE products SET stock_count = stock_count - 1 WHERE id = 42")
        # Hold the lock
        time.sleep(10)
        conn.commit()
    except Exception as e:
        print(f"Blocker error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def blocked():
    try:
        # Give blocker time to acquire lock
        time.sleep(2)
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET lock_timeout = '8s';")
        cur.execute("UPDATE products SET stock_count = stock_count - 1 WHERE id = 42")
        conn.commit()
    except Exception as e:
        print(f"Blocked error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    t1 = threading.Thread(target=blocker)
    t2 = threading.Thread(target=blocked)
    
    t1.start()
    t2.start()
    
    # Wait for the lock to be established
    time.sleep(4)
    
    # Run the diagnostics suite
    print("Running diagnostics suite...")
    subprocess.run([
        'psql', '-U', 'postgres', '-h', '127.0.0.1', '-p', '5433', '-d', 'postgres', 
        '-f', 'lock_diagnostics_suite.sql'
    ], stdout=open('output/lock_diagnostics_sample.txt', 'w'))
    print("Diagnostics complete.")
    
    t1.join()
    t2.join()
