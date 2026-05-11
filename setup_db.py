import os
import psycopg2
from dotenv import load_dotenv

# Load .env locally if present
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def setup_database():
    if not DATABASE_URL:
        print("DATABASE_URL is not set!")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Create Portfolio Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id SERIAL PRIMARY KEY,
            total_capital NUMERIC(15, 2) NOT NULL,
            available_capital NUMERIC(15, 2) NOT NULL
        );
    """)

    # 2. Create Active Positions Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(50) NOT NULL,
            strategy VARCHAR(100),
            entry_date DATE,
            entry_price NUMERIC(10, 2),
            quantity INTEGER,
            sl_price NUMERIC(10, 2),
            target_price NUMERIC(10, 2),
            bars_held INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'active'
        );
    """)

    # 3. Create Trade History Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(50),
            strategy VARCHAR(100),
            entry_date DATE,
            exit_date DATE,
            entry_price NUMERIC(10, 2),
            exit_price NUMERIC(10, 2),
            quantity INTEGER,
            profit_loss NUMERIC(10, 2),
            return_pct NUMERIC(10, 2),
            reason VARCHAR(100)
        );
    """)

    # 4. Initialize Portfolio with 2,00,000 INR (Only if table is empty)
    cur.execute("SELECT COUNT(*) FROM portfolio;")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("""
            INSERT INTO portfolio (total_capital, available_capital) 
            VALUES (200000.00, 200000.00);
        """)
        print("Initialized portfolio with ₹2,00,000.00.")

    conn.commit()
    cur.close()
    conn.close()
    print("Database setup complete!")

if __name__ == "__main__":
    setup_database()
