from app.database.session import SessionLocal
from app.ai.tools.delay import DelayTool

db = SessionLocal()

tool = DelayTool(db)

print(
    tool.execute("BK-100001")
)

db.close()