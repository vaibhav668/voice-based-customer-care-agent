import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import engine, SessionLocal
from sqlalchemy import text

def run_migrations():
    print("Checking database columns for Conversations...")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    try:
        if "conversations" in inspector.get_table_names():
            existing_columns = [col["name"] for col in inspector.get_columns("conversations")]
            print("Existing columns:", existing_columns)

            # Columns to add
            cols_to_add = [
                ("booking_id", "VARCHAR(36)"),
                ("campaign_id", "VARCHAR(36)"),
                ("resolution_status", "VARCHAR(50) DEFAULT 'unresolved'"),
                ("recording_url", "VARCHAR(255)"),
            ]

            with engine.begin() as conn:
                for col_name, col_type in cols_to_add:
                    if col_name not in existing_columns:
                        print(f"Adding column {col_name} to conversations table...")
                        # SQLite doesn't support complex constraints or syntax in ADD COLUMN, keeping it simple
                        conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {col_name} {col_type}"))
                        print(f"Column {col_name} added successfully!")
                    else:
                        print(f"Column {col_name} already exists.")
            
            print("Database migration checks complete.")
    except Exception as e:
        print("Migration warning/error:", e)

if __name__ == "__main__":
    run_migrations()
