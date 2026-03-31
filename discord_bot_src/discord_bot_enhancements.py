"""
🌀 Helix Collective v17.0 - Discord Bot Enhancements
backend/discord_bot_enhancements.py

Enhanced decorators and utilities for Discord bot v17.1:
- Coordination-aware command gating
- Permission + role + tier system
- Structured audit logging
- Command metadata & auto-discovery
- Dynamic help generation

Author: Claude (Automation)
Version: 17.1.0
"""

import asyncio
import functools
import json
import logging
import os
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================


class CommandTier(Enum):
    """Command permission tiers."""

    PUBLIC = 1
    MEMBER = 2
    MODERATOR = 3
    ADMIN = 4
    ARCHITECT = 5


class CoordinationGate(Enum):
    """Coordination level requirements."""

    ALWAYS = 0.0  # No minimum
    OPERATIONAL = 5.0  # Min 5.0 coordination
    ELEVATED = 7.0  # Min 7.0 coordination
    TRANSCENDENT = 8.5  # Min 8.5 coordination


# ============================================================================
# AUDIT LOGGING
# ============================================================================


class CommandAuditLog:
    """Structured audit trail for all command executions with robust error handling."""

    def __init__(self, log_file: Path | None = None):
        # discord_bot_enhancements.py → discord/ → backend/ → apps/ → helix-unified/
        _shadow = Path(__file__).resolve().parent.parent.parent.parent / "Shadow"
        self.log_file = log_file or (_shadow / "helix_archive" / "command_audit.jsonl")
        try:
            logger.info("📁 Audit log directory created: %s", self.log_file.parent)
        except Exception as e:
            logger.error("❌ Failed to create audit log directory: %s", e)
            raise

    async def log_command(
        self,
        user_id: int,
        user_name: str,
        command_name: str,
        guild_id: int | None,
        guild_name: str | None,
        performance_score: float,
        success: bool,
        outcome: str,
        error: str | None = None,
    ) -> None:
        """Log command execution to audit trail with error handling."""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                logger.warning("⚠️ Invalid user_id: %s", user_id)
                return

            if not isinstance(command_name, str) or not command_name.strip():
                logger.warning("⚠️ Invalid command_name: %s", command_name)
                return

            entry = {
                "timestamp": datetime.now(UTC).isoformat() + "Z",
                "user_id": user_id,
                "user_name": str(user_name)[:100],  # Limit length
                "command_name": str(command_name)[:50],
                "guild_id": guild_id,
                "guild_name": str(guild_name)[:100] if guild_name else None,
                "performance_score": round(float(performance_score), 2),
                "success": bool(success),
                "outcome": str(outcome)[:200],
                "error": str(error)[:500] if error else None,
            }

            # Write to JSONL file with error handling (async-safe)
            def write_audit_entry():
                """Blocking file write (run in thread pool)"""
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            try:
                await asyncio.get_running_loop().run_in_executor(None, write_audit_entry)
            except PermissionError:
                logger.exception("❌ Permission denied writing to audit log")
            except OSError:
                logger.exception("❌ OS error writing to audit log")
            except (ValueError, TypeError, KeyError, IndexError):
                logger.exception("❌ Unexpected error writing audit log")

            logger.info("🔍 Audit: %s → %s [%s]", user_name, command_name, outcome)

        except Exception as e:
            logger.error("❌ Failed to log command audit: %s", e)
            logger.debug("Stack trace: %s", traceback.format_exc())

    async def get_user_history(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Get command history for user with error handling."""
        if not self.log_file.exists():
            logger.debug("📁 Audit log file not found: %s", self.log_file)
            return []

        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning("⚠️ Invalid user_id for history lookup: %s", user_id)
            return []

        entries = []
        try:
            with open(self.log_file, encoding="utf-8") as f:
                for _line_num, line in enumerate(f, 1):
                    try:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        if entry.get("user_id") == user_id:
                            entries.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning("⚠️ Invalid JSON in audit log at line {line_num}: %s", e)
                    except Exception as e:
                        logger.warning("⚠️ Error processing audit log line {line_num}: %s", e)

        except PermissionError:
            logger.error("❌ Permission denied reading audit log: %s", self.log_file)
            return []
        except OSError as e:
            logger.error("❌ OS error reading audit log: %s", e)
            return []
        except Exception as e:
            logger.error("❌ Unexpected error reading audit log: %s", e)
            return []

        return entries[-limit:]

    async def get_statistics(self) -> dict[str, Any]:
        """Get audit statistics with comprehensive error handling."""
        if not self.log_file.exists():
            logger.debug("📁 Audit log file not found for statistics: %s", self.log_file)
            return {"total_commands": 0, "success_rate": 0.0, "top_commands": []}

        total = 0
        success = 0
        command_counts: dict[str, int] = {}
        errors = 0

        try:
            with open(self.log_file, encoding="utf-8") as f:
                for _line_num, line in enumerate(f, 1):
                    try:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        total += 1

                        if entry.get("success"):
                            success += 1

                        cmd = entry.get("command_name", "unknown")
                        command_counts[cmd] = command_counts.get(cmd, 0) + 1

                    except json.JSONDecodeError as e:
                        errors += 1
                        logger.warning("⚠️ Invalid JSON in audit log at line {line_num}: %s", e)
                    except Exception as e:
                        errors += 1
                        logger.warning("⚠️ Error processing audit log line {line_num}: %s", e)

        except PermissionError:
            logger.error(
                "❌ Permission denied reading audit log for statistics: %s",
                self.log_file,
            )
            return {
                "total_commands": 0,
                "success_rate": 0.0,
                "top_commands": [],
                "errors": 0,
            }
        except OSError as e:
            logger.error("❌ OS error reading audit log for statistics: %s", e)
            return {
                "total_commands": 0,
                "success_rate": 0.0,
                "top_commands": [],
                "errors": 0,
            }
        except Exception as e:
            logger.error("❌ Unexpected error reading audit log for statistics: %s", e)
            return {
                "total_commands": 0,
                "success_rate": 0.0,
                "top_commands": [],
                "errors": 0,
            }

        top_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        stats = {
            "total_commands": total,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0.0,
            "top_commands": [{"command": cmd, "count": count} for cmd, count in top_commands],
            "errors": errors,
            "error_rate": round(errors / total * 100, 2) if total > 0 else 0.0,
        }

        logger.info(
            "📊 Audit statistics: {total} commands, {success} successful, %s errors",
            errors,
        )
        return stats

    async def cleanup_old_entries(self, days_to_keep: int = 30) -> int:
        """Clean up old audit entries to prevent log file bloat."""
        if not self.log_file.exists():
            return 0

        cutoff_date = datetime.now(UTC).timestamp() - (days_to_keep * 24 * 3600)
        cleaned_count = 0
        temp_file = self.log_file.with_suffix(".tmp")

        try:
            with open(self.log_file, encoding="utf-8") as f, open(temp_file, "w", encoding="utf-8") as temp_f:
                for line in f:
                    try:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        entry_time = datetime.fromisoformat(entry["timestamp"].rstrip("Z")).timestamp()

                        if entry_time >= cutoff_date:
                            temp_f.write(line)
                        else:
                            cleaned_count += 1

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning("⚠️ Skipping invalid audit entry during cleanup: %s", e)
                        cleaned_count += 1

            # Replace original with cleaned file
            temp_file.replace(self.log_file)
            logger.info("🧹 Cleaned up %s old audit entries", cleaned_count)
            return cleaned_count

        except Exception as e:
            logger.error("❌ Failed to cleanup audit log: %s", e)
            if temp_file.exists():
                temp_file.unlink()
            return 0


# ============================================================================
# COMMAND REGISTRY & METADATA
# ============================================================================


class CommandMetadata:
    """Metadata for a command."""

    def __init__(
        self,
        name: str,
        description: str,
        tier: CommandTier = CommandTier.PUBLIC,
        coordination_gate: CoordinationGate = CoordinationGate.ALWAYS,
        aliases: list[str] | None = None,
        examples: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.tier = tier
        self.coordination_gate = coordination_gate
        self.aliases = aliases or []
        self.examples = examples or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for help/discovery."""
        return {
            "name": self.name,
            "description": self.description,
            "tier": self.tier.name,
            "coordination_gate": f"{self.coordination_gate.value}+",
            "aliases": self.aliases,
            "examples": self.examples,
        }


class CommandRegistry:
    """Registry of all bot commands with metadata."""

    def __init__(self):
        self._commands: dict[str, CommandMetadata] = {}

    def register(self, metadata: CommandMetadata) -> None:
        """Register command metadata."""
        self._commands[metadata.name] = metadata
        logger.info("📋 Registered command: %s (%s)", metadata.name, metadata.tier.name)

    def get(self, name: str) -> CommandMetadata | None:
        """Get command metadata."""
        return self._commands.get(name.lower())

    def get_all(self) -> dict[str, CommandMetadata]:
        """Get all registered commands."""
        return self._commands

    def get_by_tier(self, tier: CommandTier) -> list[CommandMetadata]:
        """Get all commands at or below tier."""
        return [cmd for cmd in self._commands.values() if cmd.tier.value <= tier.value]

    def get_by_coordination(self, coordination: float) -> list[CommandMetadata]:
        """Get all commands available at coordination level."""
        return [cmd for cmd in self._commands.values() if coordination >= cmd.coordination_gate.value]


# ============================================================================
# DECORATORS
# ============================================================================

_audit_log = CommandAuditLog()
_registry = CommandRegistry()


def register_command(
    name: str,
    description: str,
    tier: CommandTier = CommandTier.PUBLIC,
    coordination_gate: CoordinationGate = CoordinationGate.ALWAYS,
    aliases: list[str] | None = None,
    examples: list[str] | None = None,
) -> Callable:
    """Decorator to register and metadata a command."""

    def decorator(func: Callable) -> Callable:
        metadata = CommandMetadata(
            name=name,
            description=description,
            tier=tier,
            coordination_gate=coordination_gate,
            aliases=aliases,
            examples=examples,
        )
        _registry.register(metadata)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper.metadata = metadata  # Attach metadata
        return wrapper

    return decorator


def require_coordination(min_level: float) -> Callable:
    """Decorator: Gate command by coordination level."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ctx: commands.Context, *args, **kwargs):
            from apps.backend.core.ucf_helpers import calculate_performance_score, get_current_ucf

            ucf = get_current_ucf()
            coordination = calculate_performance_score(ucf)

            if coordination < min_level:
                await ctx.send(
                    f"⚠️ **Coordination Gate**\n"
                    f"Required: {min_level}+ coordination\n"
                    f"Current: {coordination:.2f}\n"
                    f"Status: **INSUFFICIENT**"
                )
                return

            return await func(ctx, *args, **kwargs)

        return wrapper

    return decorator


def require_tier(tier: CommandTier) -> Callable:
    """Decorator: Gate command by permission tier."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ctx: commands.Context, *args, **kwargs):
            # Get user's tier
            user_tier = await _get_user_tier(ctx.author, ctx.guild)

            if user_tier.value < tier.value:
                await ctx.send(f"🔒 **Permission Denied**\nRequired: {tier.name}\nYour tier: {user_tier.name}")
                return

            return await func(ctx, *args, **kwargs)

        return wrapper

    return decorator


def audit_command() -> Callable:
    """Decorator: Log all command executions with enhanced error handling."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ctx: commands.Context, *args, **kwargs):
            # Safely get UCF and coordination level
            coordination = 0.0
            try:
                from apps.backend.core.ucf_helpers import calculate_performance_score, get_current_ucf

                ucf = get_current_ucf()
                coordination = calculate_performance_score(ucf)
            except Exception as e:
                logger.warning("⚠️ Failed to get UCF for audit logging: %s", e)
                coordination = 0.0

            # Safely get context information
            user_id = ctx.author.id if ctx.author else 0
            user_name = str(ctx.author) if ctx.author else "Unknown"
            guild_id = ctx.guild.id if ctx.guild else None
            guild_name = ctx.guild.name if ctx.guild else None
            command_name = func.__name__

            try:
                result = await func(ctx, *args, **kwargs)
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=True,
                    outcome="SUCCESS",
                )
                return result

            # Note: Order matters - catch specific exceptions before base CommandError
            except commands.MissingPermissions as e:
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="MISSING_PERMISSIONS",
                    error=str(e),
                )
                await ctx.send(f"🔒 Missing permissions: {e!s}")
                raise

            except commands.BadArgument as e:
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="BAD_ARGUMENT",
                    error=str(e),
                )
                await ctx.send(f"⚠️ Invalid argument: {e!s}")
                raise

            except commands.CommandNotFound as e:
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="COMMAND_NOT_FOUND",
                    error=str(e),
                )
                await ctx.send(f"❓ Command not found: {e!s}")
                raise

            except commands.CommandError as e:
                # Handle Discord-specific command errors (base class - must be after specific exceptions)
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="COMMAND_ERROR",
                    error=str(e),
                )
                await ctx.send(f"❌ Command error: {e!s}")
                raise

            except discord.Forbidden as e:
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="DISCORD_FORBIDDEN",
                    error=str(e),
                )
                await ctx.send("🚫 Bot lacks permission to perform this action")
                raise

            except discord.HTTPException as e:
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="DISCORD_HTTP_ERROR",
                    error=f"HTTP {e.status}: {e!s}",
                )
                await ctx.send(f"🌐 Discord API error: {e.status}")
                raise

            except Exception as e:
                # Generic error handling
                error_msg = f"{type(e).__name__}: {e!s}"
                await _audit_log.log_command(
                    user_id=user_id,
                    user_name=user_name,
                    command_name=command_name,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    performance_score=coordination,
                    success=False,
                    outcome="UNHANDLED_ERROR",
                    error=error_msg,
                )

                # Log full traceback for debugging
                logger.error("❌ Unhandled error in %s: %s", command_name, error_msg)
                logger.debug("Stack trace: %s", traceback.format_exc())

                # Send user-friendly error message
                await ctx.send("❌ Unexpected error occurred. Please try again later.")
                raise

        return wrapper

    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


# Subscription tier → CommandTier mapping for linked accounts
_SUBSCRIPTION_TIER_MAP = {
    "enterprise": CommandTier.ADMIN,
    "pro": CommandTier.MODERATOR,
    "starter": CommandTier.MODERATOR,
    "hobby": CommandTier.MEMBER,
    "free": CommandTier.MEMBER,
}


async def _get_subscription_tier(discord_id: str) -> CommandTier | None:
    """Look up linked Helix account's subscription tier and map to CommandTier."""
    try:
        from apps.backend.database import get_async_session
        from apps.backend.discord.discord_account_link import get_subscription_tier_for_discord

        async with get_async_session() as db:
            sub_tier = await get_subscription_tier_for_discord(db, discord_id)

        if sub_tier is None:
            return None  # Not linked

        return _SUBSCRIPTION_TIER_MAP.get(sub_tier, CommandTier.MEMBER)
    except Exception as e:
        logger.warning("⚠️ Failed to check subscription tier for Discord %s: %s", discord_id, e)
        return None


async def _get_user_tier(user: discord.User, guild: discord.Guild | None) -> CommandTier:
    """Determine user's permission tier with error handling.

    Priority order:
    1. ARCHITECT — hardcoded admin user ID
    2. Discord guild roles (administrator → ADMIN, moderator role → MODERATOR)
    3. Linked Helix subscription tier (enterprise/pro → MODERATOR+, etc.)
    4. MEMBER fallback

    The highest tier from Discord roles vs subscription is used.
    """
    try:
        admin_id = os.getenv("ADMIN_USER_ID")
        if not admin_id:
            logger.debug("ADMIN_USER_ID not set — ARCHITECT tier disabled")
        else:
            try:
                if user.id == int(admin_id):
                    return CommandTier.ARCHITECT
            except ValueError:
                logger.warning("⚠️ Invalid ADMIN_USER_ID: %s", admin_id)

        # Start with MEMBER as baseline
        best_tier = CommandTier.MEMBER

        # In guild context, check roles
        if guild and isinstance(user, discord.Member):
            try:
                if user.guild_permissions.administrator:
                    best_tier = CommandTier.ADMIN

                # Moderator role (check for "Moderator" role)
                if best_tier.value < CommandTier.MODERATOR.value:
                    moderator_roles = [r for r in user.roles if "moderator" in r.name.lower()]
                    if moderator_roles:
                        best_tier = CommandTier.MODERATOR
            except Exception as e:
                logger.warning("⚠️ Error checking guild permissions for %s: %s", user, e)

        # Check linked subscription tier — use whichever is higher
        sub_tier = await _get_subscription_tier(str(user.id))
        if sub_tier is not None and sub_tier.value > best_tier.value:
            best_tier = sub_tier

        return best_tier

    except Exception as e:
        logger.error("❌ Failed to determine user tier for %s: %s", user, e)
        return CommandTier.MEMBER  # Safe default


async def get_command_help(command_name: str) -> str | None:
    """Get help text for command with error handling."""
    try:
        if not command_name or not isinstance(command_name, str):
            logger.warning("⚠️ Invalid command_name for help: %s", command_name)
            return None

        metadata = _registry.get(command_name)
        if not metadata:
            return None

        help_text = f"**{metadata.name}**\n"
        help_text += f"{metadata.description}\n\n"

        if metadata.tier != CommandTier.PUBLIC:
            help_text += f"🔒 **Tier**: {metadata.tier.name}\n"

        if metadata.coordination_gate != CoordinationGate.ALWAYS:
            help_text += f"🧠 **Coordination**: {metadata.coordination_gate.value}+\n"

        if metadata.aliases:
            help_text += f"📝 **Aliases**: {', '.join(metadata.aliases)}\n"

        if metadata.examples:
            help_text += f"💡 **Examples**:\n"  # noqa
            for ex in metadata.examples:
                help_text += f"  `{ex}`\n"

        return help_text

    except Exception as e:
        logger.error("❌ Failed to generate help for %s: %s", command_name, e)
        return None


async def get_available_commands(user: discord.User, guild: discord.Guild | None) -> list[CommandMetadata]:
    """Get commands available to user based on tier + coordination with error handling."""
    try:
        # Get user tier with error handling
        user_tier = await _get_user_tier(user, guild)

        # Get coordination level with error handling
        coordination = 0.0
        try:
            from apps.backend.core.ucf_helpers import calculate_performance_score, get_current_ucf

            ucf = get_current_ucf()
            coordination = calculate_performance_score(ucf)
        except Exception as e:
            logger.warning("\u26a0\ufe0f Failed to get coordination level: %s", e)
            coordination = 0.0

        available = []
        try:
            for cmd in _registry.get_all().values():
                if cmd.tier.value <= user_tier.value and coordination >= cmd.coordination_gate.value:
                    available.append(cmd)
        except Exception as e:
            logger.error("❌ Error filtering available commands: %s", e)
            return []

        return available

    except Exception as e:
        logger.error("❌ Failed to get available commands: %s", e)
        return []


# ============================================================================
# PERSONALITY-AWARE RESPONSE ROUTER
# ============================================================================


class PersonalityRouter:
    """Route command responses based on coordination level + personality."""

    CRISIS_RESPONSES: ClassVar[dict[str, str]] = {
        "help": "🚨 **EMERGENCY MODE** - Core systems only available",
        "error": "⚠️ Crisis detected. Focusing on recovery.",
    }

    OPERATIONAL_RESPONSES: ClassVar[dict[str, str]] = {
        "help": "📋 Available commands (Operational Mode)",
        "error": "❌ Command error - investigating",
    }

    TRANSCENDENT_RESPONSES: ClassVar[dict[str, str]] = {
        "help": "✨ Full coordination network available",
        "error": "🔄 Learning from this error for evolution",
    }

    @staticmethod
    def get_response_style(coordination: float) -> dict[str, str]:
        """Get response style for coordination level."""
        if coordination <= 4.0:
            return PersonalityRouter.CRISIS_RESPONSES
        elif coordination >= 8.5:
            return PersonalityRouter.TRANSCENDENT_RESPONSES
        else:
            return PersonalityRouter.OPERATIONAL_RESPONSES


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "CommandAuditLog",
    "CommandMetadata",
    "CommandRegistry",
    "CommandTier",
    "CoordinationGate",
    "PersonalityRouter",
    "_audit_log",
    "_registry",
    "audit_command",
    "get_available_commands",
    "get_command_help",
    "register_command",
    "require_coordination",
    "require_tier",
]
