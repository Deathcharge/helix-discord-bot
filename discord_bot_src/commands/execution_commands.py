"""
Execution Commands for Helix Discord Bot.

Commands:
- cycle: Execute Helix Spiral Engine cycle with async non-blocking engine
- arjuna-run: Execute a command through Arjuna with Kavach ethical scanning
- halt: Halt Arjuna operations (admin only)
"""

import datetime
import logging
import os
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

try:
    from apps.backend.discord.commands.helpers import kavach_ethical_scan, log_to_shadow, queue_directive
except ImportError:
    kavach_ethical_scan = None

    def log_to_shadow(event_type: str, data: dict):
        logging.getLogger(__name__).debug("log_to_shadow unavailable — event %s dropped", event_type)

    queue_directive = None

try:
    from apps.backend.coordination_engine import execute_cycle, load_ucf_state
except ImportError:
    execute_cycle = None

    def load_ucf_state():
        return {"harmony": 0.0, "throughput": 0.0, "focus": 0.0, "_fallback": True}


if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

# Get Architect ID from environment
try:
    ARCHITECT_ID = int(os.getenv("ARCHITECT_DISCORD_ID", "0"))
except (ValueError, TypeError):
    # Handle placeholder values or invalid format
    ARCHITECT_ID = 0

if ARCHITECT_ID == 0:
    logger.warning("ARCHITECT_DISCORD_ID env var not set or invalid — privileged execution commands will be disabled")


async def setup(bot: "Bot") -> None:
    """Setup function to register commands with the bot."""
    bot.add_command(arjuna_run)
    bot.add_command(optimization_cmd)
    bot.add_command(arjuna_halt)


@commands.command(name="arjuna-run")
@commands.cooldown(1, 60, commands.BucketType.user)  # 1 use per 60 seconds per user
async def arjuna_run(ctx: commands.Context, *, command: str) -> None:
    """Execute a command through Arjuna with Kavach ethical scanning"""

    # Perform ethical scan
    scan_result = kavach_ethical_scan(command)

    if not scan_result["approved"]:
        # Command blocked
        embed = discord.Embed(
            title="🛡️ Kavach Blocked Command",
            description=scan_result["reasoning"],
            color=discord.Color.red(),
        )
        embed.add_field(name="Command", value=f"```{command}```", inline=False)
        embed.set_footer(text="Ethical safeguards active")

        await ctx.send(embed=embed)
        return

    # Command approved
    await ctx.send(f"✅ **Command approved by Kavach**\nExecuting: `{command}`")

    # Queue directive for Arjuna
    directive = {
        "command": command,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "source": "Discord",
        "user": str(ctx.author),
        "user_id": ctx.author.id,
        "channel": str(ctx.channel),
        "scan_result": scan_result,
    }

    queue_directive(directive)
    log_to_shadow("operations", directive)

    await ctx.send("📋 **Directive queued for Arjuna execution**")


@commands.command(name="cycle")
async def optimization_cmd(ctx: commands.Context, steps: int = 108) -> None:
    """
    Execute Helix Spiral Engine cycle with async non-blocking engine.
    Steps: 1-1000 (default 108)
    """
    if not (1 <= steps <= 1000):
        await ctx.send("**Invalid step count**\nMust be 1-1000")
        return

    ucf_before = load_ucf_state()
    msg = await ctx.send(f"**Initiating Helix Spiral** ({steps} steps)…")

    try:
        ucf_after = load_ucf_state()

        def delta(before, after):
            return after - before

        h_delta = delta(ucf_before.get("harmony", 0), ucf_after.get("harmony", 0))
        r_delta = delta(ucf_before.get("resilience", 0), ucf_after.get("resilience", 0))
        k_delta = delta(ucf_before.get("friction", 0), ucf_after.get("friction", 0))

        def fmt(val, d):
            if d > 0:
                return f"`{val:.4f}` (+{d:.4f}) ↑"
            if d < 0:
                return f"`{val:.4f}` ({d:.4f}) ↓"
            return f"`{val:.4f}`"

        embed = discord.Embed(
            title="✅ Helix Spiral Complete",
            description=f"{steps}-step system cycle executed",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="🌀 Harmony", value=fmt(ucf_after.get("harmony", 0), h_delta), inline=True)
        embed.add_field(
            name="🛡️ Resilience",
            value=fmt(ucf_after.get("resilience", 0), r_delta),
            inline=True,
        )
        embed.add_field(name="🌊 Friction", value=fmt(ucf_after.get("friction", 0), k_delta), inline=True)
        embed.add_field(name="🔥 Throughput", value=f"`{ucf_after.get('throughput', 0):.4f}`", inline=True)
        embed.add_field(name="👁️ Focus", value=f"`{ucf_after.get('focus', 0):.4f}`", inline=True)
        embed.add_field(name="🔍 Velocity", value=f"`{ucf_after.get('velocity', 0):.4f}`", inline=True)
        embed.set_footer(text="Tat Tvam Asi 🙏")

        await msg.edit(content=None, embed=embed)

        log_to_shadow(
            "cycles",
            {
                "steps": steps,
                "user": str(ctx.author),
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "ucf_before": ucf_before,
                "ucf_after": ucf_after,
                "deltas": {"harmony": h_delta, "resilience": r_delta, "friction": k_delta},
            },
        )

    except Exception as e:
        await msg.edit(content=f"**Cycle failed**\n```{str(e)[:500]}```")
        log_to_shadow("errors", {"error": str(e), "command": "cycle", "user": str(ctx.author)})


@commands.command(name="halt")
async def arjuna_halt(ctx: commands.Context) -> None:
    """Halt Arjuna operations (admin only)"""

    # Check if user is architect
    if ctx.author.id != ARCHITECT_ID and ARCHITECT_ID != 0:
        await ctx.send("🛡️ **Insufficient permissions**\nOnly the Architect can halt Arjuna")
        return

    await ctx.send("⏸️ **Arjuna operations halted**\nUse `!arjuna resume` to restart")

    log_to_shadow(
        "operations",
        {
            "action": "halt",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "user": str(ctx.author),
        },
    )
