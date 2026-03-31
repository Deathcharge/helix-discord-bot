"""
Discord ↔ Web Chat Bridge - Bidirectional message routing.

Routes messages between Discord channels and web chat interface in real-time.
Enables unified communication across platforms.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class DiscordWebBridge:
    """Bridges Discord messages to web chat and vice versa."""

    def __init__(self, bot: commands.Bot, connection_manager=None):
        self.bot = bot
        self.connection_manager = connection_manager
        self.bridged_channels: dict[int, str] = {}  # channel_id -> web_chat_room
        self.enabled = True

    def set_connection_manager(self, manager):
        """Set the web chat connection manager."""
        self.connection_manager = manager
        if manager:
            manager.discord_bot = self.bot

    def add_bridged_channel(self, channel_id: int, room_name: str = "general"):
        """Add a Discord channel to bridge to web chat."""
        self.bridged_channels[channel_id] = room_name
        logger.info("🌉 Bridged Discord channel %s to web room '%s'", channel_id, room_name)

    def remove_bridged_channel(self, channel_id: int):
        """Remove a Discord channel from bridging."""
        if channel_id in self.bridged_channels:
            del self.bridged_channels[channel_id]
            logger.info("🌉 Removed bridge for Discord channel %s", channel_id)

    async def on_discord_message(self, message: discord.Message):
        """
        Handle incoming Discord message and forward to web chat.

        Called by Discord bot's on_message event.
        """
        # Ignore bot messages to prevent loops
        if message.author.bot:
            return

        # Check if this channel is bridged
        if message.channel.id not in self.bridged_channels:
            return

        if not self.connection_manager:
            return

        # Format message for web chat
        web_message = {
            "type": "discord_message",
            "username": message.author.display_name,
            "user_id": str(message.author.id),
            "avatar_url": str(message.author.display_avatar.url),
            "message": message.content,
            "channel": message.channel.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "attachments": [att.url for att in message.attachments],
            "embeds_count": len(message.embeds),
        }

        # Broadcast to all web chat users
        await self.connection_manager.broadcast(web_message)
        logger.debug("📡 Discord → Web: %s: %s...", message.author.name, message.content[:50])

    async def send_to_discord(
        self,
        channel_name: str,
        username: str,
        message: str,
        embed: discord.Embed | None = None,
    ) -> bool:
        """
        Send a message from web chat to Discord.

        Args:
            channel_name: Discord channel name (without #)
            username: Web chat username
            message: Message content
            embed: Optional Discord embed

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)

            if not channel:
                logger.warning("Discord channel #%s not found", channel_name)
                return False

            # Format message with web chat user attribution
            formatted_message = f"**[Web]** {username}: {message}"

            # Send to Discord
            if embed:
                await channel.send(formatted_message, embed=embed)
            else:
                await channel.send(formatted_message)

            logger.info("📡 Web → Discord: %s → #%s", username, channel_name)
            return True

        except discord.Forbidden:
            logger.error("No permission to send to #%s", channel_name)
            return False
        except Exception as e:
            logger.error("Error sending to Discord: %s", e, exc_info=True)
            return False

    async def send_cycle_notification(self, cycle_type: str, status: str, details: dict[str, Any]):
        """
        Send cycle notification to both Discord and web chat.

        Args:
            cycle_type: Type of cycle (daily, weekly, etc.)
            status: Status (started, completed, failed)
            details: Additional details dict
        """
        # Create embed
        color_map = {
            "started": 0xFFD700,  # Gold
            "completed": 0x00FF00,  # Green
            "failed": 0xFF0000,  # Red
        }

        embed = discord.Embed(
            title=f"🌀 Cycle {status.capitalize()}: {cycle_type.capitalize()}",
            description=details.get("description", f"{cycle_type} cycle {status}"),
            color=color_map.get(status, 0x5865F2),
            timestamp=datetime.now(UTC),
        )

        # Add fields from details
        if "ucf_boost" in details:
            embed.add_field(name="UCF Boost", value="+{}%".format(details["ucf_boost"]), inline=True)
        if "performance_score" in details:
            embed.add_field(
                name="Coordination",
                value="Level {}".format(details["performance_score"]),
                inline=True,
            )
        if "agents_involved" in details:
            embed.add_field(name="Agents", value=", ".join(details["agents_involved"]), inline=False)

        embed.set_footer(text="Helix Optimization Engine • Coordination Cycle")

        # Send to bridged Discord channels
        for channel_id in self.bridged_channels.keys():
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error("Error sending cycle notification to channel %s: %s", channel_id, e)

        # Send to web chat
        if self.connection_manager:
            await self.connection_manager.broadcast(
                {
                    "type": "cycle_notification",
                    "cycle_type": cycle_type,
                    "status": status,
                    "details": details,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    async def send_ucf_update(self, ucf_data: dict[str, Any]):
        """
        Broadcast UCF update to both Discord and web chat.

        Args:
            ucf_data: UCF state data dictionary
        """
        # Send to web chat (full data)
        if self.connection_manager:
            await self.connection_manager.broadcast(
                {
                    "type": "ucf_update",
                    "data": ucf_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        # Send to Discord (summary embed) only if significant change
        coherence = ucf_data.get("coherence", 0)

        # Only send to Discord if coherence crosses thresholds
        if coherence >= 95 or coherence <= 50:
            embed = discord.Embed(
                title="📊 UCF Coherence Alert",
                description=f"Unified Coordination Field coherence: **{coherence}%**",
                color=0x00FF00 if coherence >= 95 else 0xFF0000,
                timestamp=datetime.now(UTC),
            )

            embed.add_field(
                name="Status",
                value="OPTIMAL" if coherence >= 95 else "DEGRADED",
                inline=True,
            )
            embed.add_field(
                name="Active Agents",
                value=str(ucf_data.get("active_agents", 17)),
                inline=True,
            )
            embed.add_field(
                name="Coordination",
                value="Level {}".format(ucf_data.get("performance_score", 14)),
                inline=True,
            )

            # Send to telemetry channels
            for channel_id in self.bridged_channels.keys():
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel and "telemetry" in channel.name.lower():
                        await channel.send(embed=embed)
                except Exception as e:
                    logger.error("Error sending UCF update to channel %s: %s", channel_id, e)

    async def send_agent_message(self, agent_name: str, message: str, color: int = 0x5865F2):
        """
        Broadcast agent message to both Discord and web chat.

        Args:
            agent_name: Name of the agent
            message: Message content
            color: Embed color
        """
        # Send to web chat
        if self.connection_manager:
            await self.connection_manager.broadcast(
                {
                    "type": "agent_broadcast",
                    "agent": agent_name,
                    "message": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        # Send to Discord
        embed = discord.Embed(
            title=f"🤖 {agent_name}",
            description=message,
            color=color,
            timestamp=datetime.now(UTC),
        )

        for channel_id in self.bridged_channels.keys():
            try:
                channel = self.bot.get_channel(channel_id)
                if channel and "agent" in channel.name.lower():
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error("Error sending agent message to channel %s: %s", channel_id, e)


# Global bridge instance (will be initialized by bot)
discord_web_bridge: DiscordWebBridge | None = None


def get_bridge() -> DiscordWebBridge | None:
    """Get the global Discord-Web bridge instance."""
    return discord_web_bridge


def set_bridge(bridge: DiscordWebBridge):
    """Set the global Discord-Web bridge instance."""
    global discord_web_bridge
    discord_web_bridge = bridge
    logger.info("✅ Discord-Web bridge instance set")


# ============================================================================
# DISCORD BOT EVENT HANDLER
# ============================================================================


async def setup_bridge_events(bot: commands.Bot, connection_manager):
    """
    Setup Discord bot events for bridge integration.

    Should be called during bot initialization.
    """
    global discord_web_bridge

    # Create bridge
    discord_web_bridge = DiscordWebBridge(bot, connection_manager)

    # Auto-bridge common channels
    # These will be set up when bot is ready
    @bot.event
    async def on_ready():
        """Set up bridge channels when bot is ready."""
        if not discord_web_bridge:
            return

        # Find and bridge common channels
        for guild in bot.guilds:
            # Bridge general/chat channels
            general = discord.utils.get(guild.text_channels, name="general")
            if general:
                discord_web_bridge.add_bridged_channel(general.id, "general")

            # Bridge helix-chat if it exists
            helix_chat = discord.utils.get(guild.text_channels, name="helix-chat")
            if helix_chat:
                discord_web_bridge.add_bridged_channel(helix_chat.id, "helix")

            # Bridge web-chat if it exists
            web_chat = discord.utils.get(guild.text_channels, name="web-chat")
            if web_chat:
                discord_web_bridge.add_bridged_channel(web_chat.id, "general")

        logger.info("✅ Bridge auto-configured for %s channels", len(discord_web_bridge.bridged_channels))

    # Handle incoming Discord messages
    @bot.event
    async def on_message(message: discord.Message):
        """Forward Discord messages to web chat."""
        if discord_web_bridge:
            await discord_web_bridge.on_discord_message(message)

        # Important: Allow commands to still work
        await bot.process_commands(message)

    logger.info("✅ Discord-Web bridge events configured")


# ============================================================================
# ADMIN COMMANDS FOR BRIDGE MANAGEMENT
# ============================================================================


@commands.command(name="bridge-channel", aliases=["bridge"])
@commands.has_permissions(administrator=True)
async def bridge_channel_cmd(ctx: commands.Context, channel: discord.TextChannel = None, room: str = "general"):
    """
    🌉 Bridge a Discord channel to web chat.

    Messages in this channel will appear in web chat and vice versa.

    Usage:
        !bridge-channel #general
        !bridge-channel #helix-chat helix
    """
    target_channel = channel or ctx.channel

    if not discord_web_bridge:
        await ctx.send("❌ Discord-Web bridge not initialized!")
        return

    discord_web_bridge.add_bridged_channel(target_channel.id, room)

    embed = discord.Embed(
        title="🌉 Channel Bridged!",
        description=f"Messages in {target_channel.mention} will now appear in web chat room '{room}'",
        color=0x00FF00,
    )

    embed.add_field(name="Discord Channel", value=target_channel.mention, inline=True)
    embed.add_field(name="Web Chat Room", value=room, inline=True)
    embed.set_footer(text="Messages will flow both ways!")

    await ctx.send(embed=embed)


@commands.command(name="unbridge-channel", aliases=["unbridge"])
@commands.has_permissions(administrator=True)
async def unbridge_channel_cmd(ctx: commands.Context, channel: discord.TextChannel = None):
    """
    🌉 Remove bridge from a Discord channel.

    Usage:
        !unbridge-channel #general
    """
    target_channel = channel or ctx.channel

    if not discord_web_bridge:
        await ctx.send("❌ Discord-Web bridge not initialized!")
        return

    if target_channel.id not in discord_web_bridge.bridged_channels:
        await ctx.send(f"⚠️ {target_channel.mention} is not bridged!")
        return

    discord_web_bridge.remove_bridged_channel(target_channel.id)

    await ctx.send(f"✅ Removed bridge from {target_channel.mention}")


@commands.command(name="list-bridges", aliases=["bridges"])
@commands.has_permissions(administrator=True)
async def list_bridges_cmd(ctx: commands.Context):
    """
    🌉 List all bridged channels.

    Shows which Discord channels are connected to web chat.

    Usage: !list-bridges
    """
    if not discord_web_bridge:
        await ctx.send("❌ Discord-Web bridge not initialized!")
        return

    if not discord_web_bridge.bridged_channels:
        await ctx.send("📭 No channels are currently bridged to web chat.")
        return

    embed = discord.Embed(
        title="🌉 Bridged Channels",
        description=f"**{len(discord_web_bridge.bridged_channels)}** channel(s) connected to web chat:",
        color=0x5865F2,
    )

    for channel_id, room in discord_web_bridge.bridged_channels.items():
        channel = ctx.bot.get_channel(channel_id)
        if channel:
            embed.add_field(
                name=f"#{channel.name}",
                value=f"Web room: `{room}`\nChannel ID: `{channel_id}`",
                inline=False,
            )

    embed.set_footer(text="Use !bridge-channel to add more bridges")

    await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup bridge management commands."""
    bot.add_command(bridge_channel_cmd)
    bot.add_command(unbridge_channel_cmd)
    bot.add_command(list_bridges_cmd)
