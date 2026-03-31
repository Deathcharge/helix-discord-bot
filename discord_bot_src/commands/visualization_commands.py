"""
Visualization commands for Helix Discord bot.
"""

import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING

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


@commands.command(name="visualize", aliases=["visual", "render"])
async def visualize_command(ctx: commands.Context) -> None:
    """
    Generate and post Coordination coordination fractal visualization.

    Renders current UCF state as a Mandelbrot fractal and posts to Discord.
    Uses colors, velocity, and patterns influenced by harmony, throughput, and other metrics.

    Usage:
        !visualize
    """
    try:
        from apps.backend.discord.commands.helpers import log_to_shadow

        # Load current UCF state
        ucf_state = load_ucf_state()

        # Send initial message
        msg = await ctx.send("🎨 **Generating Coordination coordination fractal...**")

        # Generate and post visualization
        from apps.backend.fractal_renderer import generate_and_post_to_discord

        result = await generate_and_post_to_discord(ucf_state, ctx.channel)

        if result:
            # Update initial message with success
            await msg.edit(content="✅ **Coordination visualization complete!**")
        else:
            await msg.edit(content="❌ **Visualization failed** - check logs for details")

        # Log visualization event
        log_to_shadow(
            "coordination_events",
            {
                "action": "visualization",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "ucf_state": ucf_state,
                "success": result is not None,
                "user": str(ctx.author),
            },
        )

    except Exception as e:
        await ctx.send(f"❌ **Visualization error:** {e!s}")
        logger.error("Visualization command error: %s", e)
        import traceback

        traceback.print_exc()


@commands.command(name="icon")
@commands.has_permissions(administrator=True)
async def set_server_icon(ctx: commands.Context, mode: str = "info") -> None:
    """
    🎨 Set server icon - Cycle through Helix fractals.

    Modes:
        info    - Show current icon status
        helix   - Set to default Helix spiral 🌀
        fractal - Generate UCF-based fractal
        cycle   - Enable auto-cycling (24h)

    Usage:
        !icon           - Show status
        !icon helix     - Set to Helix logo
        !icon fractal   - Generate from current UCF state
        !icon cycle     - Enable auto-cycling
    """
    guild = ctx.guild

    if mode == "info":
        embed = discord.Embed(
            title="🎨 Server Icon Management",
            description="Current icon cycling status and available modes",
            color=0x00BFA5,
        )

        icon_url = str(guild.icon.url) if guild.icon else "No icon set"
        embed.add_field(
            name="Current Icon",
            value=f"[View Icon]({icon_url})" if guild.icon else "No icon set",
            inline=False,
        )

        embed.add_field(
            name="Available Modes",
            value="• `!icon helix` - Default Helix spiral 🌀\n"
            "• `!icon fractal` - UCF-based fractal generation\n"
            "• `!icon cycle` - Auto-rotate fractals every 24h",
            inline=False,
        )

        embed.set_thumbnail(url=icon_url if guild.icon else None)
        await ctx.send(embed=embed)

    elif mode == "helix":
        await ctx.send("🌀 **Setting Helix icon...**")
        icon_path = Path("assets/helix_icon.png")

        if icon_path.exists():
            with open(icon_path, "rb") as f:
                await guild.edit(icon=f.read())
            await ctx.send("✅ Server icon updated to Helix spiral!")
        else:
            await ctx.send(
                "❌ Helix icon file not found at `assets/helix_icon.png`\n💡 Add a PNG file to enable default icon"
            )

    elif mode == "fractal":
        await ctx.send(
            "🎨 **Generating UCF-based fractal icon...**\n🌀 *Using Grok Enhanced v2.0 - PIL-based Mandelbrot*"
        )

        try:
            ucf_state = load_ucf_state()

            # Generate fractal using Coordination bridge (matplotlib-based for icons)
            from apps.backend.fractal_renderer import generate_fractal_icon_bytes

            icon_bytes = await generate_fractal_icon_bytes(ucf_state=ucf_state, size=512)
            await guild.edit(icon=icon_bytes)
            ucf_summary = f"Harmony: {ucf_state.get('harmony', 0):.2f} | Throughput: {ucf_state.get('throughput', 0):.2f} | Focus: {ucf_state.get('focus', 0):.2f}"
            await ctx.send(
                f"✅ Server icon updated with UCF fractal!\n"
                f"🌀 **UCF State:** {ucf_summary}\n"
                f"🎨 **Colors:** Cyan→Gold (harmony), Green→Pink (throughput), Blue→Violet (focus)"
            )

        except ImportError as ie:
            await ctx.send(f"❌ Fractal generator not available: {ie!s}\n💡 Install Pillow: `pip install Pillow`")
        except Exception as e:
            await ctx.send(f"❌ Fractal generation failed: {e!s}")
            logger.error("Icon fractal generation failed: %s", e, exc_info=True)

    elif mode == "cycle":
        await ctx.send(
            "🔄 **Fractal Auto-Cycling Feature**\n"
            "💡 Auto-generates and rotates server icons based on UCF state every 24h.\n"
            "📋 **Status:** Planned for a future release. "
            "Use `!visualize fractal` for single-shot generation."
        )

    else:
        await ctx.send(f"❌ Unknown mode: `{mode}`\nUse: `info`, `helix`, `fractal`, or `cycle`")


async def setup(bot: "Bot") -> None:
    """Register visualization commands with the bot."""
    bot.add_command(visualize_command)
    bot.add_command(set_server_icon)
