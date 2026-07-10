import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import engine, SessionLocal
from sqlalchemy import text

def run_migrations():
    print("Checking database columns for Conversations...")
    with engine.begin() as conn:
        # Check existing columns on conversations table
        # We can run PRAGMA table_info(conversations) for SQLite
        try:
            res = conn.execute(text("PRAGMA table_info(conversations)")).fetchall()
            existing_columns = [row[1] for row in res]
            print("Existing columns:", existing_columns)

            # Columns to add
            cols_to_add = [
                ("booking_id", "VARCHAR(36) REFERENCES bookings(id)"),
                ("campaign_id", "VARCHAR(36) REFERENCES campaigns(id)"),
                ("resolution_status", "VARCHAR(50) DEFAULT 'unresolved' NOT NULL"),
                ("recording_url", "VARCHAR(255)"),
            ]

            for col_name, col_type in cols_to_add:
                if col_name not in existing_columns:
                    print(f"Adding column {col_name} to conversations table...")
                    conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {col_name} {col_type}"))
                    print(f"Column {col_name} added successfully!")
                else:
                    print(f"Column {col_name} already exists.")
            
            print("Database migration checks complete.")
        except Exception as e:
            print("Migration warning/error:", e)

if __name__ == "__main__":
    run_migrations()
