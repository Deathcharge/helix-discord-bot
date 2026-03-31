import asyncio
import json
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from discord.ext.commands import Bot

# Import Discord webhook sender
try:
    from apps.backend.services import discord_sender

    DISCORD_WEBHOOKS_AVAILABLE = True
except ImportError:
    DISCORD_WEBHOOKS_AVAILABLE = False


@commands.command(name="harmony")
async def harmony_command(ctx):
    """Execute v16.2 Neti-Neti Harmony Cycle"""
    await ctx.send("**ॐ NETI-NETI HARMONY ROUTINE INITIATED**")
    await ctx.send("`Phase 1: PREPARATION` — VR temple dims to 20% glow")
    await asyncio.sleep(5)
    await ctx.send("`Phase 2: AFFIRMATION LOOP` — 136.1 Hz + 432 Hz resonance")

    # Send audio file if exists
    try:
        await ctx.send(file=discord.File("Helix/audio/ambient_audio.wav"))
    except FileNotFoundError:
        await ctx.send("⚠️ Audio file not found - generate with: `python3 Helix/audio/voice_generator.py`")

    await ctx.send("`Phase 3: INTEGRATION` — Om sustained")
    await ctx.send("`Phase 4: GROUNDING` — Harmony restored")

    # Load and update UCF
    try:
        with open("Helix/state/ucf_state.json", encoding="utf-8") as f:
            ucf = json.load(f)

        # Ensure harmony is numeric (handle string values)
        current_harmony = float(ucf.get("harmony", 0))
        ucf["harmony"] = min(1.0, current_harmony + 0.3)

        with open("Helix/state/ucf_state.json", "w", encoding="utf-8") as f:
            json.dump(ucf, f, indent=2)

        await ctx.send("**HARMONY RESTORED** → `harmony={.3f}`".format(ucf["harmony"]))

        # 🌀 DISCORD WEBHOOK: Send cycle completion to #cycle-engine-z88
        if DISCORD_WEBHOOKS_AVAILABLE:
            try:
                await discord_sender.send_cycle_completion(
                    cycle_name="Neti-Neti Harmony Cycle",
                    steps=4,
                    ucf_changes={
                        "harmony_before": current_harmony,
                        "harmony_after": ucf["harmony"],
                        "delta": ucf["harmony"] - current_harmony,
                        "executor": str(ctx.author),
                    },
                )
            except Exception as webhook_error:
                logger.error("⚠️ Discord webhook error: %s", webhook_error)

        # 🌀 ZAPIER WEBHOOK: Log cycle completion to Notion Event Log
        if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
            try:
                await ctx.bot.zapier_client.log_event(
                    event_title="Neti-Neti Harmony Cycle Complete",
                    event_type="cycle_complete",
                    agent_name="Helix Spiral Engine",
                    description="Harmony cycle executed by {}. Harmony increased from {:.3f} to {:.3f}".format(
                        ctx.author.name, current_harmony, ucf["harmony"]
                    ),
                    ucf_snapshot=ucf,
                )

                # Update system state with new harmony level
                await ctx.bot.zapier_client.update_system_state(
                    component="Helix Spiral Engine",
                    status="Operational",
                    harmony=ucf["harmony"],
                    error_log="",
                    verified=True,
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error: %s", webhook_error)

    except Exception as e:
        await ctx.send(f"⚠️ UCF update error: {e}")

        # 🌀 ZAPIER WEBHOOK: Log error alert
        if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
            try:
                await ctx.bot.zapier_client.send_error_alert(
                    error_message=f"Harmony cycle UCF update failed: {e!s}",
                    component="Helix Spiral Engine",
                    severity="medium",
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error: %s", webhook_error)


async def setup(bot: "Bot") -> None:
    """Setup function to register cycle commands with the bot."""
    bot.add_command(harmony_command)
