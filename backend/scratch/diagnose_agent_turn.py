import os
import sys
import uuid
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.database.models.user import User, UserRole
from app.voice.ivr import ivr_manager, IVRState
from app.database.models.ivr_session import IvrSession

async def diagnose():
    print("Starting agent turn diagnostics...")
    db = SessionLocal()
    call_uuid = f"diag-{uuid.uuid4().hex[:6]}"
    
    try:
        # Create a test session in ACTIVE_AGENT state
        session = ivr_manager.get_or_create_call(call_uuid, "+918266894170", db)
        session.state = IVRState.ACTIVE_AGENT
        session.user_id = str(uuid.uuid4()) # Mock user
        session._save_to_db()
        print(f"Created active agent call session: {call_uuid}")

        # Now trigger process_text_agent_turn with a simple query
        query = "hello, can you help me?"
        print(f"Processing query: '{query}'...")
        res = await session.process_text_agent_turn(query)
        print("Success! Response dict:")
        print(res)
        
    except Exception as e:
        print("\n[CRITICAL ERROR] Diagnostic test failed:")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        db.query(IvrSession).filter_by(call_id=call_uuid).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(diagnose())
