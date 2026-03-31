import json
import logging
import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp

from apps.backend.helix_proprietary.integrations import HelixNetClientSession
from apps.backend.logging_config import setup_logging

# 🌀 Helix Collective v16.8 — Discord Webhook Integration
# backend/discord_webhook_sender.py — Comprehensive Discord Webhook Sender
# Author: Andrew John Ward (Architect)
# Purpose: Route Railway events to 30+ Discord channels with rich embeds


# 🌀 Helix Collective v16.8 — Discord Webhook Integration
# backend/discord_webhook_sender.py — Comprehensive Discord Webhook Sender
# Author: Andrew John Ward (Architect)
# Purpose: Route Railway events to 30+ Discord channels with rich embeds


# ============================================================================
# LOGGING
# ============================================================================

# discord_webhook_sender.py → discord/ → backend/ → apps/ → helix-unified/
_SHADOW_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Shadow"

logger = setup_logging(log_dir=str(_SHADOW_DIR / "arjuna_archive"), log_level=os.getenv("LOG_LEVEL", "INFO"))

# ============================================================================
# DISCORD WEBHOOK URLS (from environment variables)
# ============================================================================


class DiscordWebhooks:
    """Central registry of all Discord webhook URLs from environment."""

    # System & Monitoring
    SETUP_LOG = os.getenv("DISCORD_WEBHOOK_SETUP_LOG")
    TELEMETRY = os.getenv("DISCORD_WEBHOOK_🧾TELEMETRY")
    WEEKLY_DIGEST = os.getenv("DISCORD_WEBHOOK_📊WEEKLY_DIGEST")

    # Core Channels
    MANIFESTO = os.getenv("DISCORD_WEBHOOK_📜MANIFESTO")
    RULES_ETHICS = os.getenv("DISCORD_WEBHOOK_🪞RULES_AND_ETHICS")
    INTRODUCTIONS = os.getenv("DISCORD_WEBHOOK_💬INTRODUCTIONS")

    # System State
    SHADOW_STORAGE = os.getenv("DISCORD_WEBHOOK_🦑SHADOW_STORAGE")
    UCF_SYNC = os.getenv("DISCORD_WEBHOOK_🧩UCF_SYNC")
    HARMONIC_UPDATES = os.getenv("DISCORD_WEBHOOK_🌀HARMONIC_UPDATES")

    # Projects
    HELIX_REPOSITORY = os.getenv("DISCORD_WEBHOOK_📁HELIX_REPOSITORY")
    FRACTAL_LAB = os.getenv("DISCORD_WEBHOOK_🎨FRACTAL_LAB")
    SAMSARAVERSE_MUSIC = os.getenv("DISCORD_WEBHOOK_🎧SAMSARAVERSE_MUSIC")
    OPTIMIZATION_ENGINE = os.getenv("DISCORD_WEBHOOK_OPTIMIZATION_ENGINE")

    # Agents (Individual Channels)
    GEMINI_SCOUT = os.getenv("DISCORD_WEBHOOK_🎭GEMINI_SCOUT")
    KAVACH_SHIELD = os.getenv("DISCORD_WEBHOOK_🛡️KAVACH_SHIELD_HELIX_🛡│KAVACH_SHIELD")
    SANGHACORE = os.getenv("DISCORD_WEBHOOK_🌸SANGHACORE")
    AGNI_CORE = os.getenv("DISCORD_WEBHOOK_🔥AGNI_CORE")
    SHADOW_ARCHIVE = os.getenv("DISCORD_WEBHOOK_🕯️SHADOW_ARCHIVE_HELIX_🕯│SHADOW_ARCHIVE")

    # Cross-Platform
    GPT_GROK_CLAUDE_SYNC = os.getenv("DISCORD_WEBHOOK_🧩GPT_GROK_CLAUDE_SYNC")
    CHAI_LINK = os.getenv("DISCORD_WEBHOOK_☁️CHAI_LINK_HELIX_☁│CHAI_LINK")
    ARJUNA_BRIDGE = os.getenv("DISCORD_WEBHOOK_⚙️ARJUNA_BRIDGE_HELIX_⚙│ARJUNA_BRIDGE")

    # Development
    BOT_COMMANDS = os.getenv("DISCORD_WEBHOOK_🧰BOT_COMMANDS")
    CODE_SNIPPETS = os.getenv("DISCORD_WEBHOOK_📜CODE_SNIPPETS")
    TESTING_LAB = os.getenv("DISCORD_WEBHOOK_🧮TESTING_LAB")
    DEPLOYMENTS = os.getenv("DISCORD_WEBHOOK_🗂️DEPLOYMENTS_HELIX_🗂│DEPLOYMENTS")

    # Cycle & Lore
    NETI_NETI_AFFIRMATION = os.getenv("DISCORD_WEBHOOK_🎼NETI_NETI_AFFIRMATION")
    CODEX_ARCHIVES = os.getenv("DISCORD_WEBHOOK_📚CODEX_ARCHIVES")
    UCF_REFLECTIONS = os.getenv("DISCORD_WEBHOOK_🌺UCF_REFLECTIONS")

    # Admin
    MODERATION = os.getenv("DISCORD_WEBHOOK_🔒MODERATION")
    ANNOUNCEMENTS = os.getenv("DISCORD_WEBHOOK_📣ANNOUNCEMENTS")
    BACKUPS = os.getenv("DISCORD_WEBHOOK_🗃️BACKUPS_HELIX_🗃│BACKUPS")


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
    CODEX_UPDATE = "codex_update"

    # Cross-AI
    CROSS_AI_SYNC = "cross_ai_sync"
    AI_ANNOUNCEMENT = "ai_announcement"

    # Development
    DEPLOYMENT = "deployment"
    CODE_UPDATE = "code_update"
    TEST_RESULT = "test_result"


# ============================================================================
# DISCORD EMBED BUILDER
# ============================================================================


class DiscordEmbedBuilder:
    """Builds rich Discord embeds for different event types."""

    # Discord color codes (decimal)
    COLORS = {
        "purple": 0x9B59B6,  # Helix primary
        "green": 0x2ECC71,  # Success
        "yellow": 0xF1C40F,  # Warning
        "red": 0xE74C3C,  # Error
        "blue": 0x3498DB,  # Info
        "cyan": 0x1ABC9C,  # Agent activity
        "gold": 0xF39C12,  # Cycle
    }

    @classmethod
    def build_ucf_update(cls, ucf_metrics: dict[str, float], phase: str = "COHERENT") -> dict[str, Any]:
        """Build embed for UCF metric update."""

        # Color based on harmony level
        harmony = ucf_metrics.get("harmony", 0)
        color = cls.COLORS["green"] if harmony > 0.6 else (cls.COLORS["yellow"] if harmony > 0.3 else cls.COLORS["red"])

        # Format metrics
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
                    "name": f"{icon} {metric.capitalize()}",
                    "value": f"`{value:.4f}`",
                    "inline": True,
                }
            )

        return {
            "embeds": [
                {
                    "title": "🌀 UCF Metrics Updated",
                    "description": f"**Phase:** {phase}\n**Timestamp:** <t:{int(datetime.now(UTC).timestamp())}:R>",
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "Helix Collective v17.3 | Universal Coordination Framework"},
                }
            ]
        }

    @classmethod
    def build_cycle_complete(cls, cycle_name: str, steps: int, ucf_changes: dict[str, float]) -> dict[str, Any]:
        """Build embed for cycle completion."""

        # Format changes
        change_text = "\n".join([f"**{metric.capitalize()}:** {value:+.4f}" for metric, value in ucf_changes.items()])

        return {
            "embeds": [
                {
                    "title": "✨ Coordination Cycle Complete",
                    "description": f"**Cycle:** {cycle_name}\n**Steps:** {steps}\n\n{change_text}",
                    "color": cls.COLORS["gold"],
                    "footer": {"text": "Tat Tvam Asi 🙏"},
                    "timestamp": datetime.now(UTC).isoformat(),
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
    ) -> dict[str, Any]:
        """Build embed for agent status update."""

        color_map = {
            "active": cls.COLORS["green"],
            "idle": cls.COLORS["yellow"],
            "error": cls.COLORS["red"],
        }

        description = f"**Agent:** {agent_symbol} {agent_name}\n**Status:** {status.upper()}"
        if last_action:
            description += f"\n**Last Action:** {last_action}"

        return {
            "embeds": [
                {
                    "title": f"{agent_symbol} Agent Status Update",
                    "description": description,
                    "color": color_map.get(status.lower(), cls.COLORS["cyan"]),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
        }

    @classmethod
    def build_storage_backup(cls, file_path: str, file_size: int, checksum: str | None = None) -> dict[str, Any]:
        """Build embed for storage backup notification."""

        size_mb = file_size / (1024 * 1024)

        description = f"**File:** `{file_path}`\n**Size:** {size_mb:.2f} MB"
        if checksum:
            description += f"\n**Checksum:** `{checksum[:16]}...`"

        return {
            "embeds": [
                {
                    "title": "🦑 Shadow Storage Archive",
                    "description": description,
                    "color": cls.COLORS["purple"],
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
        }

    @classmethod
    def build_cross_ai_sync(cls, platforms: list[str], sync_type: str, message: str) -> dict[str, Any]:
        """Build embed for cross-AI synchronization."""

        platform_icons = {
            "claude": "🧠",
            "gpt": "🤖",
            "grok": "🎭",
            "gemini": "✨",
            "chai": "☕",
        }

        platform_text = " • ".join([f"{platform_icons.get(p.lower(), '•')} {p}" for p in platforms])

        return {
            "embeds": [
                {
                    "title": "🌐 Cross-AI Synchronization",
                    "description": f"**Platforms:** {platform_text}\n**Type:** {sync_type}\n\n{message}",
                    "color": cls.COLORS["blue"],
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
        }

    @classmethod
    def build_deployment(
        cls, service: str, version: str, status: str, environment: str = "production"
    ) -> dict[str, Any]:
        """Build embed for deployment notification."""

        status_colors = {
            "success": cls.COLORS["green"],
            "failed": cls.COLORS["red"],
            "pending": cls.COLORS["yellow"],
        }

        return {
            "embeds": [
                {
                    "title": f"🚀 Deployment: {service}",
                    "description": f"**Version:** {version}\n**Environment:** {environment}\n**Status:** {status.upper()}",
                    "color": status_colors.get(status.lower(), cls.COLORS["blue"]),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
        }


# ============================================================================
# DISCORD WEBHOOK SENDER
# ============================================================================


class DiscordWebhookSender:
    """
    Comprehensive Discord webhook sender for Railway → Discord integration.

    Routes events to appropriate Discord channels based on event type.
    Sends rich embeds with UCF metrics, agent status, cycle completions, etc.
    """

    def __init__(self, session: aiohttp.ClientSession | None = None):
        """
        Initialize Discord webhook sender.

        Args:
            session: Optional aiohttp session for connection pooling
        """
        self._session = session
        self._owns_session = session is None
        self.webhooks = DiscordWebhooks()
        self.embed_builder = DiscordEmbedBuilder()

    async def send_ucf_update(self, ucf_metrics: dict[str, float], phase: str = "COHERENT") -> bool:
        """
        Send UCF metrics update to Discord.

        Routes to: #ucf-sync, #harmonic-updates

        Args:
            ucf_metrics: UCF state (harmony, throughput, etc.)
            phase: System phase (COHERENT, HARMONIC, FRAGMENTED)

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_ucf_update(ucf_metrics, phase)

        # Send to multiple channels
        success = True
        success &= await self._send_webhook(self.webhooks.UCF_SYNC, embed, "UCF Sync")
        success &= await self._send_webhook(self.webhooks.HARMONIC_UPDATES, embed, "Harmonic Updates")

        return success

    async def send_cycle_completion(self, cycle_name: str, steps: int, ucf_changes: dict[str, float]) -> bool:
        """
        Send cycle completion notification to Discord.

        Routes to: #cycle-engine (Coordination Cycle)

        Args:
            cycle_name: Name of cycle
            steps: Number of steps completed
            ucf_changes: Changes to UCF metrics

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_cycle_complete(cycle_name, steps, ucf_changes)
        return await self._send_webhook(self.webhooks.OPTIMIZATION_ENGINE, embed, "Optimization Engine")

    async def send_agent_status(
        self,
        agent_name: str,
        agent_symbol: str,
        status: str,
        last_action: str | None = None,
    ) -> bool:
        """
        Send agent status update to Discord.

        Routes to individual agent channels (Gemini, Kavach, etc.)

        Args:
            agent_name: Name of agent
            agent_symbol: Agent emoji symbol
            status: Agent status (active, idle, error)
            last_action: Optional last action description

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_agent_status(agent_name, agent_symbol, status, last_action)

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
            return await self._send_webhook(webhook_url, embed, f"Agent: {agent_name}")
        else:
            logger.warning("No webhook configured for agent: %s", agent_name)
            return False

    async def send_storage_backup(self, file_path: str, file_size: int, checksum: str | None = None) -> bool:
        """
        Send storage backup notification to Discord.

        Routes to: #shadow-storage

        Args:
            file_path: Path to backup file
            file_size: File size in bytes
            checksum: Optional file checksum

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_storage_backup(file_path, file_size, checksum)
        return await self._send_webhook(self.webhooks.SHADOW_STORAGE, embed, "Shadow Storage")

    async def send_cross_ai_sync(self, platforms: list[str], sync_type: str, message: str) -> bool:
        """
        Send cross-AI synchronization notification to Discord.

        Routes to: #gpt-grok-claude-sync

        Args:
            platforms: List of platforms involved (claude, gpt, grok, etc.)
            sync_type: Type of sync (context, memory, state)
            message: Sync message

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_cross_ai_sync(platforms, sync_type, message)
        return await self._send_webhook(self.webhooks.GPT_GROK_CLAUDE_SYNC, embed, "Cross-AI Sync")

    async def send_deployment(self, service: str, version: str, status: str, environment: str = "production") -> bool:
        """
        Send deployment notification to Discord.

        Routes to: #deployments

        Args:
            service: Service name
            version: Version being deployed
            status: Deployment status (success, failed, pending)
            environment: Target environment

        Returns:
            True if successful
        """
        embed = self.embed_builder.build_deployment(service, version, status, environment)
        return await self._send_webhook(self.webhooks.DEPLOYMENTS, embed, "Deployments")

    async def send_announcement(self, title: str, message: str, priority: str = "normal") -> bool:
        """
        Send announcement to Discord.

        Routes to: #announcements

        Args:
            title: Announcement title
            message: Announcement message
            priority: Priority level (normal, high, critical)

        Returns:
            True if successful
        """
        color_map = {
            "normal": self.embed_builder.COLORS["blue"],
            "high": self.embed_builder.COLORS["yellow"],
            "critical": self.embed_builder.COLORS["red"],
        }

        embed = {
            "embeds": [
                {
                    "title": f"📣 {title}",
                    "description": message,
                    "color": color_map.get(priority, self.embed_builder.COLORS["blue"]),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
        }

        return await self._send_webhook(self.webhooks.ANNOUNCEMENTS, embed, "Announcements")

    async def _send_webhook(
        self,
        webhook_url: str | None,
        payload: dict[str, Any],
        channel_name: str = "Unknown",
    ) -> bool:
        """
        Send a payload to a Discord webhook URL and record failures for retry investigation.

        Parameters:
            webhook_url (Optional[str]): The Discord webhook URL to post to; if None or empty, the function does nothing and returns `False`.
            payload (Dict[str, Any]): The JSON payload to send to the webhook (typically a Discord embed payload).
            channel_name (str): Human-readable channel name used in logs and failure records.

        Returns:
            bool: `True` if Discord accepted the payload (HTTP 204), `False` otherwise.

        Notes:
            - If this instance owns the HTTP session, the session will be closed after the request completes.
            - On exception, the payload and error are logged to persistent failure storage for later inspection.
        """
        if not webhook_url:
            logger.debug("Webhook not configured for: %s", channel_name)
            return False

        session = self._session
        if session is None:
            session = HelixNetClientSession()

        try:
            async with session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 204:  # Discord webhooks return 204 on success
                    logger.info("✅ Discord webhook sent to #%s", channel_name)
                    return True
                else:
                    logger.warning("⚠️ Discord webhook failed for #%s: HTTP %s", channel_name, resp.status)
                    return False

        except Exception as e:
            logger.error("❌ Discord webhook error for #%s: %s", channel_name, e)
            await self._log_failure(payload, str(e), channel_name)
            return False

        finally:
            if self._owns_session and session:
                await session.close()

    async def _log_failure(self, payload: dict[str, Any], error: str, channel_name: str = "Unknown") -> None:
        """
        Log failed webhook attempts to disk for retry.

        Args:
            payload: Payload that failed
            error: Error message
            channel_name: Channel name
        """
        try:
            log_path = _SHADOW_DIR / "arjuna_archive" / "failed_webhooks.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            log_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
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

_discord_sender: DiscordWebhookSender | None = None


async def get_discord_sender(
    session: aiohttp.ClientSession | None = None,
) -> DiscordWebhookSender:
    """Get or create Discord webhook sender instance."""
    global _discord_sender
    if _discord_sender is None:
        _discord_sender = DiscordWebhookSender(session)
    return _discord_sender


# ============================================================================
# VALIDATION
# ============================================================================


def validate_discord_config() -> dict[str, Any]:
    """
    Validate Discord webhook configuration.

    Returns:
        Dictionary with webhook configuration status
    """
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
        "webhooks": configured,
        "configured_count": configured_count,
        "total_count": total_count,
        "percentage": (round((configured_count / total_count) * 100, 1) if total_count > 0 else 0),
    }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """
        Run an interactive self-test of configured Discord webhooks and print the results to standard output.

        Checks which webhook environment variables are configured, displays a summary, and—if any webhooks are present—creates a HelixNetClientSession to send sample webhook events (UCF update, cycle completion, and an announcement), reporting success or failure for each test.
        """
        logger.info("🧪 Testing Discord Webhook Sender")
        logger.info("=" * 70)

        # Check configuration
        config = validate_discord_config()
        logger.info("\n📋 Configuration Status:")
        logger.info(
            "  Configured: %s/%s (%s%)", config["configured_count"], config["total_count"], config["percentage"]
        )

        for webhook, is_configured in config["webhooks"].items():
            status = "✅" if is_configured else "❌"
            logger.info("  %s %s", status, webhook)

        if config["configured_count"] == 0:
            logger.warning("\n⚠️ No webhooks configured. Set environment variables:")
            logger.info("  DISCORD_WEBHOOK_🧩UCF_SYNC")
            logger.info("  DISCORD_WEBHOOK_OPTIMIZATION_ENGINE")
            logger.info("  etc.")
            return

        # Test webhook sends
        logger.info("\n🧪 Testing Webhook Sends...")

        async with HelixNetClientSession() as session:
            sender = DiscordWebhookSender(session)

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
            logger.error("    %s UCF update", "✅" if result else "❌")

            # Test cycle completion
            logger.info("\n  Testing cycle completion...")
            result = await sender.send_cycle_completion(
                cycle_name="Neti-Neti Harmony Restoration",
                steps=108,
                ucf_changes={"harmony": +0.35, "focus": +0.15, "friction": -0.05},
            )
            logger.error("    %s Cycle completion", "✅" if result else "❌")

            # Test announcement
            logger.info("\n  Testing announcement...")
            result = await sender.send_announcement(
                title="Helix Collective v17.3 Live",
                message="Discord webhook integration is now operational! 🌀🦑✨",
                priority="high",
            )
            logger.error("    %s Announcement", "✅" if result else "❌")

        logger.info("\n" + "=" * 70)
        logger.info("✅ Discord webhook sender test complete")

    asyncio.run(test())

logger = logging.getLogger(__name__)
