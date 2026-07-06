from app.conversation.session import ConversationSession


class MemoryStore:

    def __init__(self):
        self.sessions = {}

    def get(self, session_id):

        if session_id not in self.sessions:

            self.sessions[session_id] = ConversationSession(
                session_id=session_id
            )

        return self.sessions[session_id]


memory = MemoryStore()