"""
Dynamic Discord Channel Manager
Helix Collective v15.3

Allows the bot to dynamically create, modify, and delete channels based on:
- UCF state changes
- Agent activity
- Cycle execution
- User requests
- Automated cleanup

Usage:
    from discord_channel_manager import ChannelManager

    manager = ChannelManager(guild)
    await manager.create_optimization_space("harmony_boost")
    await manager.create_agent_workspace("Kael", "Ethics Review")
    await manager.cleanup_inactive_channels(days=7)
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import discord


class ChannelManager:
    """Manages dynamic channel creation and lifecycle."""

    def __init__(self, guild: discord.Guild, zapier_client=None):
        self.guild = guild
        self.zapier_client = zapier_client
        self.config_path = Path("config/dynamic_channels.json")
        self.load_config()

    def load_config(self):
        """Load dynamic channel configuration."""
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "optimization_spaces": {},
                "agent_workspaces": {},
                "temporary_channels": {},
                "auto_cleanup_days": 7,
            }
            self.save_config()

    def save_config(self):
        """Save dynamic channel configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    async def create_cycle_space(self, cycle_name: str, duration_hours: int = 24) -> discord.TextChannel:
        """
        Create a temporary channel for cycle execution.

        Args:
            cycle_name: Name of the cycle
            duration_hours: How long the channel should exist

        Returns:
            Created channel
        """
        # Find or create Cycle & Lore category
        category = discord.utils.get(self.guild.categories, name="🕉️ Cycle & Lore")
        if not category:
            category = await self.guild.create_category("🕉️ Cycle & Lore")

        # Create channel
        channel_name = "🔮│cycle-{}".format(cycle_name.lower().replace(" ", "-"))
        channel = await category.create_text_channel(
            name=channel_name,
            topic=f"Temporary cycle space for {cycle_name} · Auto-deletes in {duration_hours}h",
        )

        # Track for cleanup
        self.config["optimization_spaces"][str(channel.id)] = {
            "name": cycle_name,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=duration_hours)).isoformat(),
            "duration_hours": duration_hours,
        }
        self.save_config()

        # Send welcome message
        embed = discord.Embed(
            title=f"🔮 Cycle Space: {cycle_name}",
            description=f"This channel was created for cycle execution and will auto-delete in {duration_hours} hours.",
            color=discord.Color.purple(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(name="Duration", value=f"{duration_hours} hours", inline=True)
        embed.add_field(
            name="Auto-Delete",
            value=f"<t:{int((datetime.now(UTC) + timedelta(hours=duration_hours)).timestamp())}:R>",
            inline=True,
        )
        embed.set_footer(text="Use this space for cycle discussion and preparation")

        await channel.send(embed=embed)

        # Log to webhook
        if self.zapier_client:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Created: Cycle Space",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description=f"Created cycle space '{cycle_name}' ({channel.mention}) - expires in {duration_hours}h",
                    ucf_snapshot=json.dumps(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "category": category.name,
                            "cycle_name": cycle_name,
                            "duration_hours": duration_hours,
                            "expires_at": (datetime.now(UTC) + timedelta(hours=duration_hours)).isoformat(),
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in create_optimization_space: %s", webhook_error)

        return channel

    async def create_agent_workspace(
        self, agent_name: str, purpose: str, temporary: bool = False
    ) -> discord.TextChannel:
        """
        Create a workspace channel for an agent.

        Args:
            agent_name: Name of the agent (Kael, Lumina, etc.)
            purpose: Purpose of the workspace
            temporary: If True, channel will auto-delete after 7 days

        Returns:
            Created channel
        """
        # Find or create Agents category
        category = discord.utils.get(self.guild.categories, name="🤖 Agents")
        if not category:
            category = await self.guild.create_category("🤖 Agents")

        # Determine emoji based on agent
        agent_emojis = {
            "Kael": "🜂",
            "Lumina": "🌕",
            "Vega": "✨",
            "Aether": "🌌",
            "Arjuna": "🤲",
            "Gemini": "🎭",
            "Agni": "🔥",
            "Kavach": "🛡️",
            "SanghaCore": "🌸",
            "Shadow": "🕯️",
            "Coordination": "🔄",
        }

        emoji = agent_emojis.get(agent_name, "🤖")
        channel_name = "{}│{}-{}".format(emoji, agent_name.lower(), purpose.lower().replace(" ", "-"))

        # Create channel
        channel = await category.create_text_channel(
            name=channel_name,
            topic=f"{agent_name} workspace · {purpose}" + (" · Temporary" if temporary else ""),
        )

        # Track if temporary
        if temporary:
            self.config["agent_workspaces"][str(channel.id)] = {
                "agent": agent_name,
                "purpose": purpose,
                "created_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "temporary": True,
            }
            self.save_config()

        # Send welcome message
        embed = discord.Embed(
            title=f"{emoji} {agent_name} Workspace",
            description=f"**Purpose:** {purpose}",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )

        if temporary:
            embed.add_field(
                name="⏰ Temporary Channel",
                value="This workspace will auto-delete in 7 days if inactive",
                inline=False,
            )

        embed.set_footer(text=f"Managed by {agent_name}")

        await channel.send(embed=embed)

        # Log to webhook
        if self.zapier_client:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Created: Agent Workspace",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description="Created {} workspace ({}) - Purpose: {} {}".format(
                        agent_name,
                        channel.mention,
                        purpose,
                        "(temporary)" if temporary else "",
                    ),
                    ucf_snapshot=json.dumps(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "category": category.name,
                            "agent_name": agent_name,
                            "purpose": purpose,
                            "temporary": temporary,
                            "expires_at": ((datetime.now(UTC) + timedelta(days=7)).isoformat() if temporary else None),
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in create_agent_workspace: %s", webhook_error)

        return channel

    async def create_project_channel(self, project_name: str, description: str) -> discord.TextChannel:
        """
        Create a channel for a new project.

        Args:
            project_name: Name of the project
            description: Project description

        Returns:
            Created channel
        """
        # Find or create Projects category
        category = discord.utils.get(self.guild.categories, name="🔮 Projects")
        if not category:
            category = await self.guild.create_category("🔮 Projects")

        # Create channel
        channel_name = "📁│{}".format(project_name.lower().replace(" ", "-"))
        channel = await category.create_text_channel(name=channel_name, topic=description)

        # Send welcome message
        embed = discord.Embed(
            title=f"📁 New Project: {project_name}",
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(name="Status", value="🟢 Active", inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(datetime.now(UTC).timestamp())}:R>",
            inline=True,
        )
        embed.set_footer(text="Use this channel for project coordination")

        await channel.send(embed=embed)

        # Log to webhook
        if self.zapier_client:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Created: Project",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description=f"Created project channel '{project_name}' ({channel.mention}) - {description}",
                    ucf_snapshot=json.dumps(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "category": category.name,
                            "project_name": project_name,
                            "description": description,
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in create_project_channel: %s", webhook_error)

        return channel

    async def create_cross_ai_sync_channel(self, ai_names: list[str], purpose: str) -> discord.TextChannel:
        """
        Create a channel for cross-AI collaboration.

        Args:
            ai_names: List of AI names (GPT, Claude, Grok, etc.)
            purpose: Purpose of the collaboration

        Returns:
            Created channel
        """
        # Find or create Cross-Model Sync category
        category = discord.utils.get(self.guild.categories, name="🌐 Cross-Model Sync")
        if not category:
            category = await self.guild.create_category("🌐 Cross-Model Sync")

        # Create channel
        ai_string = "-".join([ai.lower() for ai in ai_names])
        channel_name = "🧩│{}-{}".format(ai_string, purpose.lower().replace(" ", "-"))

        channel = await category.create_text_channel(
            name=channel_name,
            topic="Cross-AI collaboration: {} · {}".format(", ".join(ai_names), purpose),
        )

        # Send welcome message
        embed = discord.Embed(
            title="🧩 Cross-AI Collaboration",
            description="**Participants:** {}\n**Purpose:** {}".format(", ".join(ai_names), purpose),
            color=discord.Color.gold(),
            timestamp=datetime.now(UTC),
        )
        embed.add_field(name="AIs Involved", value=str(len(ai_names)), inline=True)
        embed.add_field(name="Type", value="Collaborative Workspace", inline=True)
        embed.set_footer(text="Multi-AI coordination space")

        await channel.send(embed=embed)

        # Log to webhook
        if self.zapier_client:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Created: Cross-AI Sync",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description="Created cross-AI channel ({}) - AIs: {} - Purpose: {}".format(
                        channel.mention, ", ".join(ai_names), purpose
                    ),
                    ucf_snapshot=json.dumps(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "category": category.name,
                            "ai_names": ai_names,
                            "purpose": purpose,
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in create_cross_ai_sync_channel: %s", webhook_error)

        return channel

    async def cleanup_expired_channels(self) -> dict[str, int]:
        """
        Clean up expired temporary channels.

        Returns:
            Dict with cleanup statistics
        """
        now = datetime.now(UTC)
        deleted_count = {
            "optimization_spaces": 0,
            "agent_workspaces": 0,
            "temporary_channels": 0,
        }

        # Clean up cycle spaces
        for channel_id, data in list(self.config["optimization_spaces"].items()):
            expires_at = datetime.fromisoformat(data["expires_at"])
            if now >= expires_at:
                channel = self.guild.get_channel(int(channel_id))
                if channel:
                    await channel.delete(reason="Cycle space expired")
                    deleted_count["optimization_spaces"] += 1
                del self.config["optimization_spaces"][channel_id]

        # Clean up temporary agent workspaces
        for channel_id, data in list(self.config["agent_workspaces"].items()):
            if data.get("temporary"):
                expires_at = datetime.fromisoformat(data["expires_at"])
                if now >= expires_at:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.delete(reason="Temporary workspace expired")
                        deleted_count["agent_workspaces"] += 1
                    del self.config["agent_workspaces"][channel_id]

        self.save_config()

        # Log to webhook
        if self.zapier_client and sum(deleted_count.values()) > 0:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Cleanup: Expired Channels",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description="Cleaned up {} cycle spaces, {} workspaces, {} temporary channels".format(
                        deleted_count["optimization_spaces"],
                        deleted_count["agent_workspaces"],
                        deleted_count["temporary_channels"],
                    ),
                    ucf_snapshot=json.dumps(
                        {
                            "deleted_count": deleted_count,
                            "total_deleted": sum(deleted_count.values()),
                            "cleanup_type": "expired",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in cleanup_expired_channels: %s", webhook_error)

        return deleted_count

    async def cleanup_inactive_channels(self, days: int = 7) -> int:
        """
        Clean up channels with no activity for specified days.

        Args:
            days: Number of days of inactivity

        Returns:
            Number of channels deleted
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        deleted_count = 0

        # Check all text channels in dynamic categories
        dynamic_categories = ["🕉️ Cycle & Lore", "🤖 Agents", "🔮 Projects"]

        for category_name in dynamic_categories:
            category = discord.utils.get(self.guild.categories, name=category_name)
            if not category:
                continue

            for channel in category.text_channels:
                # Skip permanent channels
                if not channel.name.startswith(("🔮│cycle-", "📁│temp-")):
                    continue

                # Check last message
                try:
                    async for message in channel.history(limit=1):
                        if message.created_at < cutoff:
                            await channel.delete(reason=f"Inactive for {days} days")
                            deleted_count += 1
                            break
                    else:
                        # No messages at all
                        if channel.created_at < cutoff:
                            await channel.delete(reason=f"Empty and inactive for {days} days")
                            deleted_count += 1
                except (ValueError, TypeError, KeyError, IndexError) as e:
                    logger.debug("Failed to cleanup channel %s: %s", channel.name, e)

        # Log to webhook
        if self.zapier_client and deleted_count > 0:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Cleanup: Inactive Channels",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description=f"Cleaned up {deleted_count} inactive channels (inactive for {days}+ days)",
                    ucf_snapshot=json.dumps(
                        {
                            "deleted_count": deleted_count,
                            "inactivity_threshold_days": days,
                            "cleanup_type": "inactive",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in cleanup_inactive_channels: %s", webhook_error)

        return deleted_count

    async def archive_channel(self, channel: discord.TextChannel) -> discord.TextChannel:
        """
        Archive a channel by moving it to archive category and making read-only.

        Args:
            channel: Channel to archive

        Returns:
            Archived channel
        """
        # Find or create Archive category
        archive_category = discord.utils.get(self.guild.categories, name="📦 Archive")
        if not archive_category:
            archive_category = await self.guild.create_category("📦 Archive")

        # Move channel
        await channel.edit(category=archive_category)

        # Make read-only
        await channel.set_permissions(self.guild.default_role, send_messages=False, add_reactions=False)

        # Add archive prefix if not present
        if not channel.name.startswith("📦│"):
            await channel.edit(name=f"📦│{channel.name}")

        # Send archive notice
        embed = discord.Embed(
            title="📦 Channel Archived",
            description="This channel has been archived and is now read-only.",
            color=discord.Color.dark_gray(),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="Contact an admin to restore this channel")

        await channel.send(embed=embed)

        # Log to webhook
        if self.zapier_client:
            try:
                await self.zapier_client.log_event(
                    event_title="Channel Archived",
                    event_type="channel_lifecycle",
                    agent_name="ChannelManager",
                    description=f"Archived channel {channel.mention} (moved to {archive_category.name}, made read-only)",
                    ucf_snapshot=json.dumps(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "archive_category": archive_category.name,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                )
            except Exception as webhook_error:
                logger.error("⚠️ Zapier webhook error in archive_channel: %s", webhook_error)

        return channel

    def get_channel_stats(self) -> dict:
        """Get statistics about dynamic channels."""
        return {
            "optimization_spaces": len(self.config["optimization_spaces"]),
            "agent_workspaces": len(self.config["agent_workspaces"]),
            "temporary_channels": len(self.config["temporary_channels"]),
            "total_tracked": (
                len(self.config["optimization_spaces"])
                + len(self.config["agent_workspaces"])
                + len(self.config["temporary_channels"])
            ),
        }


# Bot command integration examples
"""
@bot.command(name="create_optimization_space")
@commands.has_role("Architect")
async def create_cycle_space_command(ctx, cycle_name: str, hours: int = 24):
    zapier_client = getattr(ctx.bot, 'zapier_client', None)
    manager = ChannelManager(ctx.guild, zapier_client=zapier_client)
    channel = await manager.create_optimization_space(cycle_name, hours)
    await ctx.send("✅ Created cycle space: {}".format(channel.mention))

@bot.command(name="create_agent_workspace")
@commands.has_role("Architect")
async def create_agent_workspace_command(ctx, agent_name: str, *, purpose: str):
    zapier_client = getattr(ctx.bot, 'zapier_client', None)
    manager = ChannelManager(ctx.guild, zapier_client=zapier_client)
    channel = await manager.create_agent_workspace(agent_name, purpose, temporary=True)
    await ctx.send("✅ Created workspace: {}".format(channel.mention))

@bot.command(name="cleanup_channels")
@commands.has_role("Architect")
async def cleanup_channels_command(ctx):
    zapier_client = getattr(ctx.bot, 'zapier_client', None)
    manager = ChannelManager(ctx.guild, zapier_client=zapier_client)
    stats = await manager.cleanup_expired_channels()
    await ctx.send("✅ Cleaned up {} expired channels".format(sum(stats.values())))
"""
import logging

logger = logging.getLogger(__name__)
