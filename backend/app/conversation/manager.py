from app.conversation.memory import memory


class ConversationManager:

    def get_session(self, session_id):

        return memory.get(session_id)

    def add_user_message(
        self,
        session,
        message,
    ):

        session.add_message(
            "user",
            message,
        )

    def add_ai_message(
        self,
        session,
        message,
    ):

        session.add_message(
            "assistant",
            message,
        )