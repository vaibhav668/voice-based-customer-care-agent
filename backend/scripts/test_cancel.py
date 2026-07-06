from app.database.session import SessionLocal
from app.ai.tools.booking import BookingTool

db = SessionLocal()

tool = BookingTool(db)

print(
    tool.cancel(
        "BK-100001"
    )
)

db.close()