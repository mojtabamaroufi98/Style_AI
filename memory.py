from collections import defaultdict
from typing import Dict, List


class ShortTermMemory:

    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages

        self.sessions: Dict[str, List[dict]] = defaultdict(list)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        self.sessions[session_id].append(
            {
                "role": role,
                "content": content
            }
        )

        # فقط آخرین پیام‌ها را نگه می‌داریم
        self.sessions[session_id] = (
            self.sessions[session_id][-self.max_messages:]
        )

    def get_messages(
        self,
        session_id: str
    ) -> List[dict]:

        return self.sessions.get(
            session_id,
            []
        )

    def clear(
        self,
        session_id: str
    ):
        self.sessions.pop(
            session_id,
            None
        )


memory = ShortTermMemory(
    max_messages=10
)