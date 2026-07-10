import time
import uuid

from sqlalchemy.orm import Session
from app.ai.intent.schemas import Intent
from app.ai.agent.agent import SupportAgent
from app.ai.context.resolver import ContextResolver
from app.ai.response.generator import ResponseGenerator
from app.ai.understanding.node import understand
from app.conversation.manager import ConversationManager
from app.database.session import SessionLocal
from app.schemas.chat import ChatRequest
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.conversation_message_repository import ConversationMessageRepository


class ChatService:

    def __init__(self, db: Session | None = None):
        self.db: Session = db or SessionLocal()

        self.agent = SupportAgent(self.db)
        self.context = ContextResolver()
        self.generator = ResponseGenerator()
        self.manager = ConversationManager()
        self.conv_repo = ConversationRepository(self.db)
        self.msg_repo = ConversationMessageRepository(self.db)

    def process(
        self,
        request: ChatRequest,
        user_id=None,
        channel: str = "CHAT",
        audio_input_path: str | None = None,
    ):
        start_time = time.time()
        session_id = request.session_id or str(uuid.uuid4())

        session = self.manager.get_session(session_id)
        if hasattr(request, "language") and request.language:
            session.language = request.language.lower()

        language = getattr(session, "language", "en")

        # ----------------------------------------
        # Permanent Database Conversation Session
        # ----------------------------------------
        db_conv = self.conv_repo.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            language=language,
        )

        # Record User Message in Database
        self.msg_repo.add_message(
            conversation_id=db_conv.id,
            sender="USER",
            message_type=channel,
            message=request.message,
            audio_path=audio_input_path,
        )

        self.manager.add_user_message(
            session,
            request.message,
        )

        print("=" * 60)
        print("SESSION MEMORY")
        try:
            print(str(session.entities).encode('ascii', 'replace').decode('ascii'), "Language:", language)
        except Exception:
            pass
        print("=" * 60)

        # ----------------------------------------
        # Understand current message
        # ----------------------------------------

        understanding = understand(request.message)

        # ----------------------------------------
        # Save Extracted Entities to Session
        # ----------------------------------------
        if understanding.booking_code:
            session.entities["booking_code"] = understanding.booking_code
        if understanding.passenger_name:
            session.entities["passenger_name"] = understanding.passenger_name
        if understanding.complaint:
            session.entities["complaint"] = understanding.complaint
        if understanding.bus_number:
            session.entities["bus_number"] = understanding.bus_number
        if understanding.source_city:
            session.entities["source_city"] = understanding.source_city
        if understanding.destination_city:
            session.entities["destination_city"] = understanding.destination_city
        if understanding.travel_date:
            session.entities["travel_date"] = understanding.travel_date
        if understanding.seat_number:
            session.entities["seat_number"] = understanding.seat_number
        if understanding.phone_number:
            session.entities["phone_number"] = understanding.phone_number

        # ----------------------------------------
        # Context Follow-up
        # ----------------------------------------

        context_response = self.context.resolve(
            request.message,
            session,
            intent=understanding.intent,
        )

        print("=" * 60)
        print("CONTEXT RESPONSE:", context_response)
        print("=" * 60)

        if context_response is not None:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            ai_msg = self.msg_repo.add_message(
                conversation_id=db_conv.id,
                sender="AI",
                message_type=channel,
                message=context_response,
                intent="CONTEXT_FOLLOWUP",
                response_time_ms=elapsed_ms,
            )
            self.conv_repo.update_state(
                db_conv.id,
                current_intent="CONTEXT_FOLLOWUP",
                language=language,
            )

            self.manager.add_ai_message(
                session,
                context_response,
            )

            return {
                "session_id": session_id,
                "response": context_response,
                "db_message_id": str(ai_msg.id),
                "db_conversation_id": str(db_conv.id),
            }

        # ----------------------------------------
        # Friendly General Chat
        # ----------------------------------------

        if understanding.intent == Intent.GENERAL:
            response = self.generator.general_chat(
                request.message,
                language=language,
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            ai_msg = self.msg_repo.add_message(
                conversation_id=db_conv.id,
                sender="AI",
                message_type=channel,
                message=response,
                intent=Intent.GENERAL.value,
                confidence=understanding.confidence,
                response_time_ms=elapsed_ms,
            )
            self.conv_repo.update_state(
                db_conv.id,
                current_intent=Intent.GENERAL.value,
                language=language,
            )

            self.manager.add_ai_message(
                session,
                response,
            )

            return {
                "session_id": session_id,
                "response": response,
                "db_message_id": str(ai_msg.id),
                "db_conversation_id": str(db_conv.id),
            }

        # ----------------------------------------
        # Continue Previous Intent
        # ----------------------------------------

        if session.current_intent:
            if understanding.intent in (Intent.PROVIDE_BOOKING_CODE, Intent.FOLLOW_UP) or not understanding.intent or (understanding.intent == Intent.GENERAL and understanding.booking_code):
                understanding.intent = session.current_intent
            else:
                session.current_intent = understanding.intent

        print("=" * 60)
        print("UNDERSTANDING")
        print("Intent:", understanding.intent)
        print("Booking:", understanding.booking_code)
        print("Passenger:", understanding.passenger_name)
        print("Complaint:", understanding.complaint)
        print("Bus:", understanding.bus_number)
        print("=" * 60)

        # ----------------------------------------
        # Save Extracted Entities
        # ----------------------------------------

        if understanding.booking_code:
            session.entities["booking_code"] = understanding.booking_code

        if understanding.passenger_name:
            session.entities["passenger_name"] = understanding.passenger_name

        if understanding.complaint:
            session.entities["complaint"] = understanding.complaint

        if understanding.bus_number:
            session.entities["bus_number"] = understanding.bus_number

        if understanding.source_city:
            session.entities["source_city"] = understanding.source_city

        if understanding.destination_city:
            session.entities["destination_city"] = understanding.destination_city

        if understanding.travel_date:
            session.entities["travel_date"] = understanding.travel_date

        if understanding.seat_number:
            session.entities["seat_number"] = understanding.seat_number

        if understanding.phone_number:
            session.entities["phone_number"] = understanding.phone_number

        source_city = understanding.source_city or session.entities.get("source_city")
        destination_city = understanding.destination_city or session.entities.get("destination_city")
        travel_date = understanding.travel_date or session.entities.get("travel_date")
        seat_number = understanding.seat_number or session.entities.get("seat_number")

        booking_code = (
            understanding.booking_code
            or session.entities.get("booking_code")
        )

        passenger_name = (
            understanding.passenger_name
            or session.entities.get("passenger_name")
        )

        complaint = (
            understanding.complaint
            or session.entities.get("complaint")
        )

        bus_number = (
            understanding.bus_number
            or session.entities.get("bus_number")
        )
        
        confirmation = understanding.confirmation

        # ----------------------------------------
        # Execute Agent
        # ----------------------------------------

        session_phone = understanding.phone_number or session.entities.get("phone_number")

        result = self.agent.execute(
            intent=understanding.intent,
            booking_code=booking_code,
            question=request.message,
            source_city=source_city,
            destination_city=destination_city,
            travel_date=travel_date,
            seat_number=seat_number,
            confirmation=confirmation,
            user_id=user_id,
            session_id=session_id,
            language=understanding.language or language,
            session_phone=session_phone,
        )

        print("=" * 60)
        print("TOOL:", result.tool)
        try:
            print("DATA:", str(result.data).encode('ascii', 'replace').decode('ascii'))
        except Exception:
            pass
        print("=" * 60)

        session.entities["last_tool"] = result.tool
        session.entities["last_result"] = result.data

        # ----------------------------------------
        # Waiting for Booking Code
        # ----------------------------------------

        if result.requires_booking_code:
            session.current_intent = understanding.intent
            localized_booking_msg = self.generator.request_booking_code(language=language)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            ai_msg = self.msg_repo.add_message(
                conversation_id=db_conv.id,
                sender="AI",
                message_type=channel,
                message=localized_booking_msg,
                intent=str(understanding.intent),
                confidence=understanding.confidence,
                entities=session.entities,
                tool_used=result.tool,
                response_time_ms=elapsed_ms,
                booking_code=booking_code,
            )
            self.conv_repo.update_state(
                db_conv.id,
                current_intent=str(understanding.intent),
                last_tool=result.tool,
                language=language,
            )

            return {
                "session_id": session_id,
                "response": localized_booking_msg,
                "db_message_id": str(ai_msg.id),
                "db_conversation_id": str(db_conv.id),
            }

        # ----------------------------------------
        # Conversation Finished / Processed
        # ----------------------------------------

        session.current_intent = None

        if booking_code:
            session.entities["booking_code"] = booking_code

        if passenger_name:
            session.entities["passenger_name"] = passenger_name

        if complaint:
            session.entities["complaint"] = complaint

        if bus_number:
            session.entities["bus_number"] = bus_number

        if result.data:
            session.entities["last_data"] = result.data

        # ----------------------------------------
        # Generate Final Response
        # ----------------------------------------

        response = self.generator.generate(
            result.tool,
            result.data,
            user_message=request.message,
            language=language,
        )

        print("=" * 60)
        print("FINAL RESPONSE")
        try:
            print(response.encode('ascii', 'replace').decode('ascii'))
        except Exception:
            pass
        print("=" * 60)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        ai_msg = self.msg_repo.add_message(
            conversation_id=db_conv.id,
            sender="AI",
            message_type=channel,
            message=response,
            intent=str(understanding.intent),
            confidence=understanding.confidence,
            entities=session.entities,
            tool_used=result.tool,
            response_time_ms=elapsed_ms,
            booking_code=booking_code,
        )

        if result.success and isinstance(result.data, dict) and "language" in result.data:
            language = result.data["language"]
            session.language = language

        self.conv_repo.update_state(
            db_conv.id,
            current_intent=str(understanding.intent),
            last_tool=result.tool,
            language=language,
        )

        self.manager.add_ai_message(
            session,
            response,
        )

        session.last_tool = result.tool
        session.last_result = result.data
        session.last_response = response

        session.entities["last_response"] = response

        # ----------------------------------------
        # DB Association and Resolution Status Sync
        # ----------------------------------------
        if db_conv:
            if booking_code:
                try:
                    from app.repositories.booking_repository import BookingRepository
                    booking_repo = BookingRepository(self.db)
                    booking = booking_repo.get_by_booking_code(booking_code)
                    if booking:
                        db_conv.booking_id = booking.id
                except Exception as e:
                    print("Booking linking notice:", e)

            # Resolution status logic
            if result.tool == "escalate":
                db_conv.resolution_status = "escalated"
            elif result.success and result.tool in ("booking", "cancellation", "reschedule", "complaint", "refund"):
                db_conv.resolution_status = "resolved"

            self.db.commit()

        return {
            "session_id": session_id,
            "response": response,
            "db_message_id": str(ai_msg.id),
            "db_conversation_id": str(db_conv.id),
        }