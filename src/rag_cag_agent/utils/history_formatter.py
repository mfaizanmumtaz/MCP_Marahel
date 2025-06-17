class HistoryFormatter:
    def format_history_for_standalone_query(self, chat_history) -> str:
        result = "\n".join(
            [f"User: {chat.query}\nAI: {chat.response}" for chat in chat_history]
        )
        return result

    def general_history_formatter(self, chat_history) -> list[tuple[str, str]]:
        formatted_history: list[tuple[str, str]] = []
        for chat in chat_history:
            if chat.query:
                formatted_history.append(("user", chat.query))
            if chat.response:
                formatted_history.append(("ai", chat.response))

        return formatted_history[-10:]
