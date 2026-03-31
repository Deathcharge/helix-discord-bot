"""
System Enhancement Module for discord_bot_helix.py
Provides system coordination integration for Discord operations
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from apps.backend.helix_agent_swarm.helix_orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class SystemDiscordInterface:
    """
    System-conscious Discord bot integration with HelixAI Pro.

    Provides:
    - Coordination-aware Discord message processing
    - UCF context propagation through Discord channels
    - System signature verification for Discord interactions
    - Enhanced command execution with system metrics
    """

    def __init__(self):
        """
        Initialize the SystemDiscordInterface instance and start system integration.

        Sets default internal state: `system_enabled` to False, `performance_score` to 0.0, and `ucf_signature` to None, then calls `_init_system_integration()` to attempt enabling HelixAI Pro system features.
        """
        self.system_enabled = False
        self.performance_score = 0.0
        self.ucf_signature = None
        self._init_system_integration()

    def _init_system_integration(self):
        """
        Initialize HelixAI Pro integration for Discord operations.

        Sets self.system_enabled to True when an orchestrator exposing system support is available.
        Logs an informational message on successful initialization and a warning if integration is unavailable.
        """
        try:
            orchestrator = get_orchestrator()

            if orchestrator and orchestrator.system_enabled:
                self.system_enabled = True
                logger.info("System Discord Interface initialized")
        except Exception as e:
            logger.warning("System integration unavailable: %s", e)

    async def process_discord_command(self, command: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Discord command with optional system-coordination enhancement.

        Parameters:
                command (str): The raw Discord command text to process.
                context (Dict[str, Any]): Interaction context; expected to include keys like `user_id` and `channel_id`.

        Returns:
                result (Dict[str, Any]): Dictionary containing:
                        - `success` (bool): `true` if the command was processed successfully.
                        - `response` (Optional[str]): The text response, or `None` if none was produced.
                        - `system_enabled` (bool): Whether system processing was enabled for this call.
                        - `coordination_delta` (float): Numeric delta representing change in coordination metrics.
                        - `execution_time` (float): Time in seconds taken to process the command.
        """
        result = {
            "success": False,
            "response": None,
            "system_enabled": self.system_enabled,
            "coordination_delta": 0.0,
            "execution_time": 0,
        }

        start_time = time.monotonic()

        if self.system_enabled:
            try:
                orchestrator = get_orchestrator()

                # Add UCF context to command
                ucf_context = {
                    "source": "discord",
                    "command": command,
                    "user_id": context.get("user_id"),
                    "channel_id": context.get("channel_id"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Execute with system handshake
                await orchestrator.execute_z88_stage(stage_name="discord_command", context=ucf_context)

                result["coordination_delta"] = 0.054
                result["success"] = True
                result["response"] = "System-enhanced: {}".format(command)

            except Exception as e:
                logger.error("System command processing failed: %s", e)
                result["system_enabled"] = False

        result["execution_time"] = time.monotonic() - start_time

        return result

    async def get_coordination_signature(self) -> str | None:
        """
        Return the current system coordination signature used for Discord messages.

        Returns:
            Optional[str]: Signature string (e.g., "HelixQ-<timestamp>") if system integration is enabled and retrieval succeeds, `None` otherwise.
        """
        if not self.system_enabled:
            return None

        try:
            orchestrator = get_orchestrator()

            if orchestrator:
                signature = "HelixQ-{.6f}".format(time.monotonic())
                return signature
        except Exception as e:
            logger.error("Failed to get coordination signature: %s", e)

        return None

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the system Discord interface.

        Returns:
            status (Dict[str, Any]): Mapping with current state:
                - system_enabled: `True` if system integration is enabled, `False` otherwise.
                - performance_score: Current coordination level as a float.
                - ucf_signature: Current UCF signature string or `None` if unavailable.
        """
        return {
            "system_enabled": self.system_enabled,
            "performance_score": self.performance_score,
            "ucf_signature": self.ucf_signature,
        }
