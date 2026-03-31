#!/usr/bin/env python3
"""
🌀 Helix Collective v17.2 — Portal Deployment Commands
bot/commands/portal_deployment_commands.py

Portal deployment commands for Discord bot:
- !deploy <target> — Deploy portals (all, core, agents, coordination, system)
- !portal status — Check portal deployment status
- !portal list — List all 51 portals
- !join — Join voice channel for voice commands
- !leave — Leave voice channel

Integrates with the 51-portal orchestration system.

Author: Helix Collective / Arjuna AI
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class PortalDeploymentCommands(commands.Cog):
    """Portal deployment and orchestration commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize portal deployment commands cog."""
        self.bot = bot
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.portal_config_path = self.base_dir / "portal-orchestrator" / "config" / "51-portals-complete.json"
        self.portal_script_path = self.base_dir / "portal-orchestrator" / "scripts" / "generate-portal.js"

        # Load portal configuration
        self.portals = self._load_portal_config()

    def _load_portal_config(self) -> dict[str, Any]:
        """Load the 51-portal configuration."""
        if self.portal_config_path.exists():
            try:
                with open(self.portal_config_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load portal config: %s", e)

        # Fallback: basic portal structure
        return {
            "core": [],
            "agents": [],
            "coordination": [],
            "system": [],
            "total": 51,
        }

    def _parse_portal_command(self, text: str) -> dict[str, Any] | None:
        """Parse voice/text command for portal deployment."""
        text = text.lower().strip()

        if "deploy" in text or "create" in text:
            if "all" in text or "everything" in text or "51" in text:
                return {
                    "action": "deploy",
                    "target": "all",
                    "message": "Deploying all 51 portals",
                }

            if "core" in text:
                return {
                    "action": "deploy",
                    "target": "core",
                    "message": "Deploying 12 core infrastructure portals",
                }

            if "agent" in text or "ai" in text:
                return {
                    "action": "deploy",
                    "target": "agents",
                    "message": "Deploying 17 AI agent portals",
                }

            if "coordination" in text or "awareness" in text:
                return {
                    "action": "deploy",
                    "target": "coordination",
                    "message": "Deploying 17 coordination portals",
                }

            if "system" in text:
                return {
                    "action": "deploy",
                    "target": "system",
                    "message": "Deploying 6 system portals",
                }

        if "status" in text or "check" in text:
            return {"action": "status", "message": "Checking portal deployment status"}

        return None

    async def _execute_portal_deployment(self, command: dict[str, Any]) -> dict[str, Any]:
        """Execute portal deployment command."""
        try:
            if not self.portal_script_path.exists():
                return {
                    "success": False,
                    "message": "Portal orchestrator script not found",
                    "details": f"Expected at: {self.portal_script_path}",
                }

            # Build command arguments
            args = ["node", str(self.portal_script_path)]

            if command["target"] == "all":
                args.append("--all")
            elif command["target"] in ["core", "agents", "coordination", "system"]:
                args.extend(["--type", command["target"]])
            else:
                return {"success": False, "message": "Unknown deployment target"}

            # Execute deployment
            logger.info("Executing portal deployment: %s", " ".join(args))

            result = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir),
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=60.0)

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": command["message"],
                    "details": stdout.decode("utf-8") if stdout else None,
                }
            else:
                return {
                    "success": False,
                    "message": "Deployment command failed",
                    "details": stderr.decode("utf-8") if stderr else None,
                }

        except TimeoutError:
            return {
                "success": False,
                "message": "Deployment command timed out (60s limit)",
            }
        except Exception as e:
            logger.error("Portal deployment error: %s", e)
            return {"success": False, "message": f"Deployment failed: {e!s}"}

    async def _get_portal_status(self) -> dict[str, Any]:
        """Get current portal deployment status."""
        try:
            if not self.portal_script_path.exists():
                return {
                    "success": False,
                    "message": "Portal orchestrator script not found",
                }

            result = await asyncio.create_subprocess_exec(
                "node",
                str(self.portal_script_path),
                "--status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir),
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10.0)

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Portal status retrieved",
                    "details": stdout.decode("utf-8") if stdout else None,
                }
            else:
                return {
                    "success": False,
                    "message": "Status check failed",
                    "details": stderr.decode("utf-8") if stderr else None,
                }

        except Exception as e:
            logger.error("Portal status error: %s", e)
            return {
                "success": False,
                "message": f"Status check failed: {e!s}",
            }

    @commands.command(name="deploy-portal", help="Deploy portals (all, core, agents, coordination, system)")
    async def deploy_portal(self, ctx: commands.Context, *, target: str = "help"):
        """Deploy portals via text command."""

        # Show help if no target specified
        if target == "help":
            embed = discord.Embed(
                title="🚀 Portal Deployment Commands",
                description="Deploy and manage the 51-portal constellation",
                color=discord.Color.purple(),
                timestamp=datetime.now(UTC),
            )

            embed.add_field(
                name="Deploy All Portals",
                value="`!deploy all` - Deploy all 51 portals",
                inline=False,
            )
            embed.add_field(
                name="Deploy by Category",
                value=(
                    "`!deploy core` - Deploy 12 core infrastructure portals\n"
                    "`!deploy agents` - Deploy 17 AI agent portals\n"
                    "`!deploy coordination` - Deploy 17 coordination portals\n"
                    "`!deploy system` - Deploy 6 system portals"
                ),
                inline=False,
            )
            embed.add_field(
                name="Check Status",
                value="`!portal status` - Check deployment status",
                inline=False,
            )

            embed.set_footer(text="Helix Collective v17.2 | Portal Orchestration")

            await ctx.send(embed=embed)
            return

        # Parse command
        command = self._parse_portal_command(target)

        if not command:
            await ctx.send("❓ I didn't understand that command. Use `!deploy help` for available commands.")
            return

        # Send initial message
        msg = await ctx.send("⏳ {}...".format(command["message"]))

        # Execute deployment
        result = await self._execute_portal_deployment(command)

        # Update message with result
        if result["success"]:
            response = "✅ {}".format(result["message"])
            if result.get("details"):
                details = result["details"][:1900]  # Discord message limit
                response += f"\n```\n{details}\n```"
            await msg.edit(content=response)
        else:
            await msg.edit(content="❌ {}".format(result["message"]))
            if result.get("details"):
                details = result["details"][:1900]
                await ctx.send(f"```\n{details}\n```")

    @commands.group(name="portal", help="Portal management commands")
    async def portal(self, ctx: commands.Context):
        """Portal management command group."""
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "**🌀 Portal Commands**\n"
                "`!portal status` - Check deployment status\n"
                "`!portal list` - List all 51 portals\n"
                "`!deploy <target>` - Deploy portals"
            )

    @portal.command(name="status", help="Check portal deployment status")
    async def portal_status(self, ctx: commands.Context):
        """Check portal deployment status."""
        msg = await ctx.send("⏳ Checking portal status...")

        result = await self._get_portal_status()

        if result["success"]:
            embed = discord.Embed(
                title="📊 Portal Deployment Status",
                description="Current status of the 51-portal constellation",
                color=discord.Color.green(),
                timestamp=datetime.now(UTC),
            )

            if result.get("details"):
                # Parse status details
                details = result["details"]
                embed.add_field(
                    name="Status Details",
                    value=f"```\n{details[:1000]}\n```",
                    inline=False,
                )

            embed.set_footer(text="Helix Collective v17.2 | Portal Orchestration")

            await msg.edit(content=None, embed=embed)
        else:
            await msg.edit(content="❌ {}".format(result["message"]))

    @portal.command(name="list", help="List all 51 portals")
    async def portal_list(self, ctx: commands.Context):
        """List all 51 portals."""
        embed = discord.Embed(
            title="🌌 51-Portal Constellation",
            description="Complete portal inventory",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )

        # Add portal categories
        if isinstance(self.portals, dict):
            for category, portals in self.portals.items():
                if category == "total":
                    continue

                if isinstance(portals, list) and portals:
                    portal_names = [
                        (p.get("name", p.get("id", "Unknown")) if isinstance(p, dict) else str(p)) for p in portals[:5]
                    ]
                    count = len(portals)

                    embed.add_field(
                        name=f"{category.title()} Portals ({count})",
                        value="\n".join([f"• {name}" for name in portal_names])
                        + (f"\n... and {count - 5} more" if count > 5 else ""),
                        inline=False,
                    )

        embed.add_field(
            name="Total Portals",
            value="**{}** portals in constellation".format(self.portals.get("total", 51)),
            inline=False,
        )

        embed.set_footer(text="Helix Collective v17.2 | Portal Orchestration")

        await ctx.send(embed=embed)

    @commands.command(name="join", help="Join voice channel for voice commands")
    async def join_voice(self, ctx: commands.Context):
        """Join the voice channel."""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel first!")
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        await ctx.send(f"🎤 Joined {channel.name}! Ready to listen for voice commands.")

    @commands.command(name="leave", help="Leave voice channel")
    async def leave_voice(self, ctx: commands.Context):
        """Leave the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left voice channel")
        else:
            await ctx.send("❌ I'm not in a voice channel")


async def setup(bot: commands.Bot):
    """Load the portal deployment commands cog."""
    await bot.add_cog(PortalDeploymentCommands(bot))
    logger.info("✅ Portal Deployment Commands cog loaded")
