# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Character memory management using CAMEL's ChatHistoryMemory."""

from typing import List, Optional

from camel.memories import ChatHistoryMemory, ScoreBasedContextCreator
from camel.memories.base import BaseContextCreator
from camel.memories.records import ContextRecord, MemoryRecord
from camel.types import OpenAIBackendRole


class CharacterMemory:
    """Manages conversation memory for a character agent.

    This wraps CAMEL's ChatHistoryMemory to provide a simpler interface
    for the murder mystery game context.
    """

    def __init__(
        self,
        context_creator: BaseContextCreator,
        window_size: Optional[int] = 50,
        agent_id: Optional[str] = None,
    ):
        """Initialize the character memory.

        Args:
            context_creator: The context creator for managing token limits.
            window_size: Maximum number of recent messages to keep.
            agent_id: Optional ID for this agent.
        """
        self._memory = ChatHistoryMemory(
            context_creator=context_creator,
            window_size=window_size,
            agent_id=agent_id,
        )

    @property
    def agent_id(self) -> Optional[str]:
        """Get the agent ID."""
        return self._memory.agent_id

    @agent_id.setter
    def agent_id(self, val: str) -> None:
        """Set the agent ID."""
        self._memory.agent_id = val

    def retrieve(self) -> List[ContextRecord]:
        """Retrieve memory records.

        Returns:
            List of context records.
        """
        return self._memory.retrieve()

    def add_message(
        self,
        role: str,
        content: str,
        role_name: str = "User",
    ) -> None:
        """Add a message to the memory.

        Args:
            role: The role (user, assistant, system).
            content: The message content.
            role_name: The name of the role.
        """
        if role == "user":
            from camel.messages import BaseMessage
            msg = BaseMessage.make_user_message(
                role_name=role_name,
                content=content,
            )
            record = MemoryRecord.from_base_message(msg)
        elif role == "assistant":
            from camel.messages import BaseMessage
            msg = BaseMessage.make_assistant_message(
                role_name=role_name,
                content=content,
            )
            record = MemoryRecord.from_base_message(msg)
        else:
            from camel.messages import BaseMessage
            msg = BaseMessage(
                role_name=role_name,
                role_type=OpenAIBackendRole.USER,
                content=content,
            )
            record = MemoryRecord.from_base_message(msg)

        self._memory.write_records([record])

    def add_user_message(self, content: str, role_name: str = "Player") -> None:
        """Add a user message to memory.

        Args:
            content: The message content.
            role_name: The name of the user.
        """
        self.add_message("user", content, role_name)

    def add_assistant_message(self, content: str, role_name: str = "Assistant") -> None:
        """Add an assistant message to memory.

        Args:
            content: The message content.
            role_name: The name of the assistant.
        """
        self.add_message("assistant", content, role_name)

    def get_context(self) -> List[ContextRecord]:
        """Get the current context for the agent.

        Returns:
            List of context records.
        """
        return self._memory.retrieve()

    def clear(self) -> None:
        """Clear all memory records."""
        self._memory.clear()

    def pop_records(self, count: int) -> List[MemoryRecord]:
        """Remove the most recent records.

        Args:
            count: Number of records to remove.

        Returns:
            The removed records.
        """
        return self._memory.pop_records(count)

    def set_context_creator(self, context_creator: BaseContextCreator) -> None:
        """Update the context creator.

        Args:
            context_creator: The new context creator.
        """
        self._memory = ChatHistoryMemory(
            context_creator=context_creator,
            window_size=self._memory._window_size,
            agent_id=self._memory.agent_id,
        )
