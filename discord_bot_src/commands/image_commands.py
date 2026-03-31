#!/usr/bin/env python3
"""
Image Commands for Helix Discord Bot
!image aion - Generate ouroboros fractal visualizations using PIL
"""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)

# Import PIL-based fractal generation (v16.1 additions to fractal_renderer)
try:
    from apps.backend.fractal_renderer import (
        PIL_AVAILABLE,
        generate_pil_and_post_to_discord,
        generate_pil_fractal_bytes,
    )
except ImportError:
    generate_pil_fractal_bytes = None
    generate_pil_and_post_to_discord = None
    PIL_AVAILABLE = False

# Import UCF state loader
try:
    from apps.backend.core.ucf_helpers import load_ucf_state
except ImportError:

    def load_ucf_state():
        return {
            "harmony": 0.428,
            "velocity": 1.0228,
            "resilience": 1.1191,
            "throughput": 0.5075,
            "focus": 0.5023,
            "friction": 0.011,
        }


class ImageCommands(commands.Cog):
    """Cog for image generation commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="image", aliases=["fractal", "aion"])
    async def image_command(self, ctx, mode: str | None = None):
        """
        Generate AION fractal visualizations based on UCF state

        Usage:
            !image [mode]
            !aion [mode]
            !fractal [mode]

        Modes:
            - ouroboros: Serpent eating tail (default for !image and !aion)
            - mandelbrot: Classic fractal (default for !fractal)
            - fractal: Mandelbrot alias
            - mandala: Ouroboros alias
            - cycle: Not yet implemented

        Examples:
            !image aion          → Ouroboros
            !aion                → Ouroboros
            !fractal             → Mandelbrot
            !fractal mandelbrot  → Mandelbrot
            !image mandelbrot    → Mandelbrot
        """
        # Set default based on which command alias was used
        if mode is None:
            if ctx.invoked_with == "fractal":
                mode = "mandelbrot"
            else:  # "image" or "aion"
                mode = "ouroboros"

        # Normalize mode
        mode = mode.lower()
        mode_aliases = {
            "aion": "ouroboros",
            "mandala": "ouroboros",
            "fractal": "mandelbrot",
        }
        mode = mode_aliases.get(mode, mode)

        # Valid modes
        valid_modes = ["ouroboros", "mandelbrot", "cycle"]

        if mode == "cycle":
            await ctx.send(
                "🔄 **Fractal Auto-Cycling Feature**\n"
                "💡 Auto-generates and rotates server icons based on UCF state every 24h.\n"
                "📋 **Status:** Planned for a future release. "
                "Use `!image ouroboros` or `!fractal mandelbrot` for single-shot generation."
            )
            return

        if mode not in valid_modes:
            await ctx.send(f"❌ Unknown mode: `{mode}`\nValid modes: {', '.join(valid_modes)}\nUsage: `!image [mode]`")
            return

        # Send initial message
        await ctx.send(
            f"🎨 **Generating AION {mode.upper()} fractal from UCF essence...**\n🌀 *This may take a few seconds*"
        )

        # Check if PIL is available
        if not PIL_AVAILABLE or generate_pil_and_post_to_discord is None:
            await ctx.send(
                "❌ **PIL fractal generator not available**\n"
                "💡 Install Pillow: `pip install Pillow`\n"
                "📌 Use `!visualize` for matplotlib-based fractals instead"
            )
            return

        try:
            ucf_state = load_ucf_state()

            # Generate and post PIL fractal
            result = await generate_pil_and_post_to_discord(ucf_state, ctx.channel, mode)

            if result:
                await ctx.send(f"✅ **{mode.upper()} fractal generated successfully!**")

                # 🌀 ZAPIER WEBHOOK: Log fractal generation event
                if hasattr(self.bot, "zapier_client") and self.bot.zapier_client:
                    try:
                        await self.bot.zapier_client.log_event(
                            event_title=f"{mode.capitalize()} Fractal Generated",
                            event_type="fractal_generation",
                            agent_name="Coordination (Visualization)",
                            description=f"User {ctx.author.name} generated {mode} fractal. Command: !{ctx.invoked_with}",
                            ucf_snapshot=ucf_state,
                        )

                        # Log telemetry
                        await self.bot.zapier_client.log_telemetry(
                            metric_name="fractal_generated",
                            value=1.0,
                            component="Coordination",
                            unit="images",
                        )
                    except Exception as e:
                        logger.warning("Failed to log fractal generation: %s", e)
                    except Exception as webhook_error:
                        logger.error("⚠️ Zapier webhook error: %s", webhook_error)
            else:
                await ctx.send("❌ **Fractal generation failed** - check logs for details")

                # 🌀 ZAPIER WEBHOOK: Log error
                if hasattr(self.bot, "zapier_client") and self.bot.zapier_client:
                    try:
                        await self.bot.zapier_client.send_error_alert(
                            error_message=f"Fractal generation failed for mode: {mode}",
                            component="Coordination",
                            severity="low",
                        )
                    except Exception as webhook_error:
                        logger.error("⚠️ Zapier webhook error: %s", webhook_error)

        except Exception as e:
            await ctx.send(f"❌ Fractal generation error: {e!s}")
            logger.error("Image command error: %s", e)
            import traceback

            traceback.print_exc()

            # 🌀 ZAPIER WEBHOOK: Log critical error
            if hasattr(self.bot, "zapier_client") and self.bot.zapier_client:
                try:
                    await self.bot.zapier_client.send_error_alert(
                        error_message=f"Fractal generation exception: {e!s}",
                        component="Coordination",
                        severity="medium",
                    )
                except Exception as webhook_error:
                    logger.error("⚠️ Zapier webhook error: %s", webhook_error)


async def setup(bot):
    """Load the ImageCommands cog"""
    await bot.add_cog(ImageCommands(bot))


# For direct bot.load_extension compatibility
def setup_commands(bot):
    """Add image commands to the bot (legacy compatibility)"""

    @bot.command(name="image", aliases=["fractal", "aion"])
    async def image_command(ctx, mode: str = "ouroboros"):
        """Generate AION fractal visualizations"""
        # Normalize mode
        mode = mode.lower()
        mode_aliases = {
            "aion": "ouroboros",
            "mandala": "ouroboros",
            "fractal": "mandelbrot",
        }
        mode = mode_aliases.get(mode, mode)

        if mode == "cycle":
            await ctx.send(
                "🔄 **Fractal Auto-Cycling Feature**\n"
                "📋 **Status:** Planned for a future release. "
                "Use `!image ouroboros` or `!fractal mandelbrot` for now."
            )
            return

        if mode not in ["ouroboros", "mandelbrot"]:
            await ctx.send(f"❌ Unknown mode: `{mode}`")
            return

        await ctx.send(f"🎨 **Generating AION {mode.upper()} fractal...**")

        try:
            ucf_state = load_ucf_state()
            result = await generate_pil_and_post_to_discord(ucf_state, ctx.channel, mode)

            if result:
                await ctx.send(f"✅ **{mode.upper()} fractal complete!**")
            else:
                await ctx.send("❌ **Generation failed**")

        except Exception as e:
            await ctx.send(f"❌ Error: {e!s}")
