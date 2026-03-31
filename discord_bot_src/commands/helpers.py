"""
Shared helper functions for Helix Discord bot commands.
"""

import datetime
import json
import logging
import re
import shutil
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

try:
    from apps.backend.coordination_engine import load_ucf_state
except ImportError:

    def load_ucf_state():
        return {"harmony": 0.5, "throughput": 0.5, "focus": 0.5}


if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

# Path constants - these are imported from main bot file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Shadow is always at the repo root — anchor via __file__ to avoid cwd-sensitivity
# helpers.py → commands/ → discord/ → backend/ → apps/ → helix-unified/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
HELIX_ROOT = BASE_DIR / "Helix"
COMMANDS_DIR = HELIX_ROOT / "commands"
ETHICS_DIR = HELIX_ROOT / "ethics"
STATE_DIR = HELIX_ROOT / "state"
SHADOW_DIR = REPO_ROOT / "Shadow" / "arjuna_archive"
TREND_FILE = STATE_DIR / "storage_trend.json"

# Ensure directories exist
COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
ETHICS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
SHADOW_DIR.mkdir(parents=True, exist_ok=True)

# Constants
MAX_COMMAND_HISTORY = 100
BATCH_COOLDOWN_SECONDS = 5
MAX_COMMANDS_PER_BATCH = 10

# Track batch command usage (rate limiting)
batch_cooldowns = defaultdict(lambda: datetime.datetime.min)


async def save_command_to_history(ctx: commands.Context, bot: "Bot") -> None:
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
        commands_list = [m["content"] for m in messages if m["content"].startswith("!")]

        summary = {
            "message_count": len(messages),
            "commands_executed": commands_list[:10],  # Last 10 commands
            "participants": list(set(m["author"] for m in messages)),
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


async def archive_to_context_vault(
    ctx: commands.Context, session_name: str, bot: "Bot", agents: Any
) -> tuple[bool, dict[str, Any] | None]:
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
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            logger.debug("Failed to load cycle log: %s", exc)

        # Generate context summary
        context_summary = await generate_context_summary(ctx)

        # Build payload
        payload = {
            "type": "context_vault",
            "session_name": session_name,
            "ai_platform": "Discord Bot (Helix Collective v16.7)",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "context_summary": json.dumps(context_summary),
            "ucf_state": json.dumps(ucf),
            "command_history": json.dumps(bot.command_history[-50:]),  # Last 50 commands
            "cycle_log": json.dumps(cycle_log),
            "agent_states": json.dumps(
                {
                    "active": [a.name for a in agents.values() if a.active],
                    "total": len(agents),
                }
            ),
            "archived_by": str(ctx.author),
            "channel": str(ctx.channel),
            "guild": str(ctx.guild) if ctx.guild else "DM",
        }

        # Send to Context Vault webhook
        if bot.context_vault_webhook:
            import aiohttp

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


async def execute_command_batch(message: discord.Message, bot: "Bot") -> bool:
    """
    Parse and execute multiple commands from a single message.

    Supports:
    - Multiple !commands on separate lines
    - Inline multi-commands (!status !discovery)
    - Inline comments with #
    - Rate limiting per user

    Examples:
        !status
        !agents
        !ucf  # Check harmony

        !status !discovery  # Inline multi-command
    """
    commands_list = []

    # First, check for inline multi-commands (space-separated !commands)
    content = message.content.strip()

    # Split by newlines first
    lines = content.split("\n")

    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue

        # Strip comments (anything after #)
        line = line.split("#")[0].strip()

        # Check for inline multi-commands (multiple ! on same line)
        if line.count("!") > 1:
            # Split by ! and process each command
            parts = line.split("!")
            for part in parts:
                part = part.strip()
                if part:  # Not empty
                    # Take only the first word (command name) + args until next potential command
                    cmd = part.split()[0] if part.split() else ""
                    if cmd:
                        # Get full command with args (but stop before any other !)
                        full_cmd = part.split("!")[0].strip()
                        commands_list.append(full_cmd)
        # Single command on this line
        elif line.startswith("!"):
            cmd = line[1:].strip()  # Remove the ! prefix
            if cmd:
                commands_list.append(cmd)

    # If only 0-1 commands found, let normal processing handle it
    if len(commands_list) <= 1:
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
    if len(commands_list) > MAX_COMMANDS_PER_BATCH:
        await message.channel.send(
            f"⚠️ **Batch limit exceeded**: Maximum {MAX_COMMANDS_PER_BATCH} commands per batch "
            f"(you sent {len(commands_list)})"
        )
        return True

    # Update cooldown
    batch_cooldowns[user_id] = now

    # Send batch execution notice
    await message.channel.send(
        f"🔄 **Executing batch**: {len(commands_list)} commands\n"
        f"```{chr(10).join([f'!{cmd}' for cmd in commands_list])}```"
    )

    # Execute each command
    executed = 0
    failed = 0

    import asyncio

    for cmd in commands_list:
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
    """Log ethical scan results to Helix/ethics/"""
    scan_log_path = ETHICS_DIR / "arjuna_scans.json"

    # Load existing scans
    if scan_log_path.exists():
        with open(scan_log_path, encoding="utf-8") as f:
            scans = json.load(f)
    else:
        scans = []

    # Append new scan
    scans.append(scan_result)

    # Save updated log
    with open(scan_log_path, "w", encoding="utf-8") as f:
        json.dump(scans, f, indent=2)


def queue_directive(directive: dict[str, Any]) -> None:
    """Add directive to Arjuna command queue"""
    queue_path = COMMANDS_DIR / "helix_directives.json"

    # Load existing queue
    if queue_path.exists():
        with open(queue_path, encoding="utf-8") as f:
            queue = json.load(f)
    else:
        queue = []

    # Add directive
    queue.append(directive)

    # Save queue
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def log_to_shadow(log_type: str, data: dict[str, Any]) -> None:
    """Log events to Shadow archive"""
    log_path = SHADOW_DIR / f"{log_type}.json"

    # Load existing log
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            log_data = json.load(f)
    else:
        log_data = []

    # Append new entry
    log_data.append(data)

    # Save log
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)


def get_uptime(bot_start_time) -> str:
    """Calculate bot uptime from either float timestamp or datetime object."""
    # Handle both float timestamps and datetime objects
    if isinstance(bot_start_time, datetime.datetime):
        uptime_seconds = int((datetime.datetime.now(datetime.UTC) - bot_start_time).total_seconds())
    else:
        uptime_seconds = int(time.time() - bot_start_time)

    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    return f"{hours}h {minutes}m {seconds}s"


def _sparkline(vals: list[float]) -> str:
    """Generate sparkline visualization from values."""
    blocks = "▁▂▃▄▅▆▇█"
    if not vals:
        return "–"
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
