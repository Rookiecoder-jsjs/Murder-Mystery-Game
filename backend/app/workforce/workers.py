# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========

"""Worker management for the murder mystery game workforce."""

from typing import Any, Dict, List, Optional

from camel.agents import ChatAgent
from camel.societies.workforce import SingleAgentWorker

from app.agents.character_agent import MurderMysteryCharacterAgent


class CharacterWorkerManager:
    """Manages SingleAgentWorker instances for character agents."""

    def __init__(self):
        """Initialize the worker manager."""
        self._workers: Dict[str, SingleAgentWorker] = {}
        self._agent_map: Dict[str, MurderMysteryCharacterAgent] = {}

    def add_character_worker(
        self,
        character_id: str,
        agent: MurderMysteryCharacterAgent,
        use_agent_pool: bool = True,
    ) -> SingleAgentWorker:
        """Add a character as a SingleAgentWorker.

        Args:
            character_id: The character's ID.
            agent: The MurderMysteryCharacterAgent instance.
            use_agent_pool: Whether to use agent pooling.

        Returns:
            The created SingleAgentWorker.
        """
        worker = SingleAgentWorker(
            description=f"Character: {agent.name}",
            worker=agent.agent,
            use_agent_pool=use_agent_pool,
        )
        self._workers[character_id] = worker
        self._agent_map[character_id] = agent
        return worker

    def get_worker(self, character_id: str) -> Optional[SingleAgentWorker]:
        """Get a worker by character ID.

        Args:
            character_id: The character's ID.

        Returns:
            The SingleAgentWorker or None.
        """
        return self._workers.get(character_id)

    def get_agent(self, character_id: str) -> Optional[MurderMysteryCharacterAgent]:
        """Get the agent for a character.

        Args:
            character_id: The character's ID.

        Returns:
            The MurderMysteryCharacterAgent or None.
        """
        return self._agent_map.get(character_id)

    def get_all_workers(self) -> Dict[str, SingleAgentWorker]:
        """Get all workers.

        Returns:
            Dictionary of character_id to SingleAgentWorker.
        """
        return dict(self._workers)

    def get_all_agents(self) -> Dict[str, MurderMysteryCharacterAgent]:
        """Get all agents.

        Returns:
            Dictionary of character_id to MurderMysteryCharacterAgent.
        """
        return dict(self._agent_map)

    def remove_worker(self, character_id: str) -> bool:
        """Remove a worker.

        Args:
            character_id: The character's ID.

        Returns:
            True if removed, False if not found.
        """
        if character_id in self._workers:
            del self._workers[character_id]
            if character_id in self._agent_map:
                del self._agent_map[character_id]
            return True
        return False

    def reset_all(self) -> None:
        """Reset all agents in the workers."""
        for agent in self._agent_map.values():
            agent.reset()

    def clear(self) -> None:
        """Clear all workers and agents."""
        self._workers.clear()
        self._agent_map.clear()
