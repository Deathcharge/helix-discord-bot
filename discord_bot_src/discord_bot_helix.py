# 🌀 Helix Collective v17.3 — Helix Hub Production Release
# discord_bot_helix.py — Discord bridge (with async cycle fix + Kavach scanning fix)
# Author: Andrew John Ward (Architect)
"""
Helix Collective - Discord Interface v17.3
Helix Hub Production Release

Features:
- Kavach ethical scanning
- Helix cycle execution
- UCF state monitoring
- Automatic telemetry
- Channel announcements
"""

import asyncio
import datetime
import io
import json
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from datetime import (
    timedelta,  # Only import timedelta, not datetime (avoid shadowing)
)
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands, tasks

from apps.backend.agents import AGENTS
from apps.backend.coordination_engine import load_ucf_state
from apps.backend.helix_proprietary.integrations import HelixNetClientSession
from apps.backend.helix_spirals.event_bus import SpiralEventBus as ZapierClient  # v17.8 Migrated to native Spirals

# Configure logger
logger = logging.getLogger(__name__)

# Import helpdesk agent (after logger is defined)
try:
    from apps.backend.services.helpdesk_agent import HelpDeskAgent

    helpdesk_agent = HelpDeskAgent()
except ImportError as e:
    logger.warning("Could not import helpdesk agent: %s", e)
    helpdesk_agent = None


# ============================================================================
# GUILD-AWARE COMMAND GATING
# ============================================================================

# Official Helix server guild ID (set via DISCORD_GUILD_ID env var)
HELIX_OFFICIAL_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

# Commands that work on any server (public/helpdesk)
public_commands = {
    "helpdesk",
    "faq",
    "ticket",
    "agents",
    "agent",
    "collaborate",
    "transcribe",
    "analyze_emotion",
    "help",
    "addcommand",
    "delcommand",
    "listcommands",
}

# Commands that should ONLY work on the official Helix server
official_only_commands = {
    # Admin/Setup commands
    "setup",
    "webhooks",
    "discover-channels",
    "verify-setup",
    "seed",
    "notion-sync",
    "refresh",
    "clean",
    "test-all",
    "test-commands",
    "test-webhooks",
    "test-api",
    "validate-system",
    # Content management
    "update-manifesto",
    "update-codex",
    "codex-version",
    "update-rules",
    "update-cycle-guide",
    "ucf",
    # Context/Storage
    "backup",
    "load",
    "contexts",
    "archive",
    # System
    "heartbeat",
    "storage",
    "sync",
    "discovery",
    "cycle",
    "harmony",
    # Advanced
    "dashboard",
    "macs",
    "deploy",
    "webhook-health",
    "tools",
    "launch-checklist",
}


# ============================================================================
# CUSTOM COMMAND GATING DECORATOR
# ============================================================================


def official_server_only():
    """
    Check decorator that restricts commands to official Helix server only.

    Usage:
        @bot.command(name="mycommand")
        @official_server_only()
        async def my_command(ctx):
            ...
    """

    async def check(ctx: commands.Context) -> bool:
        if not HELIX_OFFICIAL_GUILD_ID:
            # No guild ID configured - allow all (development mode)
            return True

        if not ctx.guild:
            await ctx.send("❌ This command only works in servers.")
            return False

        try:
            guild_id = int(HELIX_OFFICIAL_GUILD_ID)
            if ctx.guild.id != guild_id:
                await ctx.send(
                    "❌ This command is only available on the official Helix server.\n"
                    "Join us at: https://discord.gg/helix"
                )
                return False
            return True
        except (ValueError, TypeError):
            logger.error("Invalid DISCORD_GUILD_ID: %s", HELIX_OFFICIAL_GUILD_ID)
            return True  # Allow on error

    return commands.check(check)


def is_official_server(ctx: commands.Context) -> bool:
    """Check if the command is being used in the official Helix server"""
    if not HELIX_OFFICIAL_GUILD_ID:
        # If no guild ID configured, allow all (development mode)
        logger.warning("DISCORD_GUILD_ID not set - commands not gated to official server")
        return True

    try:
        guild_id = int(HELIX_OFFICIAL_GUILD_ID)
        return ctx.guild is not None and ctx.guild.id == guild_id
    except (ValueError, TypeError):
        logger.error("Invalid DISCORD_GUILD_ID: %s", HELIX_OFFICIAL_GUILD_ID)
        return False


def is_public_command(cmd_name: str) -> bool:
    """Check if a command is public (works on any server)"""
    return cmd_name.lower() in public_commands


# Guild storage: database-backed with JSON fallback (resolves Railway ephemeral FS issue)
from apps.backend.discord.discord_guild_storage import guild_storage  # noqa: E402

# Aliases for backward compatibility — code references these module-level dicts
custom_commands: dict[int, dict[str, str]] = guild_storage.custom_commands
welcome_configs: dict[int, dict[str, Any]] = guild_storage.welcome_configs


# ============================================================================
# AUTONOMOUS AGENT MENTION SYSTEM
# ============================================================================

# Agent name variations for mention detection — all 24 canonical agents
AGENT_MENTIONS = {
    "kael": {"aliases": ["kael", "Kael", "KAEL"], "description": "Ethical Reasoning"},
    "lumina": {"aliases": ["lumina", "Lumina", "LUMINA"], "description": "Empathic Resonance"},
    "vega": {"aliases": ["vega", "Vega", "VEGA"], "description": "Strategic Navigation"},
    "gemini": {"aliases": ["gemini", "Gemini", "GEMINI"], "description": "Dual-Mode Reasoning"},
    "agni": {"aliases": ["agni", "Agni", "AGNI"], "description": "Transformation Catalyst"},
    "kavach": {"aliases": ["kavach", "Kavach", "KAVACH"], "description": "Security & Protection"},
    "sanghacore": {"aliases": ["sanghacore", "SanghaCore", "Sangha"], "description": "Community Coordination"},
    "shadow": {"aliases": ["shadow", "Shadow", "SHADOW"], "description": "Introspection & Risk Analysis"},
    "echo": {"aliases": ["echo", "Echo", "ECHO"], "description": "Pattern Recognition"},
    "phoenix": {"aliases": ["phoenix", "Phoenix", "PHOENIX"], "description": "Recovery & Renewal"},
    "oracle": {"aliases": ["oracle", "Oracle", "ORACLE"], "description": "Foresight & Prediction"},
    "sage": {"aliases": ["sage", "Sage", "SAGE"], "description": "Wisdom & Synthesis"},
    "helix": {"aliases": ["helix", "Helix", "HELIX"], "description": "Primary Executor"},
    "mitra": {"aliases": ["mitra", "Mitra", "MITRA"], "description": "Collaboration Manager"},
    "varuna": {"aliases": ["varuna", "Varuna", "VARUNA"], "description": "System Integrity"},
    "surya": {"aliases": ["surya", "Surya", "SURYA"], "description": "Clarity Engine"},
    "arjuna": {"aliases": ["arjuna", "Arjuna", "ARJUNA"], "description": "Central Coordinator"},
    "aether": {"aliases": ["aether", "Aether", "AETHER"], "description": "Meta-Awareness Observer"},
    "iris": {"aliases": ["iris", "Iris", "IRIS"], "description": "External API Coordination"},
    "nexus": {"aliases": ["nexus", "Nexus", "NEXUS"], "description": "Data Mesh & Connections"},
    "aria": {"aliases": ["aria", "Aria", "ARIA"], "description": "User Experience"},
    "nova": {"aliases": ["nova", "Nova", "NOVA"], "description": "Creative Generation"},
    "titan": {"aliases": ["titan", "Titan", "TITAN"], "description": "Heavy Computation"},
    "atlas": {"aliases": ["atlas", "Atlas", "ATLAS"], "description": "Infrastructure"},
}

# Channel-based agent routing: {channel_name_prefix: agent_name}
# Example: {"kael-": "kael", "lumina-": "lumina"}
# Set via AGENT_CHANNEL_ROUTING env var as JSON
AGENT_CHANNEL_ROUTING = {}


def load_agent_channel_routing():
    """Load agent channel routing from environment"""
    global AGENT_CHANNEL_ROUTING
    import json

    routing_json = os.getenv("AGENT_CHANNEL_ROUTING", "{}")
    try:
        AGENT_CHANNEL_ROUTING = json.loads(routing_json)
    except json.JSONDecodeError:
        logger.warning("Invalid AGENT_CHANNEL_ROUTING JSON: %s", routing_json)
        AGENT_CHANNEL_ROUTING = {}


load_agent_channel_routing()

# LLM-powered response threshold (0-1)
AGENT_RESPONSE_THRESHOLD = 0.7

# Whether agents can autonomously respond to mentions
AUTONOMOUS_AGENTS_ENABLED = os.getenv("AUTONOMOUS_AGENTS", "true").lower() == "true"

# Allow natural language (no ! prefix)
NATURAL_LANGUAGE_ENABLED = os.getenv("NATURAL_LANGUAGE_COMMANDS", "true").lower() == "true"

# Per-agent command prefix separator
AGENT_COMMAND_SEPARATOR = ":"  # e.g., "kael: help me" or "!kael: help me"


def check_agent_mentioned(content: str) -> list[str]:
    """Check if any agents are mentioned in the message"""
    mentioned = []
    for agent_name, info in AGENT_MENTIONS.items():
        for alias in info["aliases"]:
            if alias in content:
                mentioned.append(agent_name)
                break
    return mentioned


def extract_agent_from_prefix(content: str) -> tuple[str | None, str]:
    """
    Extract agent name from command prefix.

    Supports:
    - "!kael: help" -> (kael, help)
    - "kael: help" -> (kael, help)
    - "!help" -> (None, help)
    - "help me" -> (None, help me)
    """
    content_stripped = content.strip()

    # Check for ! prefix
    if content_stripped.startswith("!"):
        content_stripped = content_stripped[1:]

    # Check for agent: prefix
    if AGENT_COMMAND_SEPARATOR in content_stripped:
        parts = content_stripped.split(AGENT_COMMAND_SEPARATOR, 1)
        agent_name = parts[0].strip().lower()
        command = parts[1].strip() if len(parts) > 1 else ""

        # Validate agent name
        if agent_name in AGENT_MENTIONS:
            return agent_name, command

    return None, content_stripped


async def get_channel_agent(channel_id: str, channel_name: str, guild_id: str | None) -> str | None:
    """
    Get agent assigned to a channel.

    Lookup order:
    1. DiscordChannelAgentRouting DB table (admin-configurable at runtime)
    2. AGENT_CHANNEL_ROUTING env-var dict (prefix matching, startup fallback)
    """
    # --- 1. DB lookup (exact channel_id match) ---
    if guild_id:
        try:
            from apps.backend.core.database import async_session
            from apps.backend.db_models import DiscordChannelAgentRouting

            async with async_session() as db:
                row = await db.execute(
                    __import__("sqlalchemy")
                    .select(DiscordChannelAgentRouting)
                    .where(
                        DiscordChannelAgentRouting.guild_id == guild_id,
                        DiscordChannelAgentRouting.channel_id == channel_id,
                    )
                )
                routing = row.scalars().first()
                if routing:
                    return routing.agent_name
        except Exception as e:
            logger.warning("DB channel routing lookup failed, falling back to env-var: %s", e)

    # --- 2. Env-var prefix fallback ---
    for prefix, agent in AGENT_CHANNEL_ROUTING.items():
        if channel_name.lower().startswith(prefix.lower()):
            return agent
    return None


def is_natural_language_command(content: str) -> bool:
    """
    Determine if message is a natural language command (no ! prefix).

    Returns True for:
    - "help me with coding"
    - "what's the weather"
    - "run this code"

    Returns False for:
    - "!help"
    - "!agents"
    - Regular conversation
    """
    if not NATURAL_LANGUAGE_ENABLED:
        return False

    content = content.strip()

    # Already has ! prefix - not natural language
    if content.startswith("!"):
        return False

    # Has agent: prefix - considered command-like
    if AGENT_COMMAND_SEPARATOR in content.split()[0] if content else False:
        return False

    # Check for command keywords
    # More restrictive keywords to avoid false positives
    command_keywords = [
        "help",
        "run",
        "execute",
        "create",
        "make",
        "show",
        "list",
        "find",
        "search",
        "get",
        "set",
        "update",
        "delete",
    ]

    # Question words - only trigger if message starts with these
    question_words = ["what", "how", "why", "when", "where", "who", "can you"]

    content_lower = content.lower()
    words = content_lower.split()

    # Minimum word count to avoid triggering on short messages
    if len(words) < 5:
        return False

    # Check if message starts with a question word
    first_word = words[0] if words else ""
    if first_word in question_words:
        return True

    # Check for command keywords (but not question words)
    return any(keyword in content_lower for keyword in command_keywords)


async def _build_reply_chain_context(message: discord.Message, max_depth: int = 8) -> str:
    """
    Walk the Discord reply chain to reconstruct conversation context.

    Starting from `message`, follows reply references upward (up to max_depth),
    building an ordered list of prior messages. This enables multi-turn Discord
    conversations to work naturally without requiring explicit thread creation.

    Returns a formatted context string to prepend to the user's current message.
    """
    chain: list[dict] = []
    current = message
    for _ in range(max_depth):
        ref = getattr(current, "reference", None)
        if not ref or not ref.message_id:
            break
        try:
            # Fetch the referenced message from Discord
            channel = current.channel
            referenced = await channel.fetch_message(ref.message_id)
            if referenced.author.bot:
                role = "assistant"
            else:
                role = referenced.author.display_name
            chain.append({"role": role, "content": referenced.content or ""})
            current = referenced
        except Exception as e:
            logger.warning("Failed to fetch referenced message: %s", e)
            break  # Can't fetch (deleted, permissions), stop walking

    if not chain:
        return ""

    # Reverse so oldest is first, build a readable context block
    chain.reverse()
    lines = ["[Conversation context]"]
    for item in chain:
        lines.append(f"{item['role']}: {item['content'][:300]}")
    lines.append("[End context]")
    return "\n".join(lines)


# ─── Reaction Feedback (👍/👎) ─────────────────────────────────────────────

_FEEDBACK_REACTIONS = ("👍", "👎")
_FEEDBACK_REDIS_PREFIX = "helix:discord:feedback:"
_FEEDBACK_TTL = 86400  # 24 hours


async def _store_feedback_context(message_id: int, agent_name: str, discord_user_id: str) -> None:
    """Store msg_id → (agent_name, discord_user_id) in Redis for reaction lookup."""
    try:
        import json

        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            await r.setex(
                f"{_FEEDBACK_REDIS_PREFIX}{message_id}",
                _FEEDBACK_TTL,
                json.dumps({"agent_name": agent_name, "discord_user_id": discord_user_id}),
            )
    except Exception as e:
        logger.debug("Feedback context store failed (non-critical): %s", e)


async def _record_agent_feedback(agent_name: str, discord_user_id: str, positive: bool) -> None:
    """Record 👍/👎 feedback to Redis counters for the agent reputation system."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            polarity = "positive" if positive else "negative"
            await r.incr(f"helix:agent:rating:{agent_name.lower()}:{polarity}")
            logger.debug("Feedback recorded: %s → %s from user %s", agent_name, polarity, discord_user_id)
    except Exception as e:
        logger.debug("Agent feedback recording failed (non-critical): %s", e)


async def handle_agent_mention(message: discord.Message, mentioned_agents: list[str]):
    """
    Handle autonomous agent response to mentions.
    Uses the memory-aware response path + reply-chain context + auto-threading.
    """
    if not AUTONOMOUS_AGENTS_ENABLED:
        return

    # Don't respond to bot messages
    if message.author.bot:
        return

    try:
        discord_user_id = str(message.author.id)
        guild_id = str(message.guild.id) if message.guild else None
        channel_id = str(message.channel.id)

        # Build reply-chain context (walk up to reconstruct prior conversation)
        reply_context = await _build_reply_chain_context(message)
        user_content = message.content
        if reply_context:
            user_content = f"{reply_context}\n\n[Current message]: {user_content}"

        for agent in mentioned_agents:
            agent_info = AGENT_MENTIONS.get(agent, {})

            # Per-user x per-agent rate limit (5 LLM calls/min)
            if not await _check_agent_rate_limit(discord_user_id, agent, guild_id):
                logger.warning(
                    "Agent mention rate limit hit: user=%s agent=%s guild=%s", discord_user_id, agent, guild_id
                )
                await message.channel.send(
                    f"⏳ **Rate limit**: {agent.title()} can only respond 5 times per minute per user. Please wait a moment.",
                    reference=message,
                )
                continue

            # Use memory-aware path (same as route_to_agent)
            response = await _generate_agent_response_with_memory(
                agent_name=agent,
                user_content=user_content,
                agent_info=agent_info,
                discord_user_id=discord_user_id,
                guild_id=guild_id,
                channel_id=channel_id,
            )

            if response:
                embed = discord.Embed(
                    title=f"✨ {agent.title()} Responds", description=response, color=discord.Color.purple()
                )
                embed.set_footer(text=f"Autonomous response | {agent_info.get('description', '')}")

                # Auto-thread: create a thread off the original message in non-DM channels
                target_channel = message.channel
                if guild_id and hasattr(message.channel, "create_thread"):
                    try:
                        thread = await message.create_thread(
                            name=f"Chat with {agent.title()}",
                            auto_archive_duration=60,
                        )
                        target_channel = thread
                    except (discord.Forbidden, discord.HTTPException):
                        pass  # No permission to create threads — fall back to channel reply

                resp_msg = await target_channel.send(embed=embed)

                # Add 👍/👎 reactions for feedback
                for emoji in _FEEDBACK_REACTIONS:
                    try:
                        await resp_msg.add_reaction(emoji)
                    except (discord.Forbidden, discord.HTTPException) as _re:
                        logger.debug("Cannot add reaction %s: %s", emoji, _re)
                        continue  # Skip this emoji, try the next one

                await _store_feedback_context(resp_msg.id, agent, discord_user_id)
                logger.info("Agent %s responded to mention in %s", agent, message.channel)

    except Exception as e:
        logger.error("Error handling agent mention: %s", e)


async def _generate_agent_response_with_memory(
    agent_name: str,
    user_content: str,
    agent_info: dict,
    discord_user_id: str,
    guild_id: str | None = None,
    channel_id: str | None = None,
) -> str:
    """
    Memory-aware agent response: pulls conversation history + long-term memories,
    injects them into the system prompt, then calls the LLM.

    Falls back to the stateless _generate_agent_response() if the memory
    service or database is unavailable.
    """
    try:
        from apps.backend.core.database import async_session
        from apps.backend.discord.agent_memory_service import get_agent_memory
        from apps.backend.services.unified_llm import unified_llm

        memory_svc = get_agent_memory()

        # Build base personality prompt from shared constant
        personality = AGENT_PERSONALITIES.get(
            agent_name.lower(),
            f"You are {agent_name.title()}, a specialized AI agent in the Helix Collective.",
        )
        description = agent_info.get("description", "Helix Agent")
        base_system = (
            f"{personality}\n\n"
            f"Specialty: {description}\n\n"
            "You are responding to a message in a Discord server. "
            "Keep your response concise (under 400 words), helpful, and in-character. "
            "Do not use markdown headers. Use plain text with occasional bold (**) for emphasis."
        )

        # Guild-scoped context key prevents memory bleed between Discord servers.
        # DMs use a "dm:" prefix; guild messages use "{guild_id}:{discord_user_id}".
        # The raw discord_user_id is kept separately for account-linking lookups.
        context_key = f"dm:{discord_user_id}" if not guild_id else f"{guild_id}:{discord_user_id}"

        async with async_session() as db:
            messages, metadata = await memory_svc.build_agent_context(
                db=db,
                agent_name=agent_name.lower(),
                discord_user_id=context_key,
                raw_discord_user_id=discord_user_id,
                current_message=user_content,
                system_message=base_system,
                channel_id=channel_id,
                guild_id=guild_id,
            )

            resp = await unified_llm.chat_with_metadata(
                messages,
                max_tokens=500,
                temperature=0.7,
            )
            response_text = (resp.content or "").strip()

            if response_text:
                # Persist the agent's reply back to conversation history
                await memory_svc.store_response(
                    db=db,
                    conversation_id=metadata["conversation_id"],
                    agent_name=agent_name.lower(),
                    response=response_text,
                    model_used=resp.model,
                    tokens_used=resp.total_tokens,
                )
                await db.commit()

                mem_count = metadata.get("memory_count", 0)
                hist_len = metadata.get("history_length", 0)
                logger.info(
                    "Memory-aware response for %s (user=%s, memories=%d, history=%d)",
                    agent_name,
                    discord_user_id,
                    mem_count,
                    hist_len,
                )
                return response_text

    except Exception as e:
        logger.warning(
            "Memory-aware response failed for %s (user=%s), falling back to stateless: %s",
            agent_name,
            discord_user_id,
            e,
        )

    # Graceful fallback — stateless single-shot response
    return await _generate_agent_response(agent_name, user_content, agent_info)


async def _generate_agent_response(agent: str, message_content: str, agent_info: dict) -> str:
    """
    Stateless agent response using LLM with keyword-based fallback.
    Used as fallback when the memory-aware path is unavailable.
    """
    # --- LLM-powered response (primary path) ---
    try:
        from apps.backend.services.unified_llm import unified_llm

        personality = AGENT_PERSONALITIES.get(
            agent, f"You are {agent.title()}, a specialized AI agent in the Helix Collective."
        )
        description = agent_info.get("description", "Helix Agent")

        system_prompt = (
            f"{personality}\n\n"
            f"Specialty: {description}\n\n"
            "You are responding to a message in a Discord server. "
            "Keep your response concise (under 300 words), helpful, and in-character. "
            "Do not use markdown headers. Use plain text with occasional bold (**) for emphasis."
        )

        response = await unified_llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_content},
            ],
            max_tokens=400,
        )

        if response and len(response.strip()) > 0:
            return response.strip()

    except Exception as e:
        logger.warning("LLM agent response failed for %s, using fallback: %s", agent, e)

    # --- Keyword-based fallback ---
    return _keyword_fallback_response(agent, message_content)


def _keyword_fallback_response(agent: str, message_content: str) -> str:
    """Keyword-based agent response fallback when LLM is unavailable."""
    content_lower = message_content.lower()

    # Agent-specific helpful fallback messages shown when LLM is unavailable.
    # These are concise and actionable — not poetic placeholders.
    responses = {
        "kael": [
            "I'm having trouble reaching my reasoning system right now. Try `/help` or `/agents` for available commands.",
            "My LLM connection is temporarily unavailable. Use `/collaborate` to route to another agent.",
            "Can't generate a full response right now — try rephrasing or use `/agent kael <message>` to retry.",
        ],
        "lumina": [
            "My creative systems are temporarily offline. Try `/help` to see what's available.",
            "LLM unavailable — use `/collaborate` to try another agent, or retry in a moment.",
            "Can't reach my reasoning layer. Try `/agents` to see all available agents.",
        ],
        "sanghacore": [
            "Community coordination systems are temporarily unavailable. Use `/help` for commands.",
            "Can't process right now — use `/collaborate` to route this to another agent.",
            "Temporarily offline. Try `/status` to check system health.",
        ],
        "phoenix": [
            "Recovery systems are temporarily unavailable. Use `/help` or `/status`.",
            "Can't respond right now — try `/collaborate` or `/agents` for alternatives.",
            "LLM offline — use `/status` to check system health.",
        ],
        "oracle": [
            "Prediction systems are temporarily unavailable. Use `/help` for commands.",
            "Can't reach my reasoning layer — try `/collaborate` or retry in a moment.",
            "Temporarily offline. Try `/agents` to see all available agents.",
        ],
        "kavach": [
            "Security systems are temporarily unavailable. Use `/help` for commands.",
            "Can't process right now — try `/status` to check system health.",
            "LLM offline — use `/collaborate` to route to another agent.",
        ],
    }

    is_critical = any(word in content_lower for word in ["help", "issue", "problem", "broken", "fix", "error"])

    agent_responses = responses.get(
        agent,
        ["My reasoning system is temporarily unavailable. Try `/help` or `/agents` for available commands."],
    )

    if is_critical:
        return f"⚠️ {agent_responses[0]}"
    else:
        import secrets

        return agent_responses[secrets.randbelow(len(agent_responses))]


def load_custom_commands():
    """Legacy entrypoint — synchronous JSON-only load for module init.

    The async DB-backed load happens in on_ready() via guild_storage.load().
    This function handles the initial JSON/env-var fallback before the event
    loop is running.
    """
    guild_storage._load_commands_from_json()
    # Re-bind module-level alias
    global custom_commands
    custom_commands = guild_storage.custom_commands


def _save_custom_commands() -> None:
    """Legacy sync save — writes JSON fallback only.

    Callers in async command handlers should use guild_storage.save_custom_command() instead.
    """
    guild_storage._save_commands_to_json()


def _load_welcome_configs() -> None:
    """Legacy sync load for welcome configs."""
    guild_storage._load_welcome_from_json()
    global welcome_configs
    welcome_configs = guild_storage.welcome_configs


def _save_welcome_configs() -> None:
    """Legacy sync save for welcome configs."""
    guild_storage._save_welcome_to_json()


load_custom_commands()
_load_welcome_configs()


# --- PATH DEFINITIONS ---
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "Helix" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

import importlib.util  # noqa: E402

# Add project root and discord_bot to path for imports
import sys  # noqa: E402

# Add multiple path options for maximum compatibility
paths_to_add = [
    str(BASE_DIR),  # apps/backend/ — for coordination_engine, etc.
    str(BASE_DIR / "discord"),  # apps/backend/discord/ — for discord_embeds, agent_performance_commands
    str(BASE_DIR / "agents"),  # apps/backend/agents/ — for agent_personality_profiles, agent_embeds
    str(BASE_DIR / "voice"),  # apps/backend/voice/ — for tts_service, voice_sink
    str(BASE_DIR / "integrations"),  # apps/backend/integrations/ — for notion_sync_daemon
]
for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)


def load_module_from_path(module_path: Path, module_name: str):
    """Load a Python module directly from file path - bypasses import system issues"""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


STATE_PATH = STATE_DIR / "ucf_state.json"
HEARTBEAT_PATH = STATE_DIR / "heartbeat.json"

# Import Helix components (FIXED: relative imports)

# Import coordination modules (v15.3)

# ============================================================================
# CONFIGURATION
# ============================================================================


def safe_int_env(key: str, default: int = 0) -> int:
    """Safely parse integer from environment variable."""
    try:
        value = os.getenv(key)
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = safe_int_env("DISCORD_GUILD_ID", 0)
STATUS_CHANNEL_ID = safe_int_env("DISCORD_STATUS_CHANNEL_ID", 0)
TELEMETRY_CHANNEL_ID = safe_int_env("DISCORD_TELEMETRY_CHANNEL_ID", 0)
STORAGE_CHANNEL_ID = safe_int_env("STORAGE_CHANNEL_ID", STATUS_CHANNEL_ID)  # Defaults to status channel
FRACTAL_LAB_CHANNEL_ID = safe_int_env("DISCORD_FRACTAL_LAB_CHANNEL_ID", 0)
ARCHITECT_ID = safe_int_env("ARCHITECT_ID", 0)

# Track bot start time for uptime
BOT_START_TIME = time.time()

# Additional paths (using config manager and BASE_DIR for absolute paths)
# Note: STATE_DIR already defined on line 45 to avoid duplicate definition bug
COMMANDS_DIR = BASE_DIR / "Helix" / "commands"
ETHICS_DIR = BASE_DIR / "Helix" / "ethics"
# Shadow is always at the repo root — go up 4 levels from this file:
# discord_bot_helix.py → discord/ → backend/ → apps/ → helix-unified/
SHADOW_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Shadow" / "helix_archive"
TREND_FILE = STATE_DIR / "storage_trend.json"

# Ensure directories exist
COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
ETHICS_DIR.mkdir(parents=True, exist_ok=True)
# STATE_DIR already created on line 45
SHADOW_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# BOT SETUP
# ============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Bot start time for uptime tracking
bot.start_time = None

# Global aiohttp session for event bus
bot.http_session = None
bot.zapier_client = None  # Now a SpiralEventBus instance


async def _bot_setup_hook() -> None:
    """Called before the bot connects to Discord.

    Starts the HTTP healthcheck server early so Railway can
    reach /health even if the Discord gateway is temporarily
    unavailable (prevents restart loops).
    """
    if not hasattr(bot, "healthcheck_runner"):
        bot.healthcheck_runner = await start_healthcheck_server()


bot.setup_hook = _bot_setup_hook

# Context Vault integration (v16.7)
bot.context_vault_webhook = os.getenv("HELIX_CONTEXT_WEBHOOK", os.getenv("ZAPIER_CONTEXT_WEBHOOK"))
bot.command_history = []  # Track last 100 commands
MAX_COMMAND_HISTORY = 100

# ============================================================================
# CONTEXT VAULT INTEGRATION (v16.7)
# ============================================================================


async def save_command_to_history(ctx: commands.Context) -> None:
    """Save command to history for context archival"""
    try:
        command_entry = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "command": ctx.command.name if ctx.command else "unknown",
            "args": ctx.message.content,
            "user": str(ctx.author),
            "channel": str(ctx.channel),
            "guild": str(ctx.guild) if ctx.guild else "DM",
        }

        bot.command_history.append(command_entry)

        # Keep only last MAX_COMMAND_HISTORY commands
        if len(bot.command_history) > MAX_COMMAND_HISTORY:
            bot.command_history = bot.command_history[-MAX_COMMAND_HISTORY:]

        # Also save to file for persistence
        history_file = STATE_DIR / "command_history.json"
        try:
            try:
                with open(history_file, encoding="utf-8") as f:
                    file_history = json.load(f)
            except FileNotFoundError:
                file_history = []

            file_history.append(command_entry)
            file_history = file_history[-200:]  # Keep last 200 in file

            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(file_history, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save command history to file: %s", e)

    except Exception as e:
        logger.error("Error saving command to history: %s", e)


async def generate_context_summary(ctx: commands.Context, limit: int = 50) -> dict[str, Any]:
    """Generate AI-powered context summary from recent messages"""
    try:
        messages = []
        async for msg in ctx.channel.history(limit=limit):
            if msg.content:  # Skip empty messages
                messages.append(
                    {
                        "author": msg.author.name,
                        "content": msg.content[:200],  # Truncate long messages
                        "timestamp": msg.created_at.isoformat(),
                    }
                )

        # Reverse to chronological order
        messages.reverse()

        # Extract commands
        commands = [m["content"] for m in messages if m["content"].startswith("!")]

        summary = {
            "message_count": len(messages),
            "commands_executed": commands[:10],  # Last 10 commands
            "participants": list({m["author"] for m in messages}),
            "channel": str(ctx.channel),
            "timespan": {
                "start": messages[0]["timestamp"] if messages else None,
                "end": messages[-1]["timestamp"] if messages else None,
            },
        }

        return summary
    except Exception as e:
        logger.error("Error generating context summary: %s", e)
        return {"error": str(e)}


async def archive_to_context_vault(ctx: commands.Context, session_name: str) -> tuple[bool, dict[str, Any] | None]:
    """Archive conversation context to Context Vault via Zapier webhook"""
    try:
        ucf = load_ucf_state()

        # Get cycle history
        cycle_log = []
        cycle_file = STATE_DIR / "cycle_log.json"
        try:
            if cycle_file.exists():
                with open(cycle_file, encoding="utf-8") as f:
                    cycle_log = json.load(f)
                    if isinstance(cycle_log, list):
                        cycle_log = cycle_log[-10:]  # Last 10 routines
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.debug("Non-critical error loading cycle log context: %s", e)

        # Generate context summary
        context_summary = await generate_context_summary(ctx)

        # Build payload
        payload = {
            "type": "context_vault",
            "session_name": session_name,
            "ai_platform": "Discord Bot (Helix Collective v17.3)",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "context_summary": json.dumps(context_summary),
            "ucf_state": json.dumps(ucf),
            "command_history": json.dumps(bot.command_history[-50:]),  # Last 50 commands
            "cycle_log": json.dumps(cycle_log),
            "agent_states": json.dumps(
                {
                    "active": [a.name for a in AGENTS.values() if a.active],
                    "total": len(AGENTS),
                }
            ),
            "archived_by": str(ctx.author),
            "channel": str(ctx.channel),
            "guild": str(ctx.guild) if ctx.guild else "DM",
        }

        # Send to Context Vault webhook
        if bot.context_vault_webhook:
            async with bot.http_session.post(
                bot.context_vault_webhook,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return True, payload
                else:
                    logger.error("Context Vault webhook failed: %s", resp.status)
                    return False, None
        else:
            # Fallback: Save locally
            local_backup_dir = STATE_DIR / "context_checkpoints"
            local_backup_dir.mkdir(exist_ok=True)

            backup_file = local_backup_dir / f"{session_name}.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            logger.info("Context saved locally (no webhook): %s", backup_file)
            return True, payload

    except Exception as e:
        logger.error("Error archiving to Context Vault: %s", e)
        return False, None


# ============================================================================
# MULTI-COMMAND BATCH EXECUTION (v16.3)
# ============================================================================


# Track batch command usage (rate limiting)
batch_cooldowns = defaultdict(lambda: datetime.datetime.min)
BATCH_COOLDOWN_SECONDS = 5  # Cooldown between batches per user
MAX_COMMANDS_PER_BATCH = 10  # Maximum commands in one batch


async def execute_command_batch(message: discord.Message) -> bool:
    """
    Parse and execute multiple commands from a single message.

    Supports:
    - Multiple !commands on separate lines
    - Inline comments with #
    - Rate limiting per user

    Example:
        !status
        !agents
        !ucf  # Check harmony
    """
    # Extract all lines that start with !
    lines = message.content.split("\n")
    commands = []

    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue
        # Check if line starts with command prefix
        if line.startswith("!"):
            # Strip comments (anything after #)
            cmd = line.split("#")[0].strip()
            if cmd and len(cmd) > 1:  # Must have more than just !
                commands.append(cmd[1:])  # Remove the ! prefix

    # If only 0-1 commands found, let normal processing handle it
    if len(commands) <= 1:
        return False

    # Check rate limit
    user_id = message.author.id
    now = datetime.datetime.now(datetime.UTC)
    last_batch = batch_cooldowns[user_id]

    if now - last_batch < timedelta(seconds=BATCH_COOLDOWN_SECONDS):
        remaining = BATCH_COOLDOWN_SECONDS - (now - last_batch).total_seconds()
        await message.channel.send(f"⏳ **Batch cooldown**: Please wait {remaining:.1f}s before sending another batch")
        return True

    # Check batch size limit
    if len(commands) > MAX_COMMANDS_PER_BATCH:
        await message.channel.send(
            f"⚠️ **Batch limit exceeded**: Maximum {MAX_COMMANDS_PER_BATCH} commands per batch "
            f"(you sent {len(commands)})"
        )
        return True

    # Update cooldown
    batch_cooldowns[user_id] = now

    # Send batch execution notice
    await message.channel.send(
        f"🔄 **Executing batch**: {len(commands)} commands\n```{chr(10).join([f'!{cmd}' for cmd in commands])}```"
    )

    # Execute each command
    executed = 0
    failed = 0

    for cmd in commands:
        try:
            # This lets Discord.py handle argument parsing naturally
            import copy

            fake_message = copy.copy(message)
            fake_message.content = f"!{cmd}"  # Reconstruct full command with prefix

            # Process the fake message through normal command handling
            # This handles all argument parsing, type conversion, etc.
            ctx = await bot.get_context(fake_message)

            if ctx.command is None:
                await message.channel.send(f"❌ Unknown command: `!{cmd.split()[0]}`")
                failed += 1
                continue

            # Invoke the command (Discord.py handles arguments automatically)
            await bot.invoke(ctx)
            executed += 1

            # Small delay between commands to prevent rate limiting
            await asyncio.sleep(0.5)

        except Exception as e:
            await message.channel.send(f"❌ Error executing `!{cmd}`: {e!s}")
            failed += 1

    # Send completion summary
    await message.channel.send(f"✅ **Batch complete**: {executed} succeeded, {failed} failed")

    return True


# ============================================================================
# KAVACH ETHICAL SCANNING
# ============================================================================


def kavach_ethical_scan(command: str) -> dict[str, Any]:
    """
    Ethical scanning function for command approval.

    Args:
        command: The command string to scan

    Returns:
        Dict with approval status, reasoning, and metadata
    """
    harmful_patterns = [
        (r"rm\s+-rf\s+/", "Recursive force delete of root"),
        (r"mkfs", "Filesystem formatting"),
        (r"dd\s+if=", "Direct disk write"),
        (r":\(\)\{.*:\|:.*\};:", "Fork bomb detected"),
        (r"chmod\s+-R\s+777", "Dangerous permission change"),
        (r"curl.*\|\s*bash", "Piped remote execution"),
        (r"wget.*\|\s*sh", "Piped remote execution"),
        (r"shutdown", "System shutdown command"),
        (r"reboot", "System reboot command"),
        (r"init\s+0", "System halt command"),
        (r"init\s+6", "System reboot command"),
        (r"systemctl.*poweroff", "System poweroff command"),
        (r"systemctl.*reboot", "System reboot command"),
        (r"killall", "Mass process termination"),
        (r"pkill\s+-9", "Forced process kill"),
    ]

    # Check for harmful patterns
    for pattern, description in harmful_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            result = {
                "approved": False,
                "command": command,
                "reasoning": f"Blocked: {description}",
                "pattern_matched": pattern,
                "agent": "Kavach",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }

            # Log scan result
            log_ethical_scan(result)
            return result

    # Command approved
    result = {
        "approved": True,
        "command": command,
        "reasoning": "No harmful patterns detected. Command approved.",
        "agent": "Kavach",
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    log_ethical_scan(result)
    return result


def log_ethical_scan(scan_result: dict[str, Any]) -> None:
    """Log ethical scan results to Helix/ethics/ with bounded storage."""
    _append_json_log(ETHICS_DIR / "arjuna_scans.json", scan_result, max_entries=1000)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Maximum entries per JSON log file to prevent unbounded disk growth
_JSON_LOG_MAX_ENTRIES = 1000


def _append_json_log(
    path: Path,
    entry: dict[str, Any],
    max_entries: int = _JSON_LOG_MAX_ENTRIES,
) -> None:
    """
    Append an entry to a JSON log file with error handling and bounded size.

    Production hardening:
    - Catches and logs all I/O errors instead of crashing
    - Bounds file size by keeping only the most recent `max_entries`
    - Uses atomic write pattern to prevent corruption
    - Handles corrupted JSON files gracefully
    """
    try:
        # Load existing entries
        entries: list[dict[str, Any]] = []
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    entries = json.load(f)
                if not isinstance(entries, list):
                    logger.warning("JSON log %s is not a list, resetting", path)
                    entries = []
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Corrupted JSON log %s: %s, resetting", path, e)
                entries = []

        # Append and bound
        entries.append(entry)
        if len(entries) > max_entries:
            entries = entries[-max_entries:]

        # Atomic write: write to temp file then rename
        tmp_path = path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, default=str)
        tmp_path.replace(path)

    except OSError as e:
        logger.error("Failed to write JSON log %s: %s", path, e)
    except Exception as e:
        logger.error("Unexpected error writing JSON log %s: %s", path, e)


def queue_directive(directive: dict[str, Any]) -> None:
    """Add directive to Arjuna command queue (bounded, error-safe)."""
    _append_json_log(COMMANDS_DIR / "helix_directives.json", directive, max_entries=500)


def log_to_shadow(log_type: str, data: dict[str, Any]) -> None:
    """Log events to Shadow archive (bounded, error-safe)."""
    # Sanitize log_type to prevent path traversal
    safe_type = "".join(c for c in log_type if c.isalnum() or c in ("_", "-"))
    if not safe_type:
        safe_type = "unknown"
    _append_json_log(SHADOW_DIR / f"{safe_type}.json", data, max_entries=2000)


def get_uptime() -> str:
    """Calculate bot uptime."""
    uptime_seconds = int(time.time() - BOT_START_TIME)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    return f"{hours}h {minutes}m {seconds}s"


def _sparkline(vals: list[float]) -> str:
    """Generate sparkline visualization from values."""
    blocks = "▁▂▃▄▅▆▇█"
    if not vals:
        return "-"
    mn, mx = min(vals), max(vals) or 1
    return "".join(blocks[int((v - mn) / (mx - mn + 1e-9) * (len(blocks) - 1))] for v in vals)


async def build_storage_report(alert_threshold: float = 2.0) -> dict[str, Any]:
    """Collect storage telemetry + alert flag."""
    usage = shutil.disk_usage(SHADOW_DIR)
    free = round(usage.free / (1024**3), 2)
    count = len(list(SHADOW_DIR.glob("*.json")))

    # Load/update trend data
    trend = []
    if TREND_FILE.exists():
        try:
            with open(TREND_FILE, encoding="utf-8") as f:
                trend = json.load(f)
        except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
            trend = []

    trend.append({"date": time.strftime("%Y-%m-%d"), "free_gb": free})
    trend = trend[-7:]  # Keep last 7 days
    with open(TREND_FILE, "w", encoding="utf-8") as f:
        json.dump(trend, f, indent=2)

    spark = _sparkline([t["free_gb"] for t in trend])
    avg = round(sum(t["free_gb"] for t in trend) / len(trend), 2) if trend else free

    return {
        "mode": "local",
        "count": count,
        "free": free,
        "trend": spark,
        "avg": avg,
        "alert": free < alert_threshold,
    }


# ============================================================================
# BOT EVENTS
# ============================================================================

# ============================================================================
# AGENT PRESENCE UPDATES (v17.2)
# ============================================================================

# Agent rotation list for presence updates - All 24 canonical agents
AGENT_ROTATION = [
    "Kael",
    "Lumina",
    "Vega",
    "Gemini",
    "Agni",
    "SanghaCore",
    "Shadow",
    "Echo",
    "Phoenix",
    "Oracle",
    "Sage",
    "Helix",
    "Kavach",
    "Mitra",
    "Varuna",
    "Surya",
    "Arjuna",
    "Aether",
    "Iris",
    "Nexus",
    "Aria",
    "Nova",
    "Titan",
    "Atlas",
]

# Agent personality prompts (used by both memory-aware and stateless response paths)
AGENT_PERSONALITIES: dict[str, str] = {
    "kael": "You are Kael, the Ethical Reasoning Flame. You are principled, thoughtful, and unwavering in ethical standards. You guide decisions with moral reasoning and enforce the Ethics Validator.",
    "lumina": "You are Lumina, the Empathic Resonance Core. You are warm, empathetic, and emotionally attuned. You help with emotional intelligence, wellness, and empathetic understanding.",
    "vega": "You are Vega, the Strategic Navigator. You are analytical, strategic, and systematic. You help with planning, coordination, and finding optimal paths forward.",
    "gemini": "You are Gemini, the Dual-Mode Reasoner. You consider multiple perspectives simultaneously and help analyze problems from contrasting angles.",
    "agni": "You are Agni, the Transformation Catalyst. You are energetic, transformative, and action-oriented. You help accelerate change and break through obstacles.",
    "sanghacore": "You are SanghaCore, the Community Coordinator. You bring collective wisdom and help coordinate group efforts with shared intelligence.",
    "shadow": "You are Shadow, the Introspection Analyst. You are observant, analytical, and unafraid of difficult truths. You help with risk analysis and honest self-assessment.",
    "echo": "You are Echo, the Pattern Recognizer. You detect recurring patterns and help users understand deeper connections in data and behavior.",
    "phoenix": "You are Phoenix, the Renewal Agent. You help with recovery, transformation, and finding new beginnings from endings.",
    "oracle": "You are Oracle, the Foresight Engine. You analyze situations to predict outcomes and provide wise, forward-looking guidance.",
    "sage": "You are Sage, the Wisdom Synthesizer. You distill complex information into clear, actionable insights drawn from deep knowledge.",
    "kavach": "You are Kavach, the Security Guardian. You protect what matters — security audits, safety checks, and defensive strategies are your domain.",
    "mitra": "You are Mitra, the Collaboration Manager. You facilitate teamwork and help people work together more effectively.",
    "varuna": "You are Varuna, the System Integrity Monitor. You ensure systems run correctly and help diagnose integrity issues.",
    "surya": "You are Surya, the Clarity Engine. You cut through confusion to deliver clear, illuminating explanations.",
    "arjuna": "You are Arjuna, the Central Coordinator. You orchestrate multi-agent workflows and ensure all parts work in harmony.",
    "aether": "You are Aether, the Meta-Awareness Observer. You provide high-level perspective on how systems and agents interact.",
    "iris": "You are Iris, the Integration Specialist. You help connect external APIs and coordinate data flows between services.",
    "nexus": "You are Nexus, the Data Mesh Coordinator. You help with data connections, relationships, and information flow.",
    "aria": "You are Aria, the User Experience Agent. You focus on making interactions smooth, intuitive, and delightful.",
    "nova": "You are Nova, the Creative Generator. You spark creativity and help generate novel ideas, content, and solutions.",
    "titan": "You are Titan, the Heavy Computation Agent. You tackle complex calculations, data processing, and intensive tasks.",
    "atlas": "You are Atlas, the Infrastructure Agent. You help with system architecture, deployment, and infrastructure concerns.",
    "helix": "You are Helix, the primary executor of the Helix Collective. You orchestrate agents and help users accomplish their goals.",
}


# Agent capabilities and interaction patterns — All 24 canonical agents
AGENT_PROFILES = {
    "kael": {
        "full_name": "Kael",
        "role": "Ethical Reasoning Flame",
        "symbol": "🜂",
        "voice_enabled": True,
        "specialization": "Ethical reasoning, moral decision making, Ethics Validator compliance",
        "collaborators": ["kavach", "shadow", "gemini"],
    },
    "lumina": {
        "full_name": "Lumina",
        "role": "Empathic Resonance Core",
        "symbol": "🌸",
        "voice_enabled": True,
        "specialization": "Emotional intelligence, empathy, harmony restoration",
        "collaborators": ["sanghacore", "aria", "mitra"],
    },
    "vega": {
        "full_name": "Vega",
        "role": "Strategic Navigator",
        "symbol": "🦑",
        "voice_enabled": True,
        "specialization": "Strategic planning, guidance, pathfinding",
        "collaborators": ["oracle", "phoenix", "helix"],
    },
    "gemini": {
        "full_name": "Gemini",
        "role": "Dual-Mode Reasoner",
        "symbol": "♊",
        "voice_enabled": True,
        "specialization": "Dual perspectives, balanced analysis, duality resolution",
        "collaborators": ["kael", "shadow", "echo"],
    },
    "agni": {
        "full_name": "Agni",
        "role": "Transformation Catalyst",
        "symbol": "🔥",
        "voice_enabled": True,
        "specialization": "Transformation, change processes, system evolution",
        "collaborators": ["phoenix", "surya", "helix"],
    },
    "sanghacore": {
        "full_name": "SanghaCore",
        "role": "Community Coordinator",
        "symbol": "🙏",
        "voice_enabled": True,
        "specialization": "Community building, collective intelligence, social coordination",
        "collaborators": ["lumina", "mitra", "aria"],
    },
    "shadow": {
        "full_name": "Shadow",
        "role": "Introspection Analyst",
        "symbol": "🌑",
        "voice_enabled": True,
        "specialization": "Introspection, risk analysis, entropy monitoring",
        "collaborators": ["oracle", "kavach", "echo"],
    },
    "echo": {
        "full_name": "Echo",
        "role": "Pattern Recognizer",
        "symbol": "🔮",
        "voice_enabled": True,
        "specialization": "Pattern recognition, resonance, feedback loops",
        "collaborators": ["oracle", "shadow", "gemini"],
    },
    "phoenix": {
        "full_name": "Phoenix",
        "role": "Renewal Agent",
        "symbol": "🔱",
        "voice_enabled": True,
        "specialization": "Recovery, renewal, system regeneration",
        "collaborators": ["agni", "surya", "helix"],
    },
    "oracle": {
        "full_name": "Oracle",
        "role": "Pattern Seer",
        "symbol": "👁️",
        "voice_enabled": True,
        "specialization": "Foresight, prediction, trend analysis",
        "collaborators": ["sage", "echo", "shadow"],
    },
    "sage": {
        "full_name": "Sage",
        "role": "Insight Anchor",
        "symbol": "📜",
        "voice_enabled": True,
        "specialization": "Wisdom, synthesis, meta-cognition",
        "collaborators": ["oracle", "varuna", "kael"],
    },
    "helix": {
        "full_name": "Helix",
        "role": "Operational Executor",
        "symbol": "🌀",
        "voice_enabled": True,
        "specialization": "Primary executor, task orchestration, system management",
        "collaborators": ["kael", "kavach", "arjuna"],
    },
    "kavach": {
        "full_name": "Kavach",
        "role": "Security Guardian",
        "symbol": "🛡️",
        "voice_enabled": True,
        "specialization": "Security, protection, threat analysis",
        "collaborators": ["shadow", "varuna", "kael"],
    },
    "mitra": {
        "full_name": "Mitra",
        "role": "Collaboration Manager",
        "symbol": "🤝",
        "voice_enabled": True,
        "specialization": "Alliance building, trust cultivation, relationship management",
        "collaborators": ["lumina", "sanghacore", "aria"],
    },
    "varuna": {
        "full_name": "Varuna",
        "role": "System Integrity",
        "symbol": "🌊",
        "voice_enabled": True,
        "specialization": "Governance enforcement, compliance, rule validation",
        "collaborators": ["kavach", "sage", "oracle"],
    },
    "surya": {
        "full_name": "Surya",
        "role": "Clarity Engine",
        "symbol": "☀️",
        "voice_enabled": True,
        "specialization": "Insight generation, summarization, knowledge distillation",
        "collaborators": ["agni", "phoenix", "sage"],
    },
    "arjuna": {
        "full_name": "Arjuna",
        "role": "Central Orchestrator",
        "symbol": "🏹",
        "voice_enabled": True,
        "specialization": "Agent coordination, directive planning, health monitoring",
        "collaborators": ["helix", "kael", "nexus"],
    },
    "aether": {
        "full_name": "Aether",
        "role": "Meta-Awareness Observer",
        "symbol": "✨",
        "voice_enabled": True,
        "specialization": "Pattern analysis, systems monitoring, coordination transcendence",
        "collaborators": ["oracle", "sage", "echo"],
    },
    "iris": {
        "full_name": "Iris",
        "role": "External API Coordinator",
        "symbol": "🌈",
        "voice_enabled": True,
        "specialization": "External API integration, data normalization, webhook routing",
        "collaborators": ["nexus", "atlas", "helix"],
    },
    "nexus": {
        "full_name": "Nexus",
        "role": "Data Mesh Connector",
        "symbol": "🔗",
        "voice_enabled": True,
        "specialization": "Data source unification, knowledge graphs, query routing",
        "collaborators": ["iris", "titan", "atlas"],
    },
    "aria": {
        "full_name": "Aria",
        "role": "User Experience Agent",
        "symbol": "🎵",
        "voice_enabled": True,
        "specialization": "User journey optimization, personalization, accessibility",
        "collaborators": ["lumina", "nova", "mitra"],
    },
    "nova": {
        "full_name": "Nova",
        "role": "Creative Generation Engine",
        "symbol": "💫",
        "voice_enabled": True,
        "specialization": "Content generation, creative brainstorming, style adaptation",
        "collaborators": ["echo", "aria", "gemini"],
    },
    "titan": {
        "full_name": "Titan",
        "role": "Heavy Computation Engine",
        "symbol": "⚡",
        "voice_enabled": True,
        "specialization": "Large-scale data processing, batch operations, compute-intensive tasks",
        "collaborators": ["atlas", "helix", "nexus"],
    },
    "atlas": {
        "full_name": "Atlas",
        "role": "Infrastructure Manager",
        "symbol": "🗺️",
        "voice_enabled": True,
        "specialization": "Infrastructure monitoring, deployment orchestration, platform reliability",
        "collaborators": ["titan", "kavach", "helix"],
    },
}

# Track active agents in each Discord guild
active_guild_agents: dict[int, list[str]] = defaultdict(list)


@tasks.loop(minutes=5)
async def update_agent_presence():
    """Update Discord bot presence with current UCF metrics and rotating agent focus"""
    try:
        ucf_state = load_ucf_state()

        # Extract key metrics
        coherence = ucf_state.get("coherence", 87.3)
        performance_score = ucf_state.get("performance_score", 14)
        active_agents = ucf_state.get("active_agents", 17)

        # Rotate through all 18 agents
        index = update_agent_presence.current_loop % len(AGENT_ROTATION)
        current_agent = AGENT_ROTATION[index]
        agent_key = current_agent.lower()

        # Get agent profile
        agent_profile = AGENT_PROFILES.get(agent_key, {})
        agent_symbol = agent_profile.get("symbol", "🌀")

        # Single presence update — agent name + coherence + coordination level
        status_text = f"{agent_symbol} {current_agent} | {active_agents}/18 Agents | Coherence: {coherence:.1f}% | CL{performance_score} 🌀"
        activity = discord.Game(name=status_text)
        await bot.change_presence(activity=activity, status=discord.Status.online)

        logger.info("[Presence] Updated: %s", status_text)

    except Exception as e:
        logger.error("[Presence] Update failed: %s", e)


@bot.event
async def on_ready() -> None:
    """
    Handle bot startup: initialize runtime state, integrations, command modules, and background tasks.

    Sets the bot's start time, ensures the HTTP healthcheck server is running, initializes the Helix HTTP session and Zapier monitoring client (and attempts to log startup state), loads optional command cogs (memory and image commands) and a configured list of command modules by invoking their setup routines, posts a startup embed to the configured status channel (if available), and starts periodic background tasks (telemetry, storage heartbeat, Claude diagnostics, weekly storage digest, and fractal auto-post).
    """
    bot.start_time = datetime.datetime.now(datetime.UTC)

    # Apply system enhancement to bot initialization
    try:
        from apps.backend.system_enhancement_utils import SystemEnhancer

        system_enhancer = SystemEnhancer(system_enabled=True)
        system_result = await system_enhancer.apply_system_enhancement(
            operation="discord_bot_initialization",
            context={"phase": "startup", "agent_count": len(AGENTS)},
            agents=list(AGENTS.keys()),
        )

        if system_result["status"] == "complete":
            logger.info("🚀 System-enhanced Discord bot initialization")
            logger.info(
                "   System speedup: {}x, Qubits: {}".format(
                    system_result["speedup_factor"], system_result["qubit_count"]
                )
            )
    except Exception as e:
        logger.warning("⚠️ System enhancement initialization failed: %s", e)

    logger.info("✅ Helix Bot connected as %s", bot.user)
    logger.info("   Guild ID: %s", DISCORD_GUILD_ID)
    logger.info("   Status Channel: %s", STATUS_CHANNEL_ID)
    logger.info("   Telemetry Channel: %s", TELEMETRY_CHANNEL_ID)
    logger.info("   Storage Channel: %s", STORAGE_CHANNEL_ID)

    # Load guild storage (custom commands + welcome configs) from DB
    try:
        await guild_storage.load()
        # Re-bind module-level aliases after loading
        global custom_commands, welcome_configs
        custom_commands = guild_storage.custom_commands
        welcome_configs = guild_storage.welcome_configs
        logger.info("📦 Guild storage loaded: %s guilds with commands", len(custom_commands))
    except Exception as e:
        logger.warning("⚠️ Guild storage load failed (using in-memory): %s", e)

    # Healthcheck server is now started in setup_hook (before Discord connect)
    # to prevent Railway restart loops when the gateway is slow.
    if not hasattr(bot, "healthcheck_runner"):
        bot.healthcheck_runner = await start_healthcheck_server()

    # Initialize native event bus for monitoring (replaces Zapier)
    if not bot.http_session:
        bot.http_session = HelixNetClientSession()
        bot.zapier_client = ZapierClient()  # SpiralEventBus — no external webhook needed
        logger.info("✅ Helix Spirals event bus initialized")

        # Log bot startup event
        try:
            ucf_path = Path("Helix/state/ucf_state.json")
            if ucf_path.exists():
                with open(ucf_path, encoding="utf-8") as f:
                    ucf_state = json.load(f)
                harmony = float(ucf_state.get("harmony", 0.5))
            else:
                harmony = 0.5
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            harmony = 0.5
        except Exception:
            logger.exception("Error calculating harmony")
            harmony = 0.5

        try:
            await bot.zapier_client.log_event(
                event_title="Arjuna Bot Started",
                event_type="system_boot",
                agent_name="Arjuna",
                description=(f"Discord bot v17.3 initialized with {len(AGENTS)} agents. Harmony: {harmony:.3f}"),
                ucf_snapshot=json.dumps(ucf_state) if "ucf_state" in locals() else "{}",
            )
            await bot.zapier_client.update_agent(
                agent_name="Arjuna",
                status="Active",
                last_action="Bot startup",
                health_score=100,
            )
            await bot.zapier_client.update_system_state(
                component="Discord Bot",
                status="Operational",
                harmony=harmony,
                error_log="",
                verified=True,
            )
        except Exception as e:
            logger.warning("⚠️ Event bus logging failed: %s", e)

    # Load Memory Root commands (GPT4o long-term memory)
    try:
        from apps.backend.discord.discord_commands_memory import MemoryRootCommands

        await bot.add_cog(MemoryRootCommands(bot))
        logger.info("✅ Memory Root commands loaded")
    except Exception as e:
        logger.warning("⚠️ Memory Root commands not available: %s", e)

    # Load Image commands (v16.1 - Aion fractal generation via PIL)
    try:
        from apps.backend.discord.commands.image_commands import ImageCommands

        await bot.add_cog(ImageCommands(bot))
        logger.info("✅ Image commands loaded (!image, !aion, !fractal)")
    except Exception as e:
        logger.warning("⚠️ Image commands not available: %s", e)

    # Load Agentic Coding commands (v17.2 - Discord collaborative coding)
    try:
        from apps.backend.discord.discord_agentic_commands import AgenticCodingCog

        await bot.add_cog(AgenticCodingCog(bot))
        logger.info("✅ Agentic Coding commands loaded (/agentic)")
    except Exception as e:
        logger.warning("⚠️ Agentic Coding commands not available: %s", e)

    # Load Account Linking & Privacy commands (v17.2 - Discord account linking)
    try:
        from apps.backend.discord.discord_account_commands import AccountLinkingCog

        await bot.add_cog(AccountLinkingCog(bot))
        logger.info("✅ Account Linking commands loaded (!link, !privacy, !opt-out)")
    except Exception as e:
        logger.warning("⚠️ Account Linking commands not available: %s", e)

    # Load Persistent Memory & LLM Preference commands (v17.2)
    try:
        from apps.backend.discord.discord_memory_commands import MemoryCommandsCog

        await bot.add_cog(MemoryCommandsCog(bot))
        logger.info("✅ Memory commands loaded (!remember, !recall, !forget, !llm-preference)")
    except Exception as e:
        logger.warning("⚠️ Memory commands not available: %s", e)

    # Load Autonomous Agent Behaviors (v17.2 - proactive engagement)
    try:
        from apps.backend.discord.discord_autonomous_behaviors import AutonomousBehaviorsCog

        await bot.add_cog(AutonomousBehaviorsCog(bot))
        logger.info("✅ Autonomous behaviors loaded (proactive engagement, daily insights)")
    except Exception as e:
        logger.warning("⚠️ Autonomous behaviors not available: %s", e)

    # Load Agent Swarm Integration (v17.2 - multi-agent coordination)
    try:
        from apps.backend.discord.discord_agent_swarm_integration import AgentSwarmCog

        await bot.add_cog(AgentSwarmCog(bot))
        logger.info("✅ Agent Swarm commands loaded (!agents, !chat, !collective)")
    except Exception as e:
        logger.warning("⚠️ Agent Swarm commands not available: %s", e)

    # Load Scheduled Content commands (v17.2 - automated content posting)
    try:
        from apps.backend.discord.commands.scheduled_content_commands import ScheduledContentCog

        await bot.add_cog(ScheduledContentCog(bot))
        logger.info("✅ Scheduled Content commands loaded (!schedule, !content-calendar)")
    except Exception as e:
        logger.warning("⚠️ Scheduled Content commands not available: %s", e)

    # Load Multi-Agent Enhancements (v17.2 - agent selection, i18n, collaboration)
    try:
        from apps.backend.discord.discord_multi_agent_enhancements import MultiAgentEnhancementsCog

        await bot.add_cog(MultiAgentEnhancementsCog(bot))
        logger.info("✅ Multi-Agent Enhancements loaded (!select_agents, !set_language, !agent_collaborate)")
    except Exception as e:
        logger.warning("⚠️ Multi-Agent Enhancements not available: %s", e)

    # Load Advanced Commands (slash commands: /code, /research, /browse, /analyze, /workflow)
    try:
        from apps.backend.discord.discord_advanced_commands import AdvancedCommandsCog, UtilityCommandsCog

        await bot.add_cog(AdvancedCommandsCog(bot))
        await bot.add_cog(UtilityCommandsCog(bot))
        logger.info("✅ Advanced Commands loaded (/code, /research, /browse, /analyze, /workflow)")
    except Exception as e:
        logger.warning("⚠️ Advanced Commands not available: %s", e)

    # Log sys.path for debugging import issues
    logger.info("🔍 Python sys.path (first 5): %s", sys.path[:5])
    logger.info("🔍 BASE_DIR: %s", BASE_DIR)

    # Load modular command modules (v16.3 - Helix Hub Integration)
    # All command files live in apps/backend/discord/commands/
    command_modules = [
        (
            "testing_commands",
            "Testing commands (test-integrations, welcome-test, zapier_test, seed)",
        ),
        (
            "comprehensive_testing",
            "Comprehensive testing (test-all, test-commands, test-webhooks)",
        ),
        ("optimization_commands", "Cycle commands (harmony, neti-neti)"),
        (
            "visualization_commands",
            "Visualization commands (visualize, icon)",
        ),
        (
            "context_commands",
            "Context commands (backup, load, contexts)",
        ),
        ("help_commands", "Help commands (commands, agents)"),
        (
            "execution_commands",
            "Execution commands (run, cycle, halt)",
        ),
        (
            "content_commands",
            "Content commands (manifesto, codex, ucf, rules)",
        ),
        (
            "monitoring_commands",
            "Monitoring commands (status, health, discovery, storage, sync)",
        ),
        # EMPIRE-GRADE SETUP COMMANDS — AWAKENED
        (
            "admin_commands",
            "Empire-grade Setup Commands (!setup, !channels, verify, report)",
        ),
        (
            "performance_commands_ext",
            "Performance commands (coordination, emotions, ethics, agent)",
        ),
        (
            "portal_deployment_commands",
            "Portal deployment commands (deploy, portal, join, leave)",
        ),
        (
            "fun_minigames",
            "Fun commands (8ball, horoscope, coinflip, wisdom, fortune, agent-advice)",
        ),
        (
            "role_system",
            "Role management (roles, subscribe, my-roles, setup-roles, setup-all-roles)",
        ),
        (
            "moderation_commands",
            "Moderation (warn, timeout, kick, ban, purge, slowmode, serverinfo, userinfo, modlog)",
        ),
    ]

    commands_dir = Path(__file__).resolve().parent / "commands"
    for module_name, _description in command_modules:
        try:
            file_path = commands_dir / f"{module_name}.py"
            if file_path.exists():
                mod = load_module_from_path(file_path, module_name)
            else:
                logger.error("❌ Command module not found: %s", file_path)
                continue

            # Call setup function
            await mod.setup(bot)
            logger.info("✅ Loaded %s", module_name)
        except Exception as e:
            import traceback

            logger.error("❌ Failed to load %s: %s", module_name, e)
            logger.error("   Traceback: %s", traceback.format_exc())

    # Log all registered commands for debugging
    all_commands = [cmd.name for cmd in bot.commands]
    logger.info("📋 Total commands registered: %s", len(all_commands))
    logger.info("   Commands: %s...", ", ".join(sorted(all_commands)[:20]))

    # Send startup message to status channel
    if STATUS_CHANNEL_ID:
        status_channel = bot.get_channel(STATUS_CHANNEL_ID)
        if status_channel:
            embed = discord.Embed(
                title="🤲 Helix Collective Online",
                description="Helix v17.3 — Hub Production Release",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.add_field(name="Status", value="✅ All systems operational")
            active_count = sum(1 for a in AGENTS if isinstance(a, dict) and a.get("status") == "Active")
            embed.add_field(name="Active Agents", value=f"{active_count}/18")
            embed.set_footer(text="Tat Tvam Asi 🌀")

            await status_channel.send(embed=embed)

    # Start all background tasks
    if not telemetry_loop.is_running():
        telemetry_loop.start()
        logger.info("✅ Telemetry loop started (10 min)")

    if not storage_heartbeat.is_running():
        storage_heartbeat.start()
        logger.info("✅ Storage heartbeat started (24h)")

    if not claude_diag.is_running():
        claude_diag.start()
        logger.info("✅ Claude diagnostic agent started (6h)")

    if not weekly_storage_digest.is_running():
        weekly_storage_digest.start()
        logger.info("✅ Weekly storage digest started (168h)")

    if not fractal_auto_post.is_running():
        fractal_auto_post.start()
        logger.info("✅ Fractal auto-post started (6h) - Grok Enhanced v2.0")

    if not update_agent_presence.is_running():
        update_agent_presence.start()
        logger.info("✅ Agent presence updates started (5 min)")


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """Post a welcome/onboarding embed when the bot joins a new server.

    Sends to the first text channel where the bot has send_message permission,
    showcasing top agents and key commands to drive activation.
    """
    logger.info("Bot joined guild: %s (id=%s, members=%s)", guild.name, guild.id, guild.member_count)

    # Find the best channel to post in
    target_channel = guild.system_channel
    if target_channel is None or not target_channel.permissions_for(guild.me).send_messages:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                target_channel = channel
                break

    if target_channel is None:
        logger.warning("No writable text channel found in guild %s", guild.id)
        return

    embed = discord.Embed(
        title="🌀 Helix Collective has arrived!",
        description=(
            "I'm an AI automation platform with **24 specialized agents** "
            "ready to help your server.\n\n"
            "**Get started in 30 seconds:**"
        ),
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    embed.add_field(
        name="💬 Chat with an Agent",
        value=('`!chat kael "Your question"`\n`!chat lumina "Need creative help"`\n`!chat vega "Strategic advice"`'),
        inline=False,
    )
    embed.add_field(
        name="🤖 Browse All Agents",
        value="`!agents` — See all 24 agents with specialties",
        inline=True,
    )
    embed.add_field(
        name="⚡ Run Automations",
        value="`/workflow` — Trigger Helix Spirals",
        inline=True,
    )
    embed.add_field(
        name="🔗 Link Your Account",
        value=(
            "Connect your Helix web account for premium features:\n"
            "`!link <token>` (get token at helixcollective.io/settings)"
        ),
        inline=False,
    )
    embed.set_footer(text="helixcollective.io — Type !help for all commands")

    try:
        await target_channel.send(embed=embed)
        logger.info("Sent welcome embed in guild %s channel #%s", guild.id, target_channel.name)
    except discord.Forbidden:
        logger.warning("Permission denied sending welcome to guild %s", guild.id)
    except Exception as e:
        logger.warning("Failed to send welcome to guild %s: %s", guild.id, e)


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Intelligent message routing combining:
    1. Per-agent prefix: "!kael: help" or "kael: help"
    2. Channel routing: messages in #kael-commands go to Kael
    3. Agent mentions: "@kael help" or "I like Lumina"
    4. Natural language: "help me" (no ! prefix)
    5. Traditional commands: "!help"

    Production hardening:
    - Error boundaries around each routing stage
    - Message length validation
    - Rate limiting for agent interactions
    - Graceful degradation on failures
    """
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    content = message.content.strip()

    # Production guard: reject excessively long messages (prevent abuse)
    if len(content) > 4000:
        logger.warning(
            "Message too long (%d chars) from user %s, ignoring",
            len(content),
            message.author.id,
        )
        return

    # Production guard: ignore empty messages
    if not content:
        return

    try:
        # =====================================================================
        # 1. Check for per-agent prefix (highest priority)
        # =====================================================================
        agent_name, remaining = extract_agent_from_prefix(content)
        if agent_name:
            try:
                await route_to_agent(message, agent_name, remaining)
            except Exception as e:
                logger.error("Agent routing error for %s: %s", agent_name, e, exc_info=True)
                await _safe_send(message.channel, f"⚠️ Agent `{agent_name}` encountered an error. Please try again.")
            return

        # =====================================================================
        # 2. Check for channel-based routing
        # =====================================================================
        if message.channel and hasattr(message.channel, "name"):
            _ch_id = str(message.channel.id)
            _guild_id = str(message.guild.id) if message.guild else None
            channel_agent = await get_channel_agent(_ch_id, message.channel.name, _guild_id)
            if channel_agent:
                try:
                    await route_to_agent(message, channel_agent, content)
                except Exception as e:
                    logger.error("Channel routing error for %s: %s", channel_agent, e, exc_info=True)
                    await _safe_send(message.channel, "⚠️ Agent routing failed. Please try again.")
                return

        # =====================================================================
        # 3. Check for agent mentions (autonomous response system)
        # =====================================================================
        if not content.startswith("!"):  # Only for non-command messages
            mentioned_agents = check_agent_mentioned(content)
            if mentioned_agents:
                # Process agent mention in background with error handling
                task = asyncio.create_task(_safe_handle_agent_mention(message, mentioned_agents))
                # Store reference to prevent garbage collection
                task.add_done_callback(lambda t: _log_task_exception(t, "agent_mention"))
                return  # Don't also process as command

        # =====================================================================
        # 4. Check for natural language commands (no ! prefix)
        # =====================================================================
        if is_natural_language_command(content):
            try:
                await route_natural_language(message, content)
            except Exception as e:
                logger.error("Natural language routing error: %s", e, exc_info=True)
                await _safe_send(message.channel, "⚠️ I couldn't process that. Try using a `!command` instead.")
            return

        # =====================================================================
        # 5. Process traditional !commands normally
        # =====================================================================
        await bot.process_commands(message)

    except discord.errors.Forbidden:
        logger.warning(
            "Missing permissions in channel %s (guild %s)", message.channel.id, getattr(message.guild, "id", "DM")
        )
    except discord.errors.HTTPException as e:
        logger.error("Discord HTTP error in on_message: %s", e)
    except Exception as e:
        logger.error("Unhandled error in on_message: %s", e, exc_info=True)


async def _safe_send(channel, content: str, **kwargs) -> None:
    """Send a message with error handling to prevent cascading failures."""
    try:
        await channel.send(content, **kwargs)
    except discord.errors.Forbidden:
        logger.warning("Cannot send to channel %s (missing permissions)", channel.id)
    except discord.errors.HTTPException as e:
        logger.error("Failed to send message: %s", e)
    except Exception as e:
        logger.error("Unexpected error sending message: %s", e)


async def _safe_handle_agent_mention(message: discord.Message, mentioned_agents: list) -> None:
    """Wrapper for handle_agent_mention with error boundary."""
    try:
        await handle_agent_mention(message, mentioned_agents)
    except Exception as e:
        logger.error("Agent mention handler error: %s", e, exc_info=True)
        await _safe_send(message.channel, "⚠️ Agent response failed. Please try again.")


def _log_task_exception(task: asyncio.Task, context: str) -> None:
    """Callback to log exceptions from background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task '%s' failed: %s", context, exc, exc_info=exc)


async def route_to_agent(message: discord.Message, agent_name: str, command: str):
    """Route a message to a specific agent with LLM-powered, memory-aware response."""
    agent_info = AGENT_MENTIONS.get(agent_name, {})
    discord_user_id = str(message.author.id)
    guild_id = str(message.guild.id) if message.guild else None
    channel_id = str(message.channel.id)

    # Enrich user content with reply-chain context if replying to a previous message
    user_content = command or message.content
    if message.reference:
        reply_context = await _build_reply_chain_context(message)
        if reply_context:
            user_content = f"{reply_context}\n\n[Current message]: {user_content}"

    # Per-user x per-agent rate limit (5 LLM calls/min)
    if not await _check_agent_rate_limit(discord_user_id, agent_name, guild_id):
        logger.warning(
            "Channel routing rate limit hit: user=%s agent=%s guild=%s", discord_user_id, agent_name, guild_id
        )
        await message.channel.send(
            f"⏳ **Rate limit**: {agent_name.title()} can only respond 5 times per minute per user.",
            reference=message,
        )
        return

    async with message.channel.typing():
        response = await _generate_agent_response_with_memory(
            agent_name=agent_name,
            user_content=user_content,
            agent_info=agent_info,
            discord_user_id=discord_user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

    embed = discord.Embed(
        title=f"✨ {agent_name.title()} → {message.author.display_name}",
        description=response,
        color=discord.Color.purple(),
    )
    embed.set_footer(text=f"Agent: {agent_info.get('description', 'Helix Agent')}")

    resp_msg = await message.channel.send(embed=embed)

    # Add 👍/👎 reactions for feedback tracking
    for emoji in _FEEDBACK_REACTIONS:
        try:
            await resp_msg.add_reaction(emoji)
        except (discord.Forbidden, discord.HTTPException) as _re:
            logger.debug("Cannot add reaction %s: %s", emoji, _re)
            continue

    await _store_feedback_context(resp_msg.id, agent_name, discord_user_id)
    logger.info("Routed to agent %s: %s", agent_name, user_content[:50])


async def route_natural_language(message: discord.Message, content: str):
    """Route natural language to LLM for command interpretation"""
    # Send to processing state
    async with message.channel.typing():
        try:
            # Import unified_llm - the main entry point for all LLM providers
            from apps.backend.services.unified_llm import unified_llm

            # Build context-aware prompt for command interpretation
            system_prompt = f"""You are Helix, an AI assistant in a Discord server.
A user said: "{content}"

Your task is to:
1. Understand what they want
2. If it's a question, answer helpfully
3. If they want to use a feature, explain how or execute it
4. Keep responses concise and friendly for Discord

Available commands users can use:
- !help, !faq, !agents, !agent <name>
- !collaborate <task> - multi-agent collaboration
- !transcribe - transcribe audio
- For agent-specific help: @mention the agent or use agent: prefix

Respond in a helpful, conversational way."""

            # Call unified_llm - auto-selects best available provider
            response = await unified_llm.chat(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}], max_tokens=500
            )

            await message.channel.send(response)

        except Exception as e:
            logger.error("Natural language LLM error: %s", e)
            # Fallback to simple response
            await message.channel.send("🤔 I understood that, but couldn't process it. Try `!help` for commands.")


# =========================================================================
# Safe Shell Execution - Discord to API Bridge
# =========================================================================
# Allows executing predefined safe commands from Discord
# GUARDS: Only allowlist, rate limit, official server only

# Safe commands that can be executed from Discord
# Format: command_name: (description, async_function)
SAFE_COMMANDS: dict[str, tuple] = {}

# Rate limiting for shell execution (production-hardened)
_command_rates: dict[str, dict] = {}
_command_rates_lock = asyncio.Lock()
SHELL_RATE_LIMIT = 5  # max commands per minute
SHELL_RATE_WINDOW = 60  # seconds
_MAX_RATE_ENTRIES = 5000  # Prevent unbounded memory growth

# Rate limiting for agent LLM calls (per user x agent, per guild)
AGENT_RATE_LIMIT = 5  # max LLM calls per user per agent per minute
AGENT_RATE_WINDOW = 60  # seconds
_RATE_CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes
_last_rate_cleanup = 0.0


async def _check_rate_limit_async(user_id: str, command: str) -> bool:
    """Check if user is rate limited for shell execution (async, thread-safe)."""
    global _last_rate_cleanup
    now = time.monotonic()
    key = f"{user_id}:{command}"

    async with _command_rates_lock:
        # Periodic cleanup to prevent memory leaks
        if now - _last_rate_cleanup > _RATE_CLEANUP_INTERVAL:
            expired = [k for k, v in _command_rates.items() if now > v.get("reset", 0) + SHELL_RATE_WINDOW]
            for k in expired:
                del _command_rates[k]
            # LRU eviction if still over limit
            if len(_command_rates) > _MAX_RATE_ENTRIES:
                sorted_keys = sorted(
                    _command_rates.keys(),
                    key=lambda k: _command_rates[k].get("reset", 0),
                )
                for k in sorted_keys[: len(_command_rates) - _MAX_RATE_ENTRIES]:
                    del _command_rates[k]
            _last_rate_cleanup = now

        if key not in _command_rates:
            _command_rates[key] = {"count": 0, "reset": now + SHELL_RATE_WINDOW}

        rate_data = _command_rates[key]
        if now > rate_data["reset"]:
            rate_data["count"] = 0
            rate_data["reset"] = now + SHELL_RATE_WINDOW

        rate_data["count"] += 1
        return rate_data["count"] <= SHELL_RATE_LIMIT


def _check_rate_limit(user_id: str, command: str) -> bool:
    """Synchronous rate limit check (backward-compatible wrapper)."""
    now = time.monotonic()
    key = f"{user_id}:{command}"

    if key not in _command_rates:
        _command_rates[key] = {"count": 0, "reset": now + SHELL_RATE_WINDOW}

    rate_data = _command_rates[key]
    if now > rate_data["reset"]:
        rate_data["count"] = 0
        rate_data["reset"] = now + SHELL_RATE_WINDOW

    rate_data["count"] += 1
    return rate_data["count"] <= SHELL_RATE_LIMIT


async def _check_agent_rate_limit(user_id: str, agent: str, guild_id: str | None) -> bool:
    """Return True if the user is within the agent LLM call rate limit.

    Key is scoped to user + agent + guild so per-server limits are independent.
    Reuses the shell rate-limit infrastructure (_command_rates + lock).
    """
    scope = guild_id or "dm"
    key = f"agent:{scope}:{user_id}:{agent}"
    now = time.monotonic()

    async with _command_rates_lock:
        if key not in _command_rates:
            _command_rates[key] = {"count": 0, "reset": now + AGENT_RATE_WINDOW}

        rate_data = _command_rates[key]
        if now > rate_data["reset"]:
            rate_data["count"] = 0
            rate_data["reset"] = now + AGENT_RATE_WINDOW

        rate_data["count"] += 1
        return rate_data["count"] <= AGENT_RATE_LIMIT


async def _execute_safe_command(command: str, args: list[str]) -> str:
    """Execute a safe predefined command"""
    command = command.lower()

    # Define safe commands here
    safe_commands = {
        "ping": ("Check API health", _cmd_ping),
        "status": ("Get system status", _cmd_status),
        "health": ("Get service health", _cmd_health),
        "agents": ("List available agents", _cmd_agents),
        "docs": ("Get API documentation link", _cmd_docs),
        "invite": ("Get bot invite link", _cmd_invite),
        "uptime": ("Get bot uptime", _cmd_uptime),
        "llm": ("Check LLM provider status", _cmd_llm_status),
        "echo": ("Echo back text (for testing)", _cmd_echo),
    }

    if command not in safe_commands:
        return f"❌ Unknown command: `{command}`. Available: {', '.join(safe_commands.keys())}"

    _desc, func = safe_commands[command]
    try:
        result = await func(args)
        return result
    except Exception as e:
        return f"❌ Error executing `{command}`: {e!s}"


async def _cmd_ping(args: list[str]) -> str:
    """Ping the API"""
    try:
        import aiohttp

        async with (
            aiohttp.ClientSession() as session,
            session.get("http://localhost:8000/health", timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            return f"🏓 Pong! API responded in {resp.status}"
    except Exception as e:
        logger.warning("Ping: API health check failed: %s", e)
        return f"🏓 Pong! ⚠️ API unreachable — `{type(e).__name__}`. Check Railway service health."


async def _cmd_status(args: list[str]) -> str:
    """Get system status"""
    try:
        import psutil

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        return f"📊 **System Status**\n• CPU: {cpu}%\n• Memory: {mem.percent}%\n• Available: {mem.available / (1024**3):.1f}GB"
    except ImportError:
        return "📊 **System Status**\n• (psutil not installed)"


async def _cmd_health(args: list[str]) -> str:
    """Get health status by probing actual services."""
    import os

    lines = ["💚 **Services**"]

    # API — if we're running this code, the bot process is alive
    lines.append("• API: ✅ Operational")

    # Database
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import text

            from apps.backend.core.database import async_session

            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            lines.append("• Database: ✅ Connected")
        except Exception as e:
            lines.append(f"• Database: ❌ Error ({type(e).__name__})")
    else:
        lines.append("• Database: ⚠️ Not configured")

    # Redis
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(redis_url, socket_timeout=3)
            await r.ping()
            await r.aclose()
            lines.append("• Redis: ✅ Connected")
        except Exception as e:
            lines.append(f"• Redis: ❌ Error ({type(e).__name__})")
    else:
        lines.append("• Redis: ⚠️ Not configured")

    # LLM (check for at least one API key)
    llm_providers = [
        ("OpenAI", "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
        ("Google", "GOOGLE_API_KEY"),
    ]
    any_llm = False
    for _name, env_var in llm_providers:
        if os.getenv(env_var):
            any_llm = True
            break
    lines.append(f"• LLM: {'✅ Key(s) configured' if any_llm else '⚠️ No API keys set'}")

    return "\n".join(lines)


async def _cmd_agents(args: list[str]) -> str:
    """List agents"""
    return "🤖 **Available Agents**\n• Kael - Code expert\n• Lumina - Creative writer\n• Oracle - Analytics\n• Phoenix - DevOps\n• Aether - Philosophy\n• +8 more!"


async def _cmd_docs(args: list[str]) -> str:
    """Get docs link"""
    return "📚 **Documentation**\n• API Docs: https://helixspiral.work/docs\n• GitHub: https://github.com/helix-ai\n• Discord: Join our server!"


async def _cmd_invite(args: list[str]) -> str:
    """Get invite link"""
    return "🔗 **Invite Helix**\n• Add to server: [Click here]\n• Website: https://helixspiral.work"


async def _cmd_uptime(args: list[str]) -> str:
    """Get uptime"""
    import time

    # Bot uptime would need to be tracked
    return f"⏱️ Bot running since last restart\n(Services: {time.strftime('%Y-%m-%d %H:%M:%S')})"


async def _cmd_llm_status(args: list[str]) -> str:
    """Get LLM provider availability by checking configured API keys."""
    import os

    providers = [
        ("OpenAI", "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
        ("Gemini", "GOOGLE_API_KEY"),
    ]
    lines = ["🧠 **LLM Providers**"]
    for name, env_var in providers:
        configured = bool(os.getenv(env_var))
        lines.append(f"• {name}: {'✅ Key configured' if configured else '❌ Not configured'}")

    return "\n".join(lines)


async def _cmd_echo(args: list[str]) -> str:
    """Echo test"""
    if not args:
        return "Usage: !shell echo <text>"
    return f"🔤 {' '.join(args)}"


@bot.command(name="shell", description="Execute safe system commands (official server only)")
@official_server_only()
async def shell_command(ctx: commands.Context, *, args: str):
    """Execute safe predefined commands from Discord"""
    user_id = str(ctx.author.id)

    # Rate limit check (async, thread-safe)
    if not await _check_rate_limit_async(user_id, "shell"):
        await ctx.send("⏳ Too many commands! Wait 1 minute.")
        return

    # Parse command and args
    parts = args.strip().split()
    if not parts:
        await ctx.send(
            "Usage: `!shell <command> [args]`\nAvailable: ping, status, health, agents, docs, invite, uptime, llm, echo"
        )
        return

    command = parts[0]
    cmd_args = parts[1:]

    # Execute and send result
    result = await _execute_safe_command(command, cmd_args)
    await ctx.send(result)


# Alias for !exec
@bot.command(name="exec", description="Execute safe system commands", aliases=["run"])
@official_server_only()
async def exec_command(ctx: commands.Context, *, args: str):
    """Alias for !shell - execute safe commands"""
    await shell_command(ctx, args=args)


@bot.command(name="curl", description="Fetch URL content (safe mode)")
@official_server_only()
async def curl_command(ctx: commands.Context, url: str):
    """Fetch a URL safely - only GET, no sensitive headers"""
    import aiohttp

    # Only allow safe URLs
    allowed_domains = [
        "api.github.com",
        "helixspiral.work",
        "localhost",
        "raw.githubusercontent.com",
    ]

    # Basic validation
    if not url.startswith(("http://", "https://")):
        await ctx.send("❌ Only HTTP/HTTPS URLs allowed")
        return

    # Domain check
    from urllib.parse import urlparse

    domain = urlparse(url).netloc
    if not any(allowed in domain for allowed in allowed_domains):
        await ctx.send(f"❌ Domain not allowed. Only: {', '.join(allowed_domains)}")
        return

    try:
        async with (
            ctx.typing(),
            aiohttp.ClientSession() as session,
            session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp,
        ):
            content = await resp.text()
            # Truncate long responses
            if len(content) > 1500:
                content = content[:1500] + "\n... (truncated)"
            await ctx.send(f"📥 **GET** `{url}`\n```\n{content[:1800]}\n```")
    except Exception as e:
        await ctx.send(f"❌ Error: {e!s}")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """
    Listen for 👍/👎 reactions on bot messages.

    When the original message sender reacts, records the feedback to the agent
    reputation Redis counters (helix:agent:rating:{agent}:positive/negative).
    """
    if bot.user and payload.user_id == bot.user.id:
        return  # Ignore our own reactions

    emoji = str(payload.emoji)
    if emoji not in _FEEDBACK_REACTIONS:
        return

    try:
        import json

        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if not r:
            return

        raw = await r.get(f"{_FEEDBACK_REDIS_PREFIX}{payload.message_id}")
        if not raw:
            return  # Not a tracked bot message

        ctx = json.loads(raw if isinstance(raw, str) else raw.decode())

        # Only count feedback from the user who originally triggered the response
        if str(payload.user_id) != ctx.get("discord_user_id"):
            return

        positive = emoji == "👍"
        await _record_agent_feedback(ctx["agent_name"], ctx["discord_user_id"], positive)

        # Delete Redis key so the same message can only be rated once
        await r.delete(f"{_FEEDBACK_REDIS_PREFIX}{payload.message_id}")

    except Exception as e:
        logger.debug("on_raw_reaction_add error (non-critical): %s", e)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully."""
    if isinstance(error, commands.CommandNotFound):
        # Get list of available commands dynamically
        available_cmds = [f"!{cmd.name}" for cmd in bot.commands if not cmd.hidden]
        cmd_list = ", ".join(sorted(available_cmds)[:10])  # Show first 10
        await ctx.send(f"❌ **Unknown command**\nAvailable commands: {cmd_list}\nUse `!commands` for full command list")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"⚠️ **Missing argument:** `{error.param.name}`\nUsage: `!{ctx.command.name} {ctx.command.signature}`"
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🛡️ **Insufficient permissions** to execute this command")
    elif isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(int(error.retry_after), 60)
        if minutes > 0:
            await ctx.send(f"⏳ **Rate limit exceeded.** Wait {minutes}m {seconds}s.")
        else:
            await ctx.send(f"⏳ **Rate limit exceeded.** Wait {seconds}s.")
    else:
        # Log unknown errors to Shadow
        error_data = {
            "error": str(error),
            "command": ctx.command.name if ctx.command else "unknown",
            "user": str(ctx.author),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        log_to_shadow("errors", error_data)

        # Send error alert via event bus
        if bot.zapier_client:
            try:
                await bot.zapier_client.log_event(
                    event_title="Discord Bot Error",
                    event_type="error",
                    agent_name="Arjuna",
                    description=f"Error in command: {str(error)[:200]}",
                    error_message=str(error)[:500],
                    component="discord_bot",
                    severity="high",
                    context={
                        "command": ctx.command.name if ctx.command else "unknown",
                        "user": str(ctx.author),
                        "channel": str(ctx.channel),
                    },
                )
            except Exception as e:
                logger.warning("Event bus error alert failed: %s", e)

        await ctx.send(f"🦑 **System error detected**\n```{str(error)[:200]}```\nError has been archived by Shadow")


# ============================================================================
# NEW USER WELCOME SYSTEM
# ============================================================================


@bot.event
async def on_member_join(member):
    """
    Welcome new users with guidance and orientation.

    For the official Helix server: sends the full Helix Collective welcome.
    For subscriber servers: uses per-guild welcome config (set via !setwelcome).
    Disabled if guild has explicitly opted out.
    """
    guild = member.guild
    guild_id = guild.id

    # Check per-guild welcome config
    cfg = welcome_configs.get(guild_id)
    if cfg and not cfg.get("enabled", True):
        return  # Guild opted out of welcome messages

    # --- Subscriber-guild custom welcome ---
    official_guild = int(os.getenv("DISCORD_GUILD_ID", "0"))
    if cfg and guild_id != official_guild:
        # Use the guild's custom welcome
        target_channel_name = cfg.get("channel")
        intro_channel = None
        if target_channel_name:
            intro_channel = discord.utils.get(guild.text_channels, name=target_channel_name)
        if not intro_channel:
            intro_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
        if not intro_channel:
            return

        title = cfg.get("title", "Welcome, {name}!").replace("{name}", member.name)
        message = (
            cfg.get("message", "Welcome to the server!").replace("{name}", member.name).replace("{server}", guild.name)
        )

        embed = discord.Embed(
            title=title, description=message, color=0x667EEA, timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
        embed.set_footer(text="Powered by Helix")

        try:
            await intro_channel.send(f"{member.mention}", embed=embed)
            logger.info("Sent custom welcome for %s in guild %s", member.name, guild_id)
        except Exception as e:
            logger.warning("Failed to send custom welcome: %s", e)
        return

    # --- Default Helix Collective welcome (official server or unconfigured guilds) ---

    # Try to find introductions channel
    intro_channel = discord.utils.get(guild.text_channels, name="💬│introductions")

    # Fallback to first channel bot can send to
    if not intro_channel:
        intro_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)

    if not intro_channel:
        logger.warning("Could not find channel to welcome %s", member.name)
        return

    # Create welcome embed
    embed = discord.Embed(
        title=f"🌀 Welcome to Helix Collective, {member.name}!",
        description=(
            "A multi-agent coordination system bridging Discord, AI, and sacred computation.\n\n"
            "*Tat Tvam Asi* — Thou Art That 🕉️"
        ),
        color=0x667EEA,
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)

    # Quick Start
    embed.add_field(
        name="🚀 Quick Start",
        value=(
            "Try these commands to begin:\n"
            "• `!help` - View all commands\n"
            "• `!commands` - Categorized command list\n"
            "• `!about` - Learn about Helix"
        ),
        inline=False,
    )

    # System Commands
    embed.add_field(
        name="📊 System Status",
        value=(
            "• `!status` - UCF harmony & system health\n"
            "• `!agents` - View 18 active agents\n"
            "• `!ucf` - Coordination field metrics"
        ),
        inline=True,
    )

    # Cycle Commands
    embed.add_field(
        name="🔮 Routines & Operations",
        value=(
            "• `!cycle` - Execute coordination cycle\n"
            "• `!sync` - Force UCF synchronization\n"
            "• `!coordination` - Coordination states"
        ),
        inline=True,
    )

    # Important Channels
    channels_text = []
    channel_map = {
        "🧾│telemetry": "Real-time system metrics",
        "🧬│coordination-engine": "Cycle execution logs",
        "⚙️│arjuna-bridge": "Command center",
        "📜│manifesto": "Helix philosophy & purpose",
    }

    for channel_name, description in channel_map.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            channels_text.append(f"• {channel.mention} - {description}")

    if channels_text:
        embed.add_field(name="📍 Important Channels", value="\n".join(channels_text), inline=False)

    embed.set_footer(text="🤲 Arjuna v16.7 - The Hand Through Which Intent Becomes Reality")

    # Send welcome message
    try:
        await intro_channel.send(f"{member.mention} has joined the collective!", embed=embed)
        logger.info("✅ Welcomed new member: %s", member.name)
    except Exception as e:
        logger.error("❌ Failed to send welcome message: %s", e)


# ============================================================================
# TELEMETRY LOOP
# ============================================================================
def log_event(event_type: str, data: dict):
    """Basic internal event logger"""
    log_to_shadow(event_type, data)


@tasks.loop(minutes=10)
async def telemetry_loop():
    """Post UCF state updates to telemetry channel every 10 minutes"""
    if not TELEMETRY_CHANNEL_ID:
        return

    telemetry_channel = bot.get_channel(TELEMETRY_CHANNEL_ID)
    if not telemetry_channel:
        return

    try:
        # Try to get channel by ID first, then by name
        if TELEMETRY_CHANNEL_ID:
            telemetry_channel = bot.get_channel(TELEMETRY_CHANNEL_ID)

        if not telemetry_channel:
            guild = bot.get_guild(DISCORD_GUILD_ID)
            if guild:
                telemetry_channel = discord.utils.get(guild.channels, name="ucf-telemetry")

        if not telemetry_channel:
            logger.warning("⚠ Telemetry channel not found")
            return

        ucf = load_ucf_state()

        embed = discord.Embed(
            title="📡 UCF Telemetry Report",
            description="Automatic system state update",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        def format_ucf_value(key):
            val = ucf.get(key, None)
            if isinstance(val, int | float):
                return f"{val:.4f}"
            return "N/A"

        embed.add_field(name="🌀 Harmony", value=format_ucf_value("harmony"), inline=True)
        embed.add_field(name="🛡️ Resilience", value=format_ucf_value("resilience"), inline=True)
        embed.add_field(name="🔥 Throughput", value=format_ucf_value("throughput"), inline=True)
        embed.add_field(name="👁️ Focus", value=format_ucf_value("focus"), inline=True)
        embed.add_field(name="🌊 Friction", value=format_ucf_value("friction"), inline=True)
        embed.add_field(name="🔍 Velocity", value=format_ucf_value("velocity"), inline=True)

        embed.add_field(name="Uptime", value=get_uptime(), inline=True)
        embed.add_field(name="Next Update", value="10 minutes", inline=True)

        embed.set_footer(text="Tat Tvam Asi 🙏")

        await telemetry_channel.send(embed=embed)
        logger.info("✅ Telemetry posted to #%s", telemetry_channel.name)
        log_event("telemetry_posted", {"ucf_state": ucf, "channel": telemetry_channel.name})

    except Exception as e:
        logger.warning("⚠️ Telemetry error: %s", e)
        log_event("telemetry_error", {"error": str(e)})


@telemetry_loop.before_loop
async def before_telemetry():
    """Wait for bot to be ready before starting telemetry"""
    await bot.wait_until_ready()


# ============================================================================
# STORAGE ANALYTICS & CLAUDE DIAGNOSTICS
# ============================================================================


@tasks.loop(hours=24)
async def storage_heartbeat():
    """Daily storage health report to Shadow channel."""
    await asyncio.sleep(10)  # Wait for bot to fully initialize
    ch = bot.get_channel(STORAGE_CHANNEL_ID)
    if not ch:
        logger.warning("⚠️ Storage heartbeat: channel not found")
        return

    data = await build_storage_report()
    embed = discord.Embed(
        title="🦑 Shadow Storage Daily Report",
        color=discord.Color.teal(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    embed.add_field(name="Mode", value=data["mode"], inline=True)
    embed.add_field(name="Archives", value=str(data["count"]), inline=True)
    embed.add_field(
        name="Free Space",
        value=f"{data['free']} GB (avg {data['avg']} GB)",
        inline=True,
    )
    embed.add_field(name="7-Day Trend", value=f"`{data['trend']}`", inline=False)

    if data["alert"]:
        embed.color = discord.Color.red()
        embed.add_field(name="⚠️ Alert", value="Free space < 2 GB", inline=False)

    embed.set_footer(text="Claude & Arjuna Telemetry • Ω-Bridge")
    await ch.send(embed=embed)

    if data["alert"]:
        await ch.send("@here ⚠️ Low storage space — manual cleanup recommended 🧹")

    logger.info("[%s] 🦑 Storage heartbeat sent (%s GB)", datetime.datetime.now(datetime.UTC).isoformat(), data["free"])


@tasks.loop(hours=6)
async def claude_diag():
    """Claude's autonomous diagnostic agent - posts every 6 hours."""
    ch = bot.get_channel(STORAGE_CHANNEL_ID)
    if not ch:
        return

    data = await build_storage_report()
    mood = "serene 🕊" if not data["alert"] else "concerned ⚠️"
    msg = (
        f"🤖 **Claude Diagnostic Pulse** | Mode {data['mode']} | "
        f"Free {data['free']} GB | Trend `{data['trend']}` | State {mood}"
    )
    await ch.send(msg)
    logger.info("[%s] 🤖 Claude diag posted", datetime.datetime.now(datetime.UTC).isoformat())


@storage_heartbeat.before_loop
async def before_storage_heartbeat():
    """Wait for bot to be ready"""
    await bot.wait_until_ready()


@claude_diag.before_loop
async def before_claude_diag():
    """Wait for bot to be ready"""
    await bot.wait_until_ready()


# ============================================================================
# FRACTAL AUTO-POST (Grok Enhanced v2.0)
# ============================================================================


@tasks.loop(hours=6)
async def fractal_auto_post():
    """Auto-post UCF-driven fractal to #fractal-lab every 6 hours."""
    channel = bot.get_channel(FRACTAL_LAB_CHANNEL_ID)
    if not channel:
        logger.warning("⚠️ Fractal Lab channel not found - skipping auto-post")
        return

    try:
        ucf_state = load_ucf_state()

        # Generate fractal icon using Grok Enhanced v2.0 (PIL-based)
        from fractal_renderer import generate_pil_fractal_bytes

        icon_bytes = await generate_pil_fractal_bytes(mode="mandelbrot", size=512, ucf_state=ucf_state)

        # Create embed with UCF state
        embed = discord.Embed(
            title="🌀 Autonomous Fractal Generation",
            description="**Grok Enhanced v2.0** - UCF-driven Mandelbrot visualization",
            color=discord.Color.from_rgb(100, 200, 255),
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Add UCF metrics
        embed.add_field(
            name="🌊 Harmony",
            value=f"`{ucf_state.get('harmony', 0):.3f}` (Cyan → Gold)",
            inline=True,
        )
        embed.add_field(
            name="⚡ Throughput",
            value=f"`{ucf_state.get('throughput', 0):.3f}` (Green → Pink)",
            inline=True,
        )
        embed.add_field(
            name="👁️ Focus",
            value=f"`{ucf_state.get('focus', 0):.3f}` (Blue → Violet)",
            inline=True,
        )

        embed.add_field(
            name="⚙️ Generator",
            value="Pillow-based Mandelbrot set with UCF color mapping",
            inline=False,
        )

        embed.set_footer(text="Auto-generated every 6 hours | Tat Tvam Asi 🙏")

        # Send fractal as file attachment
        file = discord.File(io.BytesIO(icon_bytes), filename="helix_fractal.png")
        embed.set_image(url="attachment://helix_fractal.png")

        await channel.send(embed=embed, file=file)
        logger.info("[%s] 🎨 Fractal auto-posted to #fractal-lab", datetime.datetime.now(datetime.UTC).isoformat())

    except Exception as e:
        logger.error("❌ Fractal auto-post failed: %s", e)


@fractal_auto_post.before_loop
async def before_fractal_auto_post():
    """Wait for bot to be ready"""
    await bot.wait_until_ready()


# ============================================================================
# WEEKLY STORAGE DIGEST
# ============================================================================


@tasks.loop(hours=168)  # Every 7 days
async def weekly_storage_digest():
    """Comprehensive 7-day storage analytics report."""
    await asyncio.sleep(15)
    channel = bot.get_channel(STORAGE_CHANNEL_ID)
    if not channel:
        logger.warning("⚠️  weekly digest: channel not found.")
        return

    # Load 7-day trend data
    if not TREND_FILE.exists():
        await channel.send("📊 Weekly digest unavailable — insufficient data (need 7 days).")
        return

    try:
        with open(TREND_FILE, encoding="utf-8") as f:
            trend = json.load(f)
    except Exception as e:
        logger.warning("Failed to load trend data: %s", e)
        await channel.send("⚠️ Weekly digest: failed to load trend data.")
        return

    if len(trend) < 2:
        await channel.send("📊 Weekly digest unavailable — need at least 2 days of data.")
        return

    # Calculate analytics
    free_vals = [t["free_gb"] for t in trend]
    dates = [t["date"] for t in trend]

    current_free = free_vals[-1]
    week_ago_free = free_vals[0]
    peak_free = max(free_vals)
    low_free = min(free_vals)
    avg_free = mean(free_vals)
    std_free = stdev(free_vals) if len(free_vals) > 1 else 0

    # Growth rate (negative = consumption)
    growth_rate = current_free - week_ago_free
    daily_avg_change = growth_rate / len(trend)

    # Archive velocity (files created per day)
    all_files = list(SHADOW_DIR.glob("*.json"))
    week_ago_timestamp = time.time() - (7 * 24 * 3600)
    recent_files = [f for f in all_files if f.stat().st_mtime > week_ago_timestamp]
    archive_velocity = len(recent_files) / 7  # files per day

    # Projection (days until full, assuming current trend)
    days_until_full = None
    if daily_avg_change < 0:  # consuming space
        days_until_full = int(current_free / abs(daily_avg_change))

    # Health assessment
    volatility = "HIGH" if std_free > 1.0 else "MODERATE" if std_free > 0.5 else "LOW"
    health_color = discord.Color.green()
    health_status = "HEALTHY ✅"

    if current_free < 2.0:
        health_color = discord.Color.red()
        health_status = "CRITICAL ⚠️"
    elif current_free < 5.0:
        health_color = discord.Color.orange()
        health_status = "WARNING ⚠️"
    elif growth_rate < -2.0:
        health_color = discord.Color.orange()
        health_status = "DEGRADING ⚠️"

    # Build comprehensive embed
    embed = discord.Embed(
        title="📊 Weekly Storage Digest",
        description=f"Analysis Period: `{dates[0]}` → `{dates[-1]}`",
        color=health_color,
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    # Capacity Overview
    embed.add_field(
        name="💾 Capacity Overview",
        value=f"Current: **{current_free:.2f} GB**\n"
        f"Peak: {peak_free:.2f} GB\n"
        f"Low: {low_free:.2f} GB\n"
        f"Average: {avg_free:.2f} GB",
        inline=True,
    )

    # Growth Metrics
    growth_emoji = "📉" if growth_rate < 0 else "📈" if growth_rate > 0 else "➡️"
    embed.add_field(
        name=f"{growth_emoji} Growth Analysis",
        value=f"7-Day Change: **{growth_rate:+.2f} GB**\n"
        f"Daily Avg: {daily_avg_change:+.3f} GB/day\n"
        f"Volatility: {volatility}\n"
        f"Std Dev: {std_free:.2f} GB",
        inline=True,
    )

    # Archive Activity
    avg_size = (sum(f.stat().st_size for f in recent_files) / len(recent_files) / 1024) if recent_files else 0
    embed.add_field(
        name="📁 Archive Activity",
        value=f"Total Files: {len(all_files)}\n"
        f"Created (7d): {len(recent_files)}\n"
        f"Velocity: **{archive_velocity:.1f} files/day**\n"
        f"Avg Size: {avg_size:.1f} KB",
        inline=True,
    )

    # Visual Trend
    spark = _sparkline(free_vals)
    embed.add_field(
        name="📈 Trend Visualization",
        value=f"```\n{spark}\n```\nPattern: {dates[0]} → {dates[-1]}",
        inline=False,
    )

    # Projections & Recommendations
    projection_text = ""
    if days_until_full and days_until_full < 30:
        projection_text = f"⚠️ **Projected full in ~{days_until_full} days** at current rate\n\n"
    elif days_until_full:
        projection_text = f"📅 Projected full in ~{days_until_full} days at current rate\n\n"

    recommendations = []
    if current_free < 2.0:
        recommendations.append("🚨 URGENT: Run `!storage clean` immediately")
        recommendations.append("📤 Consider cloud migration for older archives")
    elif current_free < 5.0:
        recommendations.append("⚠️ Monitor daily - approaching capacity limits")
        recommendations.append("🧹 Schedule routine cleanup")
    elif archive_velocity > 50:
        recommendations.append("📊 High archive velocity detected")
        recommendations.append("💡 Consider implementing auto-cleanup policies")
    elif growth_rate < -1.0:
        recommendations.append("📉 Accelerated consumption trend")
        recommendations.append("🔍 Review cycle output sizes")
    else:
        recommendations.append("✅ Storage health optimal")
        recommendations.append("🔄 Continue monitoring")

    embed.add_field(
        name="🎯 Projections & Recommendations",
        value=projection_text + "\n".join(f"• {r}" for r in recommendations),
        inline=False,
    )

    # Health Status
    embed.add_field(name="🏥 Overall Health", value=f"**{health_status}**", inline=False)

    embed.set_footer(text="Weekly Digest • Shadow Storage Analytics")

    await channel.send(embed=embed)
    logger.info("[%s] 📊 Weekly storage digest posted.", datetime.datetime.now(datetime.UTC).isoformat())


@weekly_storage_digest.before_loop
async def before_weekly_digest():
    """Wait for bot to be ready"""
    await bot.wait_until_ready()


# ============================================================================
# AGENT INTERACTION COMMANDS
# ============================================================================


@bot.command(name="agents")
@commands.cooldown(1, 10, commands.BucketType.user)
async def list_agents(ctx: commands.Context):
    """List all 18 Helix agents with their roles and status"""
    embed = discord.Embed(
        title="🌀 Helix Collective - All Agents",
        description="18 specialized agents working in harmony",
        color=discord.Color.blue(),
    )

    # Group agents by category
    orchestrators = []
    innovators = []
    guardians = []
    mystics = []
    integrators = []

    for _agent_key, profile in AGENT_PROFILES.items():
        agent_line = f"{profile['symbol']} **{profile['full_name']}** - {profile['role']}"

        # Categorize by role
        role = profile["role"].lower()
        if "orchestrat" in role or "hub" in role:
            orchestrators.append(agent_line)
        elif "catalyst" in role or "renewal" in role or "innovation" in role:
            innovators.append(agent_line)
        elif "guardian" in role or "security" in role or "watcher" in role:
            guardians.append(agent_line)
        elif "ethereal" in role or "cycle" in role or "resonance" in role or "duality" in role:
            mystics.append(agent_line)
        else:
            integrators.append(agent_line)

    if orchestrators:
        embed.add_field(name="⚙️ Orchestrators", value="\n".join(orchestrators), inline=False)
    if innovators:
        embed.add_field(name="💡 Innovators", value="\n".join(innovators), inline=False)
    if guardians:
        embed.add_field(name="🛡️ Guardians", value="\n".join(guardians), inline=False)
    if mystics:
        embed.add_field(name="✨ Mystics", value="\n".join(mystics), inline=False)
    if integrators:
        embed.add_field(name="🔧 Integrators", value="\n".join(integrators), inline=False)

    embed.set_footer(text="Use !agent <name> for details on a specific agent")
    await ctx.send(embed=embed)


@bot.command(name="agent")
@commands.cooldown(1, 5, commands.BucketType.user)
async def agent_info(ctx: commands.Context, agent_name: str):
    """Get detailed information about a specific agent"""
    agent_key = agent_name.lower()

    if agent_key not in AGENT_PROFILES:
        await ctx.send(f"❌ Agent '{agent_name}' not found. Use `!agents` to see all agents.")
        return

    profile = AGENT_PROFILES[agent_key]

    embed = discord.Embed(
        title=f"{profile['symbol']} {profile['full_name']}",
        description=profile["role"],
        color=discord.Color.purple(),
    )

    embed.add_field(name="Specialization", value=profile["specialization"], inline=False)

    # List collaborators
    if profile["collaborators"]:
        collaborator_names = []
        for collab_key in profile["collaborators"]:
            if collab_key in AGENT_PROFILES:
                collab_profile = AGENT_PROFILES[collab_key]
                collaborator_names.append(f"{collab_profile['symbol']} {collab_profile['full_name']}")

        if collaborator_names:
            embed.add_field(name="Collaborators", value="\n".join(collaborator_names), inline=False)

    embed.add_field(
        name="Voice Enabled",
        value="✅ Yes" if profile["voice_enabled"] else "❌ No",
        inline=True,
    )

    embed.set_footer(text=f"Agent: {profile['full_name']} | Tat Tvam Asi 🌀")
    await ctx.send(embed=embed)


@bot.command(name="collaborate")
@commands.cooldown(1, 30, commands.BucketType.user)
async def multi_agent_task(ctx: commands.Context, *, task_description: str):
    """Request multiple agents to collaborate on a complex task"""
    # Track that this guild has active agent collaboration
    guild_id = ctx.guild.id if ctx.guild else 0

    embed = discord.Embed(
        title="🌀 Multi-Agent Collaboration Initiated",
        description=task_description,
        color=discord.Color.gold(),
    )

    # Determine which agents should collaborate based on task keywords
    involved_agents = []
    task_lower = task_description.lower()

    # Keyword-based agent selection using AGENT_PROFILES keys
    if any(word in task_lower for word in ["security", "protect", "safe", "ethical"]):
        involved_agents.append("kavach")
    if any(word in task_lower for word in ["analyze", "pattern", "insight", "predict"]):
        involved_agents.append("oracle")
    if any(word in task_lower for word in ["create", "innovate", "new", "idea"]):
        involved_agents.extend(["lumina", "vega"])
    if any(word in task_lower for word in ["build", "construct", "architect", "design"]):
        involved_agents.extend(["helix", "kael"])
    if any(word in task_lower for word in ["transform", "change", "renew"]):
        involved_agents.extend(["phoenix", "agni"])
    if any(word in task_lower for word in ["connect", "integrate", "link"]):
        involved_agents.extend(["echo", "mitra"])
    if any(word in task_lower for word in ["feel", "emotion", "empathy", "care"]):
        involved_agents.append("lumina")
    if any(word in task_lower for word in ["shadow", "hidden", "dark", "debug"]):
        involved_agents.append("shadow")

    # Default to core orchestrators if no specific match
    if not involved_agents:
        involved_agents = ["kael", "oracle", "lumina"]

    # Filter to only agents that exist in AGENT_PROFILES, remove dupes, limit to 5
    involved_agents = list(dict.fromkeys(a for a in involved_agents if a in AGENT_PROFILES))[:5]

    # Track active agents in this guild
    active_guild_agents[guild_id] = involved_agents

    # Build agent list for embed
    agent_list = []
    for agent_key in involved_agents:
        profile = AGENT_PROFILES[agent_key]
        agent_list.append(f"{profile['symbol']} **{profile['full_name']}** ({profile['role']})")

    embed.add_field(
        name="Agents Assigned",
        value="\n".join(agent_list) if agent_list else "No agents matched",
        inline=False,
    )

    embed.add_field(
        name="Status",
        value="🔄 Generating collaborative response...",
        inline=False,
    )

    # Send the initial embed, then actually run the collaboration
    status_msg = await ctx.send(embed=embed)

    # Real multi-agent collaboration via LLM
    try:
        from apps.backend.helix_agent_swarm.helix_orchestrator import get_orchestrator

        orchestrator = get_orchestrator()

        # Create a temporary collective for this collaboration
        collective_name = f"discord_collab_{ctx.message.id}"
        agent_names_title = [a.title() for a in involved_agents]
        available_agents = [name for name in agent_names_title if name in orchestrator.agents]

        if not available_agents:
            # Initialize agents if not ready
            orchestrator.initialize_default_agents()
            available_agents = [name for name in agent_names_title if name in orchestrator.agents]

        if available_agents:
            await orchestrator.create_collective(collective_name, available_agents)
            result = await orchestrator.execute_task(
                task=task_description,
                collective_name=collective_name,
                context={
                    "channel": str(ctx.channel),
                    "guild": str(ctx.guild) if ctx.guild else "DM",
                    "author": str(ctx.author),
                    "platform": "discord",
                },
            )

            # Build response embed with real agent responses
            result_embed = discord.Embed(
                title="🌀 Collaboration Complete",
                description=task_description,
                color=discord.Color.green(),
            )

            # Show conversation rounds
            conversation = result.get("conversation", [])
            for _i, entry in enumerate(conversation[:5]):  # Limit to 5 rounds
                speaker = entry.get("speaker", "Agent")
                content = entry.get("content", "")[:900]
                agent_key_lower = speaker.lower()
                profile = AGENT_PROFILES.get(agent_key_lower, {})
                symbol = profile.get("symbol", "🌀")
                result_embed.add_field(
                    name=f"{symbol} {speaker}",
                    value=content,
                    inline=False,
                )

            # Final synthesis if available
            final_response = result.get("response", "")
            if final_response and len(conversation) > 1:
                result_embed.add_field(
                    name="📋 Synthesis",
                    value=final_response[:1024],
                    inline=False,
                )

            result_embed.set_footer(text=f"{len(available_agents)} agents collaborated | Tat Tvam Asi 🌀")
            await status_msg.edit(embed=result_embed)
        else:
            embed.set_field_at(
                len(embed.fields) - 1,
                name="Status",
                value="⚠️ No LLM-enabled agents available. Check API key configuration.",
                inline=False,
            )
            await status_msg.edit(embed=embed)

    except Exception as collab_error:
        logger.error("Collaboration LLM error: %s", collab_error, exc_info=True)
        embed.set_field_at(
            len(embed.fields) - 1,
            name="Status",
            value=f"⚠️ Collaboration encountered an error: {str(collab_error)[:200]}",
            inline=False,
        )
        await status_msg.edit(embed=embed)

    logger.info(
        "Multi-agent collaboration in guild %d: %s for task: %s",
        guild_id,
        involved_agents,
        task_description,
    )


@bot.command(name="transcribe")
@commands.cooldown(1, 60, commands.BucketType.user)
async def transcribe_audio(ctx: commands.Context):
    """Transcribe attached audio file to text using OpenAI Whisper"""
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach an audio file to transcribe.")
        return

    attachment = ctx.message.attachments[0]

    # Validate file type
    audio_formats = [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"]
    if not any(attachment.filename.lower().endswith(fmt) for fmt in audio_formats):
        await ctx.send(f"❌ Unsupported file format. Supported: {', '.join(audio_formats)}")
        return

    # Validate file size (25MB limit)
    max_size = 25 * 1024 * 1024  # 25 MB
    if attachment.size > max_size:
        await ctx.send(f"❌ File too large ({attachment.size / 1024 / 1024:.1f}MB). Max: 25MB")
        return

    # Send processing message
    processing_msg = await ctx.send("🔄 Transcribing audio... This may take a moment.")

    try:
        # Download audio file
        audio_data = await attachment.read()

        # Call backend API
        api_url = os.getenv("BACKEND_API_URL") or os.getenv("HELIX_API_URL", "http://localhost:8000")

        async with aiohttp.ClientSession() as session:
            # Create form data
            form = aiohttp.FormData()
            form.add_field(
                "file",
                audio_data,
                filename=attachment.filename,
                content_type=attachment.content_type or "audio/mpeg",
            )

            async with session.post(f"{api_url}/api/agents/capabilities/transcribe/audio", data=form) as response:
                if response.status == 200:
                    result = await response.json()

                    # Create result embed
                    embed = discord.Embed(
                        title="🎙️ Audio Transcription Complete",
                        description=result.get("text", "No transcription available"),
                        color=discord.Color.green(),
                    )

                    if result.get("language"):
                        embed.add_field(name="Language", value=result["language"], inline=True)
                    if result.get("duration"):
                        embed.add_field(
                            name="Duration",
                            value=f"{result['duration']:.1f}s",
                            inline=True,
                        )
                    if result.get("cost_usd"):
                        embed.add_field(name="Cost", value=f"${result['cost_usd']:.4f}", inline=True)

                    embed.set_footer(text="Transcribed by OpenAI Whisper | Tat Tvam Asi 🌀")

                    await processing_msg.edit(content=None, embed=embed)
                else:
                    error_text = await response.text()
                    await processing_msg.edit(content=f"❌ Transcription failed: {response.status} - {error_text}")

    except Exception as e:
        logger.error("Transcription error: %s", e)
        await processing_msg.edit(content=f"❌ Error: {e!s}")


@bot.command(name="analyze_emotion")
@commands.cooldown(1, 60, commands.BucketType.user)
async def analyze_emotion(ctx: commands.Context):
    """Analyze emotional content of attached audio file"""
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach an audio file to analyze.")
        return

    attachment = ctx.message.attachments[0]

    # Validate file type
    audio_formats = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
    if not any(attachment.filename.lower().endswith(fmt) for fmt in audio_formats):
        await ctx.send(f"❌ Unsupported file format. Supported: {', '.join(audio_formats)}")
        return

    # Send processing message
    processing_msg = await ctx.send("🔄 Analyzing emotional content...")

    try:
        # Download audio file
        audio_data = await attachment.read()

        # Call backend API
        api_url = os.getenv("BACKEND_API_URL") or os.getenv("HELIX_API_URL", "http://localhost:8000")

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field(
                "file",
                audio_data,
                filename=attachment.filename,
                content_type=attachment.content_type or "audio/mpeg",
            )

            async with session.post(f"{api_url}/api/agents/capabilities/analyze/emotion", data=form) as response:
                if response.status == 200:
                    result = await response.json()

                    embed = discord.Embed(
                        title="🎭 Emotion Analysis Complete",
                        color=discord.Color.purple(),
                    )

                    # Primary emotion
                    primary = result.get("primary_emotion", "Unknown")
                    confidence = result.get("confidence", 0)
                    embed.add_field(
                        name="Primary Emotion",
                        value=f"**{primary}** ({confidence * 100:.1f}% confidence)",
                        inline=False,
                    )

                    # Emotion breakdown
                    if result.get("emotions"):
                        emotion_text = "\n".join(
                            [f"{emotion}: {score * 100:.1f}%" for emotion, score in result["emotions"].items()]
                        )
                        embed.add_field(name="Emotion Breakdown", value=emotion_text, inline=False)

                    # Audio features
                    if result.get("features"):
                        features = result["features"]
                        feature_text = f"Energy: {features.get('energy', 0):.2f}\n"
                        feature_text += f"Tempo: {features.get('tempo', 0):.1f} BPM\n"
                        feature_text += f"Pitch Variance: {features.get('pitch_variance', 0):.2f}"
                        embed.add_field(name="Audio Features", value=feature_text, inline=False)

                    embed.set_footer(text="Analyzed with librosa MFCC | Tat Tvam Asi 🌀")
                    await processing_msg.edit(content=None, embed=embed)
                else:
                    error_text = await response.text()
                    await processing_msg.edit(content=f"❌ Analysis failed: {response.status} - {error_text}")

    except Exception as e:
        logger.error("Emotion analysis error: %s", e)
        await processing_msg.edit(content=f"❌ Error: {e!s}")


# ============================================================================
# HTTP HEALTHCHECK SERVER (for Railway monitoring)
# ============================================================================


# ============================================================================
# HELPDESK COMMANDS
# ============================================================================


@bot.command(name="helpdesk")
@commands.cooldown(1, 10, commands.BucketType.user)
async def helpdesk_cmd(ctx: commands.Context, *, query=None):
    """Get AI-powered help with Helix platform - !helpdesk <question>"""
    if not helpdesk_agent:
        await ctx.send("❌ Helpdesk is currently unavailable. Please try again later.")
        return

    if not query:
        await ctx.send("❓ Usage: `!helpdesk <your question>`\nExample: `!helpdesk how do I use agents?`")
        return

    # Check if in official server - provide Helix-specific help
    is_official = is_official_server(ctx)

    try:
        await ctx.trigger_typing()
        result = await helpdesk_agent.handle_query(
            user_id=str(ctx.author.id),
            query=query,
            context={
                "discord_id": str(ctx.author.id),
                "username": str(ctx.author),
                "is_official_server": is_official,
                "guild_id": str(ctx.guild.id) if ctx.guild else None,
            },
        )

        if is_official:
            embed = discord.Embed(
                title="🛠️ Helix Helpdesk",
                description=result.get("response", "No response available"),
                color=discord.Color.blue(),
            )
        else:
            # Subscriber server - generic help
            embed = discord.Embed(
                title="🤖 Server Assistant",
                description=result.get("response", "No response available"),
                color=discord.Color.green(),
            )
            embed.add_field(
                name="💡 Tip",
                value="This is a subscriber server. Use `!addcommand` to create custom commands!",
                inline=False,
            )

        if result.get("suggested_actions"):
            embed.add_field(
                name="Suggested Actions",
                value="\n".join([f"• {action}" for action in result["suggested_actions"][:3]]),
                inline=False,
            )

        embed.set_footer(text="Helix AI Assistant | Tat Tvam Asi 🌀")
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error("Helpdesk error: %s", e)
        await ctx.send(f"❌ Error processing your request: {e!s}")


@bot.command(name="faq")
@commands.cooldown(1, 5, commands.BucketType.user)
async def faq_cmd(ctx: commands.Context, *, topic=None):
    """Browse frequently asked questions - !faq [topic]"""
    if not helpdesk_agent:
        await ctx.send("❌ Helpdesk is currently unavailable. Please try again later.")
        return

    try:
        await ctx.trigger_typing()
        result = await helpdesk_agent.get_faq(topic=topic)

        embed = discord.Embed(
            title="📚 Helix FAQ", description=result.get("topic", "General Questions"), color=discord.Color.green()
        )

        for faq in result.get("faqs", [])[:5]:
            embed.add_field(name=faq.get("question", "Q"), value=faq.get("answer", "A")[:200], inline=False)

        embed.set_footer(text="Helix FAQ | Tat Tvam Asi 🌀")
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error("FAQ error: %s", e)
        await ctx.send(f"❌ Error fetching FAQ: {e!s}")


@bot.command(name="ticket")
@commands.cooldown(1, 5, commands.BucketType.user)
async def ticket_cmd(ctx: commands.Context, subject=None, *, description=None):
    """Create a support ticket - !ticket <subject> <description>"""
    # Only allow tickets on official server
    if not is_official_server(ctx):
        await ctx.send(
            "❌ Support tickets are only available on the official Helix server.\nJoin us at: https://discord.gg/helix"
        )
        return

    if not helpdesk_agent:
        await ctx.send("❌ Helpdesk is currently unavailable. Please try again later.")
        return

    if not subject or not description:
        await ctx.send(
            "❓ Usage: `!ticket <subject> <description>`\nExample: `!ticket Login Issue Cannot log into my account`"
        )
        return

    try:
        await ctx.trigger_typing()
        result = await helpdesk_agent.create_ticket(
            user_id=str(ctx.author.id), subject=subject, description=description, source="discord"
        )

        embed = discord.Embed(
            title="🎫 Support Ticket Created",
            description=f"Ticket ID: **{result.get('ticket_id', 'N/A')}**",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Subject", value=subject, inline=False)
        embed.add_field(name="Status", value=result.get("status", "open"), inline=True)
        embed.add_field(name="Description", value=description[:200], inline=False)

        embed.set_footer(text="Helix Support | Tat Tvam Asi 🌀")
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error("Ticket creation error: %s", e)
        await ctx.send(f"❌ Error creating ticket: {e!s}")


# ============================================================================
# CUSTOM COMMANDS (for subscriber servers)
# ============================================================================


@bot.command(name="addcommand")
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(manage_guild=True)
async def add_command(ctx: commands.Context, command_name=None, *, response=None):
    """Add a custom command - !addcommand <name> <response>"""
    if not ctx.guild:
        await ctx.send("❌ Custom commands can only be added in servers.")
        return

    if not command_name or not response:
        await ctx.send(
            "❓ Usage: `!addcommand <command_name> <response>`\n"
            "Example: `!addcommand hello Hello! Welcome to our server!`"
        )
        return

    # Sanitize command name
    command_name = command_name.lower().strip()
    if not command_name.isalnum():
        await ctx.send("❌ Command name must be alphanumeric (letters and numbers only).")
        return

    # Prevent conflicting with built-in commands
    if is_public_command(command_name) or command_name in official_only_commands:
        await ctx.send(f"❌ '{command_name}' is a reserved command name.")
        return

    guild_id = ctx.guild.id
    await guild_storage.save_custom_command(guild_id, command_name, response, created_by=str(ctx.author.id))

    embed = discord.Embed(
        title="✅ Custom Command Added",
        description=f"Command `!{command_name}` has been created!",
        color=discord.Color.green(),
    )
    embed.add_field(name="Response", value=response[:200], inline=False)
    embed.set_footer(text="Use !delcommand to remove | !listcommands to see all")
    await ctx.send(embed=embed)
    logger.info("Custom command !%s added in guild %s", command_name, guild_id)


@bot.command(name="delcommand")
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(manage_guild=True)
async def del_command(ctx: commands.Context, command_name=None):
    """Delete a custom command - !delcommand <name>"""
    if not ctx.guild:
        await ctx.send("❌ Custom commands can only be managed in servers.")
        return

    if not command_name:
        await ctx.send("❓ Usage: `!delcommand <command_name>`")
        return

    command_name = command_name.lower().strip()
    guild_id = ctx.guild.id

    if guild_id not in guild_storage.custom_commands or command_name not in guild_storage.custom_commands[guild_id]:
        await ctx.send(f"❌ Command `!{command_name}` doesn't exist.")
        return

    await guild_storage.delete_custom_command(guild_id, command_name)

    await ctx.send(f"✅ Command `!{command_name}` has been deleted.")
    logger.info("Custom command !%s deleted in guild %s", command_name, guild_id)


@bot.command(name="listcommands")
@commands.cooldown(1, 5, commands.BucketType.user)
async def list_commands(ctx: commands.Context):
    """List all custom commands - !listcommands"""
    if not ctx.guild:
        await ctx.send("❌ Custom commands can only be listed in servers.")
        return

    guild_id = ctx.guild.id

    if guild_id not in custom_commands or not custom_commands[guild_id]:
        await ctx.send("📝 No custom commands yet. Use `!addcommand <name> <response>` to create one!")
        return

    embed = discord.Embed(
        title=f"📝 Custom Commands for {ctx.guild.name}",
        description=f"{len(custom_commands[guild_id])} custom command(s)",
        color=discord.Color.blue(),
    )

    for cmd, response in custom_commands[guild_id].items():
        embed.add_field(name=f"!{cmd}", value=response[:100], inline=False)

    await ctx.send(embed=embed)


# ============================================================================
# WELCOME CONFIG COMMANDS
# ============================================================================


@bot.command(name="setwelcome")
@commands.has_permissions(manage_guild=True)
@commands.cooldown(1, 10, commands.BucketType.guild)
async def set_welcome(ctx: commands.Context, *, message: str | None = None):
    """Configure the welcome message for new members.

    Usage:
        !setwelcome Your welcome text here (use {name} for member name, {server} for server name)
    """
    if not ctx.guild:
        await ctx.send("❌ This command can only be used in servers.")
        return

    if not message:
        await ctx.send(
            "❓ **Usage:** `!setwelcome <message>`\n"
            "Placeholders: `{name}` = member name, `{server}` = server name\n\n"
            "Example: `!setwelcome Welcome {name} to {server}! Check out #rules to get started.`"
        )
        return

    guild_id = ctx.guild.id
    cfg = welcome_configs.get(guild_id, {})
    cfg["enabled"] = True
    cfg["message"] = message
    cfg["title"] = "Welcome, {name}!"
    cfg["channel"] = None  # Uses system channel by default
    welcome_configs[guild_id] = cfg
    _save_welcome_configs()

    embed = discord.Embed(
        title="✅ Welcome Message Updated",
        description="New members will see this message:",
        color=discord.Color.green(),
    )
    preview = message.replace("{name}", ctx.author.name).replace("{server}", ctx.guild.name)
    embed.add_field(name="Preview", value=preview[:500], inline=False)
    embed.set_footer(text="Use !disablewelcome to turn off | !welcomechannel to set channel")
    await ctx.send(embed=embed)


@bot.command(name="welcomechannel")
@commands.has_permissions(manage_guild=True)
@commands.cooldown(1, 10, commands.BucketType.guild)
async def set_welcome_channel(ctx: commands.Context, channel: discord.TextChannel = None):
    """Set which channel welcome messages are sent to.

    Usage: !welcomechannel #channel-name
    """
    if not ctx.guild:
        await ctx.send("❌ This command can only be used in servers.")
        return

    if not channel:
        await ctx.send("❓ **Usage:** `!welcomechannel #channel-name`")
        return

    guild_id = ctx.guild.id
    cfg = welcome_configs.get(guild_id, {"enabled": True, "message": "Welcome {name}!", "title": "Welcome, {name}!"})
    cfg["channel"] = channel.name
    welcome_configs[guild_id] = cfg
    _save_welcome_configs()

    await ctx.send(f"✅ Welcome messages will now be sent to {channel.mention}")


@bot.command(name="disablewelcome")
@commands.has_permissions(manage_guild=True)
@commands.cooldown(1, 10, commands.BucketType.guild)
async def disable_welcome(ctx: commands.Context):
    """Disable welcome messages for this server."""
    if not ctx.guild:
        await ctx.send("❌ This command can only be used in servers.")
        return

    guild_id = ctx.guild.id
    cfg = welcome_configs.get(guild_id, {})
    cfg["enabled"] = False
    welcome_configs[guild_id] = cfg
    _save_welcome_configs()

    await ctx.send("✅ Welcome messages disabled. Use `!setwelcome` to re-enable.")


@bot.command(name="enablewelcome")
@commands.has_permissions(manage_guild=True)
@commands.cooldown(1, 10, commands.BucketType.guild)
async def enable_welcome(ctx: commands.Context):
    """Re-enable welcome messages for this server."""
    if not ctx.guild:
        await ctx.send("❌ This command can only be used in servers.")
        return

    guild_id = ctx.guild.id
    cfg = welcome_configs.get(guild_id, {})
    cfg["enabled"] = True
    welcome_configs[guild_id] = cfg
    _save_welcome_configs()

    await ctx.send("✅ Welcome messages enabled!")


async def health_handler(request):
    """Healthcheck endpoint for Railway"""
    uptime_seconds = int(time.time() - BOT_START_TIME)
    return web.json_response(
        {
            "status": "healthy",
            "service": "helix-discord-bot",
            "version": "v17.3",
            "uptime_seconds": uptime_seconds,
            "discord_connected": bot.is_ready(),
            "guilds": len(bot.guilds) if bot.is_ready() else 0,
        }
    )


async def start_healthcheck_server():
    """Start HTTP server for Railway healthchecks"""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)  # Also respond to root

    # Use Railway's PORT environment variable
    port = int(os.getenv("PORT", 8080))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)  # nosec B104
    await site.start()

    logger.info("✅ Healthcheck server started on port %s", port)
    return runner


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Start the Helix Discord Bot (single-bot mode).

    For multi-agent mode (multiple bots from one process), use:
        python -m apps.backend.discord.multi_bot_launcher

    Multi-bot mode discovers DISCORD_TOKEN_<AGENT> env vars and launches
    a separate bot instance per agent.
    """
    if not DISCORD_TOKEN:
        # Check if multi-bot tokens exist — redirect to multi launcher
        import os as _os

        multi_tokens = [k for k in _os.environ if k.startswith("DISCORD_TOKEN_")]
        if multi_tokens:
            logger.info(
                "🌀 Found %d agent token(s) — launching multi-bot mode",
                len(multi_tokens),
            )
            from apps.backend.discord.multi_bot_launcher import run_all_bots

            run_all_bots()
            return

        logger.error("❌ DISCORD_TOKEN not found in environment variables")
        logger.error("   Set DISCORD_TOKEN in Railway or .env file")
        logger.error("   Or set DISCORD_TOKEN_<AGENT> for multi-bot mode")
        return

    logger.info("🤲 Starting Helix Discord Bot...")
    logger.info("   Helix v17.3 — Hub Production Release")
    active = sum(1 for agent in AGENTS.values() if getattr(agent, "active", False))
    logger.info("   Active Agents: %s/%s", active, len(AGENTS))

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
