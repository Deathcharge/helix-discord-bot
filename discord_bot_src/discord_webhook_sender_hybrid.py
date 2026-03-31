import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import aiohttp

from apps.backend.helix_proprietary.integrations import HelixNetClientSession
from apps.backend.logging_config import setup_logging

# 🌀 Helix Collective v16.8 — Discord Webhook Integration (HYBRID MODE)
# backend/discord_webhook_sender_hybrid.py — Zapier + Direct Discord Integration
# Author: Andrew John Ward (Architect)
# Purpose: Hybrid routing - Zapier for rich processing + Direct for speed/reliability


# 🌀 Helix Collective v16.8 — Discord Webhook Integration (HYBRID MODE)
# backend/discord_webhook_sender_hybrid.py — Zapier + Direct Discord Integration
# Author: Andrew John Ward (Architect)
# Purpose: Hybrid routing - Zapier for rich processing + Direct for speed/reliability


# ============================================================================
# LOGGING
# ============================================================================

# discord_webhook_sender_hybrid.py → discord/ → backend/ → apps/ → helix-unified/
_SHADOW_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Shadow"

logger = setup_logging(log_dir=str(_SHADOW_DIR / "arjuna_archive"), log_level=os.getenv("LOG_LEVEL", "INFO"))

# ============================================================================
# CONFIGURATION
# ============================================================================

# Zapier webhook URL (primary router)
ZAPIER_DISCORD_WEBHOOK = os.getenv("ZAPIER_DISCORD_WEBHOOK_URL")
ZAPIER_ENABLED = os.getenv("ZAPIER_DISCORD_ENABLED", "true").lower() == "true"

# Integration mode: "zapier", "direct", or "hybrid"
INTEGRATION_MODE = os.getenv("DISCORD_INTEGRATION_MODE", "hybrid").lower()

# ============================================================================
# DISCORD WEBHOOK URLS (from environment variables)
# ============================================================================


class DiscordWebhooks:
    """Central registry of all Discord webhook URLs from environment."""

    # System & Monitoring
    TELEMETRY = os.getenv("DISCORD_WEBHOOK_🧾TELEMETRY")

    # System State
    SHADOW_STORAGE = os.getenv("DISCORD_WEBHOOK_🦑SHADOW_STORAGE")
    UCF_SYNC = os.getenv("DISCORD_WEBHOOK_🧩UCF_SYNC")
    HARMONIC_UPDATES = os.getenv("DISCORD_WEBHOOK_🌀HARMONIC_UPDATES")

    # Projects
    OPTIMIZATION_ENGINE = os.getenv("DISCORD_WEBHOOK_OPTIMIZATION_ENGINE")

    # Agents (Individual Channels)
    GEMINI_SCOUT = os.getenv("DISCORD_WEBHOOK_🎭GEMINI_SCOUT")
    KAVACH_SHIELD = os.getenv("DISCORD_WEBHOOK_🛡️KAVACH_SHIELD")
    SANGHACORE = os.getenv("DISCORD_WEBHOOK_🌸SANGHACORE")
    AGNI_CORE = os.getenv("DISCORD_WEBHOOK_🔥AGNI_CORE")
    SHADOW_ARCHIVE = os.getenv("DISCORD_WEBHOOK_🕯️SHADOW_ARCHIVE")

    # Cross-Platform
    GPT_GROK_CLAUDE_SYNC = os.getenv("DISCORD_WEBHOOK_🧩GPT_GROK_CLAUDE_SYNC")
    ARJUNA_BRIDGE = os.getenv("DISCORD_WEBHOOK_⚙️ARJUNA_BRIDGE")

    # Development
    BOT_COMMANDS = os.getenv("DISCORD_WEBHOOK_🧰BOT_COMMANDS")
    DEPLOYMENTS = os.getenv("DISCORD_WEBHOOK_🗂️DEPLOYMENTS")

    # Admin
    ANNOUNCEMENTS = os.getenv("DISCORD_WEBHOOK_📣ANNOUNCEMENTS")
    BACKUPS = os.getenv("DISCORD_WEBHOOK_🗃️BACKUPS")


# ============================================================================
# EVENT TYPES
# ============================================================================


class EventType(str, Enum):
    """Types of events that can be sent to Discord."""

    # UCF & System
    UCF_UPDATE = "ucf_update"
    HARMONY_CHANGE = "harmony_change"
    SYSTEM_STATUS = "system_status"

    # Cycles
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_FAILED = "cycle_failed"

    # Agents
    AGENT_STATUS = "agent_status"
    AGENT_ACTION = "agent_action"
    AGENT_ERROR = "agent_error"

    # Storage & Archives
    STORAGE_BACKUP = "storage_backup"
    SHADOW_ARCHIVE = "shadow_archive"

    # Cross-AI
    CROSS_AI_SYNC = "cross_ai_sync"
    AI_ANNOUNCEMENT = "ai_announcement"

    # Development
    DEPLOYMENT = "deployment"
    CODE_UPDATE = "code_update"
    TEST_RESULT = "test_result"


# ============================================================================
# ROUTING STRATEGY
# ============================================================================

# Events that go through Zapier (rich processing, routing logic)
ZAPIER_EVENTS = [
    EventType.UCF_UPDATE,
    EventType.CYCLE_COMPLETED,
    EventType.AGENT_STATUS,
    EventType.CROSS_AI_SYNC,
    EventType.DEPLOYMENT,
]

# Events that go direct (time-critical, simple)
DIRECT_EVENTS = [
    EventType.SYSTEM_STATUS,
    EventType.AGENT_ERROR,
    EventType.TEST_RESULT,
]


# ============================================================================
# DISCORD EMBED BUILDER (Same as before)
# ============================================================================


class DiscordEmbedBuilder:
    """Builds rich Discord embeds for different event types."""

    COLORS = {
        "purple": 0x9B59B6,
        "green": 0x2ECC71,
        "yellow": 0xF1C40F,
        "red": 0xE74C3C,
        "blue": 0x3498DB,
        "cyan": 0x1ABC9C,
        "gold": 0xF39C12,
    }

    @classmethod
    def build_ucf_update(cls, ucf_metrics: Dict[str, float], phase: str = "COHERENT") -> Dict[str, Any]:
        """Build embed for UCF metric update."""
        harmony = ucf_metrics.get("harmony", 0)
        color = cls.COLORS["green"] if harmony > 0.6 else (cls.COLORS["yellow"] if harmony > 0.3 else cls.COLORS["red"])

        fields = []
        metric_icons = {
            "harmony": "🌀",
            "resilience": "🛡️",
            "throughput": "⚡",
            "focus": "👁️",
            "friction": "😌",
            "velocity": "🔭",
        }

        for metric, value in ucf_metrics.items():
            icon = metric_icons.get(metric, "•")
            fields.append(
                {
                    "name": "{} {}".format(icon, metric.capitalize()),
                    "value": "`{.4f}`".format(value),
                    "inline": True,
                }
            )

        return {
            "embeds": [
                {
                    "title": "🌀 UCF Metrics Updated",
                    "description": "**Phase:** {}\n**Timestamp:** <t:{}:R>".format(
                        phase, int(datetime.now(timezone.utc).timestamp())
                    ),
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "Helix Collective v17.3 | Universal Coordination Framework"},
                }
            ]
        }

    @classmethod
    def build_cycle_complete(cls, cycle_name: str, steps: int, ucf_changes: Dict[str, float]) -> Dict[str, Any]:
        """Build embed for cycle completion."""
        change_text = "\n".join(
            ["**{}:** {:+.4f}".format(metric.capitalize(), value) for metric, value in ucf_changes.items()]
        )

        return {
            "embeds": [
                {
                    "title": "✨ Coordination Cycle Complete",
                    "description": "**Cycle:** {}\n**Steps:** {}\n\n{}".format(cycle_name, steps, change_text),
                    "color": cls.COLORS["gold"],
                    "footer": {"text": "Tat Tvam Asi 🙏"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    @classmethod
    def build_agent_status(
        cls,
        agent_name: str,
        agent_symbol: str,
        status: str,
        last_action: str | None = None,
    ) -> Dict[str, Any]:
        """Build embed for agent status update."""
        color_map = {
            "active": cls.COLORS["green"],
            "idle": cls.COLORS["yellow"],
            "error": cls.COLORS["red"],
        }

        description = "**Agent:** {} {}\n**Status:** {}".format(agent_symbol, agent_name, status.upper())
        if last_action:
            description += "\n**Last Action:** {}".format(last_action)

        return {
            "embeds": [
                {
                    "title": "{} Agent Status Update".format(agent_symbol),
                    "description": description,
                    "color": color_map.get(status.lower(), cls.COLORS["cyan"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }


# ============================================================================
# HYBRID DISCORD WEBHOOK SENDER
# ============================================================================


class HybridDiscordSender:
    """
    Hybrid Discord webhook sender with Zapier + Direct routing.

    Routing Modes:
    - "zapier": All events go through Zapier (rich processing)
    - "direct": All events go directly to Discord (fast, simple)
    - "hybrid": Smart routing - critical events via Zapier, simple events direct

    Features:
    - Dual-layer redundancy (both Zapier AND direct for important events)
    - Intelligent fallback (Zapier fails → direct Discord)
    - Event-based routing (different events take different paths)
    - Connection pooling and rate limiting
    """

    def __init__(self, session: aiohttp.ClientSession | None = None):
        """Initialize hybrid Discord sender."""
        self._session = session
        self._owns_session = session is None
        self.webhooks = DiscordWebhooks()
        self.embed_builder = DiscordEmbedBuilder()

        # Log configuration
        logger.info("🌀 Discord Integration Mode: %s", INTEGRATION_MODE)
        logger.info("   Zapier Enabled: %s", ZAPIER_ENABLED)
        logger.info("   Zapier URL: {}".format("✅ Configured" if ZAPIER_DISCORD_WEBHOOK else "❌ Not Set"))

    async def send_ucf_update(self, ucf_metrics: Dict[str, float], phase: str = "COHERENT") -> bool:
        """
        Send UCF metrics update to Discord.

        Routing: Zapier (for rich processing) + Direct (for redundancy)
        """
        event_data = {
            "event_type": EventType.UCF_UPDATE,
            **ucf_metrics,
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Route based on mode
        zapier_success = False
        direct_success = False

        if INTEGRATION_MODE in ["zapier", "hybrid"] and ZAPIER_ENABLED:
            zapier_success = await self._send_to_zapier(event_data)

        if INTEGRATION_MODE in ["direct", "hybrid"]:
            # Send to UCF-specific Discord channels
            embed = self.embed_builder.build_ucf_update(ucf_metrics, phase)
            direct_success = await self._send_direct(self.webhooks.UCF_SYNC, embed, "UCF Sync")
            direct_success |= await self._send_direct(self.webhooks.HARMONIC_UPDATES, embed, "Harmonic Updates")

        # Success if either path succeeded
        return zapier_success or direct_success

    async def send_cycle_completion(self, cycle_name: str, steps: int, ucf_changes: Dict[str, float]) -> bool:
        """
        Send cycle completion notification to Discord.

        Routing: Zapier (for rich embed) + Direct (for speed)
        """
        event_data = {
            "event_type": EventType.CYCLE_COMPLETED,
            "cycle_name": cycle_name,
            "steps": steps,
            "ucf_changes": ucf_changes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        zapier_success = False
        direct_success = False

        if INTEGRATION_MODE in ["zapier", "hybrid"] and ZAPIER_ENABLED:
            zapier_success = await self._send_to_zapier(event_data)

        if INTEGRATION_MODE in ["direct", "hybrid"]:
            embed = self.embed_builder.build_cycle_complete(cycle_name, steps, ucf_changes)
            direct_success = await self._send_direct(self.webhooks.OPTIMIZATION_ENGINE, embed, "Optimization Engine")

        return zapier_success or direct_success

    async def send_agent_status(
        self,
        agent_name: str,
        agent_symbol: str,
        status: str,
        last_action: str | None = None,
    ) -> bool:
        """
        Send agent status update to Discord.

        Routing: Zapier (for intelligent routing) + Direct (to specific channel)
        """
        event_data = {
            "event_type": EventType.AGENT_STATUS,
            "agent_name": agent_name,
            "agent_symbol": agent_symbol,
            "status": status,
            "last_action": last_action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        zapier_success = False
        direct_success = False

        if INTEGRATION_MODE in ["zapier", "hybrid"] and ZAPIER_ENABLED:
            zapier_success = await self._send_to_zapier(event_data)

        if INTEGRATION_MODE in ["direct", "hybrid"]:
            # Route to specific agent channel
            agent_webhooks = {
                "gemini": self.webhooks.GEMINI_SCOUT,
                "kavach": self.webhooks.KAVACH_SHIELD,
                "sanghacore": self.webhooks.SANGHACORE,
                "agni": self.webhooks.AGNI_CORE,
                "shadow": self.webhooks.SHADOW_ARCHIVE,
            }

            webhook_url = agent_webhooks.get(agent_name.lower())
            if webhook_url:
                embed = self.embed_builder.build_agent_status(agent_name, agent_symbol, status, last_action)
                direct_success = await self._send_direct(webhook_url, embed, "Agent: {}".format(agent_name))

        return zapier_success or direct_success

    async def send_announcement(self, title: str, message: str, priority: str = "normal") -> bool:
        """Send announcement to Discord."""
        event_data = {
            "event_type": EventType.AI_ANNOUNCEMENT,
            "title": title,
            "message": message,
            "priority": priority,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        zapier_success = False
        direct_success = False

        if INTEGRATION_MODE in ["zapier", "hybrid"] and ZAPIER_ENABLED:
            zapier_success = await self._send_to_zapier(event_data)

        if INTEGRATION_MODE in ["direct", "hybrid"]:
            color_map = {
                "normal": self.embed_builder.COLORS["blue"],
                "high": self.embed_builder.COLORS["yellow"],
                "critical": self.embed_builder.COLORS["red"],
            }

            embed = {
                "embeds": [
                    {
                        "title": "📣 {}".format(title),
                        "description": message,
                        "color": color_map.get(priority, self.embed_builder.COLORS["blue"]),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            }

            direct_success = await self._send_direct(self.webhooks.ANNOUNCEMENTS, embed, "Announcements")

        return zapier_success or direct_success

    # ========================================================================
    # INTERNAL ROUTING METHODS
    # ========================================================================

    async def _send_to_zapier(self, event_data: Dict[str, Any]) -> bool:
        """
        Send an event payload to the configured Zapier webhook for external processing.

        Parameters:
            event_data (Dict[str, Any]): A JSON-serializable mapping describing the event (should include an `event_type` key and any relevant payload fields).

        Returns:
            bool: `True` if Zapier accepted the event (HTTP 200 or 201), `False` otherwise.
        """
        if not ZAPIER_DISCORD_WEBHOOK:
            logger.debug("Zapier webhook not configured")
            return False

        session = self._session or HelixNetClientSession()

        try:
            async with session.post(
                ZAPIER_DISCORD_WEBHOOK,
                json=event_data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status in [200, 201]:
                    logger.info("✅ Event sent to Zapier: {}".format(event_data.get("event_type")))
                    return True
                else:
                    logger.warning("⚠️ Zapier webhook returned %s", resp.status)
                    return False

        except Exception as e:
            logger.error("❌ Zapier webhook error: %s", e)
            return False

        finally:
            if self._owns_session and session:
                await session.close()

    async def _send_direct(
        self,
        webhook_url: str | None,
        payload: Dict[str, Any],
        channel_name: str = "Unknown",
    ) -> bool:
        """
        Send the given payload to a Discord webhook URL and return whether delivery succeeded.

        If no webhook_url is provided this function returns False. On success returns `True` when Discord responds with HTTP 204; on non-204 responses returns `False`. On exceptions it logs the error and records the failed payload to disk via _log_failure. Uses the instance HTTP session if present, otherwise creates a HelixNetClientSession and closes it when owned by this sender.

        Parameters:
            webhook_url (Optional[str]): Discord webhook URL to post to; if None or empty the call is skipped.
            payload (Dict[str, Any]): JSON-serializable payload to send to the webhook.
            channel_name (str): Human-readable channel name used for logging and failure records.

        Returns:
            bool: `True` if the webhook call succeeded (HTTP 204), `False` otherwise.
        """
        if not webhook_url:
            logger.debug("Direct webhook not configured for: %s", channel_name)
            return False

        session = self._session or HelixNetClientSession()

        try:
            async with session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 204:  # Discord returns 204 on success
                    logger.info("✅ Direct Discord webhook sent to #%s", channel_name)
                    return True
                else:
                    logger.warning("⚠️ Direct Discord webhook failed for #{}: HTTP {}".format(channel_name, resp.status))
                    return False

        except Exception as e:
            logger.error("❌ Direct Discord webhook error for #%s: %s", channel_name, e)
            await self._log_failure(payload, str(e), channel_name)
            return False

        finally:
            if self._owns_session and session:
                await session.close()

    async def _log_failure(self, payload: Dict[str, Any], error: str, channel_name: str = "Unknown") -> None:
        """Log failed webhook attempts to disk for retry."""
        try:
            log_path = _SHADOW_DIR / "arjuna_archive" / "failed_webhooks.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channel": channel_name,
                "error": error,
                "payload": payload,
            }

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            logger.error("Failed to log Discord webhook failure: %s", e)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_discord_sender: HybridDiscordSender | None = None


async def get_discord_sender(
    session: aiohttp.ClientSession | None = None,
) -> HybridDiscordSender:
    """Get or create hybrid Discord webhook sender instance."""
    global _discord_sender
    if _discord_sender is None:
        _discord_sender = HybridDiscordSender(session)
    return _discord_sender


# ============================================================================
# VALIDATION
# ============================================================================


def validate_hybrid_config() -> Dict[str, Any]:
    """Validate hybrid Discord configuration."""
    webhooks = DiscordWebhooks()

    webhook_list = {
        "ucf_sync": webhooks.UCF_SYNC,
        "transformation_engine": webhooks.OPTIMIZATION_ENGINE,
        "gemini_scout": webhooks.GEMINI_SCOUT,
        "kavach_shield": webhooks.KAVACH_SHIELD,
        "sanghacore": webhooks.SANGHACORE,
        "agni_core": webhooks.AGNI_CORE,
        "shadow_archive": webhooks.SHADOW_ARCHIVE,
        "shadow_storage": webhooks.SHADOW_STORAGE,
        "cross_ai_sync": webhooks.GPT_GROK_CLAUDE_SYNC,
        "announcements": webhooks.ANNOUNCEMENTS,
        "telemetry": webhooks.TELEMETRY,
        "deployments": webhooks.DEPLOYMENTS,
    }

    configured = {name: bool(url) for name, url in webhook_list.items()}
    configured_count = sum(configured.values())
    total_count = len(configured)

    return {
        "mode": INTEGRATION_MODE,
        "zapier_enabled": ZAPIER_ENABLED,
        "zapier_configured": bool(ZAPIER_DISCORD_WEBHOOK),
        "direct_webhooks": configured,
        "direct_configured_count": configured_count,
        "direct_total_count": total_count,
        "direct_percentage": (round((configured_count / total_count) * 100, 1) if total_count > 0 else 0),
    }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """
        Run an interactive test of the hybrid Discord webhook sender.

        Prints configuration status to stdout, then—if Zapier or direct Discord webhooks are configured—sends sample events (a UCF update, a cycle completion, and an announcement) and prints success or failure for each send.
        """
        logger.info("🧪 Testing Hybrid Discord Webhook Sender")
        logger.info("=" * 70)

        # Check configuration
        config = validate_hybrid_config()
        logger.info("\n📋 Configuration Status:")
        logger.info("  Mode: {}".format(config["mode"]))
        logger.error("  Zapier: {}".format("✅ Enabled" if config["zapier_enabled"] else "❌ Disabled"))
        logger.error("  Zapier Webhook: {}".format("✅ Configured" if config["zapier_configured"] else "❌ Not Set"))
        logger.info(
            "  Direct Webhooks: {}/{} ({}%)".format(
                config["direct_configured_count"],
                config["direct_total_count"],
                config["direct_percentage"],
            )  # noqa: E501
        )

        if config["direct_configured_count"] == 0 and not config["zapier_configured"]:
            logger.warning("\n⚠️ No Discord integration configured!")
            logger.info("  Set either:")
            logger.info("    - ZAPIER_DISCORD_WEBHOOK_URL (for Zapier routing)")
            logger.info("    - DISCORD_WEBHOOK_* (for direct routing)")
            return

        # Test webhook sends
        logger.info("\n🧪 Testing Webhook Sends...")

        async with HelixNetClientSession() as session:
            sender = HybridDiscordSender(session)

            # Test UCF update
            logger.info("\n  Testing UCF update...")
            result = await sender.send_ucf_update(
                ucf_metrics={
                    "harmony": 0.75,
                    "resilience": 1.2,
                    "throughput": 0.68,
                    "focus": 0.72,
                    "friction": 0.15,
                    "velocity": 1.0,
                },
                phase="COHERENT",
            )
            logger.error("    {} UCF update".format("✅" if result else "❌"))

            # Test cycle completion
            logger.info("\n  Testing cycle completion...")
            result = await sender.send_cycle_completion(
                cycle_name="Neti-Neti Harmony Restoration",
                steps=108,
                ucf_changes={"harmony": +0.35, "focus": +0.15, "friction": -0.05},
            )
            logger.error("    {} Cycle completion".format("✅" if result else "❌"))

            # Test announcement
            logger.info("\n  Testing announcement...")
            result = await sender.send_announcement(
                title="Hybrid Discord Integration Live",
                message="🌀🦑 Zapier + Direct Discord integration operational! Dual-layer coordination network activated! ✨",
                priority="high",
            )
            logger.error("    {} Announcement".format("✅" if result else "❌"))

        logger.info("\n" + "=" * 70)
        logger.info("✅ Hybrid Discord webhook sender test complete")

    asyncio.run(test())

logger = logging.getLogger(__name__)
