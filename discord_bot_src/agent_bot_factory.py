"""
Agent Bot Factory — Create Discord Bot Instances Per Agent
==========================================================

Creates agent-specific discord.py Bot instances, each with its own:
- Discord Application token
- Agent personality (name, symbol, role, traits)
- Custom status message reflecting the agent's role
- Shared command set with agent-aware responses
- Optional agent-specific Cogs

Usage:
    from apps.backend.discord.agent_bot_factory import create_agent_bot

    bot = create_agent_bot("Kael")
    bot.run(token)

Each bot responds to the same commands but with the personality of its agent.
The factory pulls agent definitions from apps.backend.agents.AGENTS.

Author: Andrew John Ward (Architect)
Version: v1.0 Multi-Agent Discord
"""

import datetime
import logging
from typing import Any

import discord
from discord.ext import commands

from apps.backend.agents import AGENTS
from apps.backend.agents.agent_registry import AGENT_REGISTRY, get_discord_profiles
from apps.backend.helix_agent_swarm.agent_factory import AgentFactory

logger = logging.getLogger(__name__)


# Discord activity type mapping (registry stores strings, discord.py needs enums)
_ACTIVITY_TYPE_MAP = {
    "watching": discord.ActivityType.watching,
    "listening": discord.ActivityType.listening,
    "playing": discord.ActivityType.playing,
    "competing": discord.ActivityType.competing,
}


# Agent-specific Discord configuration — derived from unified agent_registry.py
# This is built once at import time from the single source of truth.
AGENT_DISCORD_PROFILES: dict[str, dict[str, Any]] = {}
for _name, _profile in get_discord_profiles().items():
    AGENT_DISCORD_PROFILES[_name] = {
        "status": _profile["status"],
        "activity_type": _ACTIVITY_TYPE_MAP.get(_profile["activity_type"], discord.ActivityType.playing),
        "color": _profile["color"],
        "prefix": _profile["prefix"],
        "fallback_prefix": _profile["fallback_prefix"],
    }

# Default profile for agents not in the registry
DEFAULT_DISCORD_PROFILE: dict[str, Any] = {
    "status": "Active in the Helix Collective",
    "activity_type": discord.ActivityType.playing,
    "color": 0x7B68EE,
    "prefix": "!",
    "fallback_prefix": "!",
}


def get_agent_profile(agent_name: str) -> dict[str, Any]:
    """Get the Discord profile for an agent, with fallback to defaults.

    Pulls identity data (symbol, role, traits) from the unified agent registry
    rather than the AGENTS dict, ensuring all 16 agents are fully described.
    """
    profile = AGENT_DISCORD_PROFILES.get(agent_name, DEFAULT_DISCORD_PROFILE).copy()

    # Pull identity from the unified registry (authoritative source)
    reg = AGENT_REGISTRY.get(agent_name)
    if reg is not None:
        profile["symbol"] = reg.get("symbol", "🌀")
        profile["role"] = reg.get("role", "Agent")
        profile["traits"] = reg.get("traits", [])
        profile["name"] = agent_name
    else:
        # Fallback: try the legacy AGENTS dict
        agent = AGENTS.get(agent_name)
        if agent is not None:
            profile["symbol"] = getattr(agent, "symbol", "🌀")
            profile["role"] = getattr(agent, "role", "Agent")
            profile["traits"] = getattr(agent, "traits", [])
            profile["name"] = agent_name
        else:
            profile["symbol"] = "🌀"
            profile["role"] = "Agent"
            profile["traits"] = []
            profile["name"] = agent_name

    return profile


def create_agent_bot(
    agent_name: str,
    *,
    command_prefix: str | None = None,
    shared_commands: bool = True,
) -> commands.Bot:
    """
    Create a Discord Bot instance configured for a specific agent.

    Parameters
    ----------
    agent_name : str
        Name of the agent (must match a key in AGENTS dict).
    command_prefix : str, optional
        Override the default command prefix. If None, uses the agent's
        configured prefix (e.g., "!kael ") with "!" as fallback.
    shared_commands : bool
        If True, registers the shared command set (status, agents, help, etc.)
        that all agent bots support. Default True.

    Returns
    -------
    commands.Bot
        A configured discord.py Bot instance ready to be run with a token.
    """
    profile = get_agent_profile(agent_name)

    # Determine prefix — agent-specific prefix + fallback "!" for common commands
    if command_prefix is not None:
        prefixes = [command_prefix, "!"]
    else:
        agent_prefix = profile.get("prefix", "!")
        prefixes = [agent_prefix, profile.get("fallback_prefix", "!")]

    # De-duplicate while preserving order
    seen = set()
    unique_prefixes = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            unique_prefixes.append(p)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    bot = commands.Bot(command_prefix=unique_prefixes, intents=intents)

    # Attach agent metadata to the bot instance
    bot.agent_name = agent_name
    bot.agent_profile = profile
    bot.agent_symbol = profile["symbol"]
    bot.agent_color = profile["color"]
    bot.start_time = None

    @bot.event
    async def on_ready():
        bot.start_time = datetime.datetime.now(datetime.UTC)
        logger.info(
            "%s %s bot connected as %s",
            profile["symbol"],
            agent_name,
            bot.user,
        )

        # Load memory & settings cog for persistent memory commands
        try:
            from apps.backend.discord.discord_memory_commands import MemoryCommandsCog

            if not bot.get_cog("Memory & Settings"):
                await bot.add_cog(MemoryCommandsCog(bot))
                logger.info("   %s loaded MemoryCommandsCog", agent_name)
        except Exception as cog_err:
            logger.warning(
                "   %s could not load MemoryCommandsCog: %s",
                agent_name,
                cog_err,
            )

        # Load autonomous behaviors cog (context-aware responses, reactions)
        try:
            from apps.backend.discord.discord_autonomous_behaviors import AutonomousBehaviorsCog

            if not bot.get_cog("Autonomous Behaviors"):
                await bot.add_cog(AutonomousBehaviorsCog(bot))
                logger.info("   %s loaded AutonomousBehaviorsCog", agent_name)
        except Exception as cog_err:
            logger.warning(
                "   %s could not load AutonomousBehaviorsCog: %s",
                agent_name,
                cog_err,
            )

        # Load agent swarm integration (multi-agent coordination)
        try:
            from apps.backend.discord.discord_agent_swarm_integration import AgentSwarmCog

            if not bot.get_cog("AgentSwarmCog"):
                await bot.add_cog(AgentSwarmCog(bot))
                logger.info("   %s loaded AgentSwarmCog", agent_name)
        except Exception as cog_err:
            logger.warning(
                "   %s could not load AgentSwarmCog: %s",
                agent_name,
                cog_err,
            )

        # Set agent-specific status
        activity = discord.Activity(
            type=profile["activity_type"],
            name=profile["status"],
        )
        await bot.change_presence(activity=activity)
        logger.info(
            "   %s status: %s %s",
            agent_name,
            profile["activity_type"].name,
            profile["status"],
        )

    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandNotFound):
            # Only respond to the agent's own prefix, ignore "!" misses silently
            # to avoid all bots responding to unknown commands
            if ctx.prefix and ctx.prefix.strip() != "!":
                await ctx.send(
                    f"{profile['symbol']} **{agent_name}**: I don't know that command. Try `{ctx.prefix}help`"
                )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"{profile['symbol']} **{agent_name}**: "
                f"Missing argument `{error.param.name}` — "
                f"usage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`"
            )

    if shared_commands:
        _register_shared_commands(bot, profile)

    return bot


def _register_shared_commands(bot: commands.Bot, profile: dict[str, Any]) -> None:
    """Register the shared command set that all agent bots support."""
    agent_name = profile["name"]
    symbol = profile["symbol"]
    color = profile["color"]

    @bot.command(name="whoami")
    async def whoami(ctx: commands.Context):
        """Show this agent's identity and role"""
        agent = AGENTS.get(agent_name)
        embed = discord.Embed(
            title=f"{symbol} {agent_name}",
            description=profile.get("role", "Helix Collective Agent"),
            color=color,
        )
        if profile.get("traits"):
            embed.add_field(
                name="Traits",
                value=", ".join(profile["traits"]),
                inline=False,
            )
        if agent is not None:
            embed.add_field(
                name="Status",
                value="🟢 Active" if getattr(agent, "active", False) else "🔴 Inactive",
                inline=True,
            )
            tier = getattr(agent, "current_tier", "core")
            embed.add_field(name="Tier", value=tier.title(), inline=True)
        embed.set_footer(text="Helix Collective — Tat Tvam Asi 🌀")
        await ctx.send(embed=embed)

    @bot.command(name="status")
    async def status(ctx: commands.Context):
        """Show this agent's current status"""
        uptime = "Unknown"
        if bot.start_time:
            delta = datetime.datetime.now(datetime.UTC) - bot.start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{hours}h {minutes}m {seconds}s"

        embed = discord.Embed(
            title=f"{symbol} {agent_name} — Status",
            color=color,
        )
        embed.add_field(name="Uptime", value=uptime, inline=True)
        embed.add_field(name="Latency", value=f"{bot.latency * 1000:.0f}ms", inline=True)
        embed.add_field(name="Guilds", value=str(len(bot.guilds)), inline=True)
        embed.set_footer(text="Helix Collective — Tat Tvam Asi 🌀")
        await ctx.send(embed=embed)

    @bot.command(name="agents")
    async def list_agents(ctx: commands.Context):
        """List all agents in the Helix Collective"""
        lines = []
        for name, agent in AGENTS.items():
            sym = getattr(agent, "symbol", "🌀")
            role = getattr(agent, "role", "Agent")
            active = "🟢" if getattr(agent, "active", False) else "🔴"
            marker = " ← **me**" if name == agent_name else ""
            lines.append(f"{active} {sym} **{name}** — {role}{marker}")

        embed = discord.Embed(
            title="🌀 Helix Collective — Agent Roster",
            description="\n".join(lines),
            color=0x7B68EE,
        )
        embed.set_footer(text=f"Responding as {agent_name} | {len(AGENTS)} agents total")
        await ctx.send(embed=embed)

    @bot.command(name="speak")
    async def speak(ctx: commands.Context, *, message: str):
        """Have this agent respond in character using its LLM personality.

        Features persistent memory — the agent remembers your past conversations
        across sessions and platforms. Use `!model` to change your preferred LLM.
        """
        # Show typing indicator while generating response
        async with ctx.typing():
            try:
                # Lazily create / retrieve the agent's conscious instance
                if not hasattr(bot, "_conscious_agent") or bot._conscious_agent is None:
                    try:
                        bot._conscious_agent = AgentFactory.create_agent_by_name(agent_name)
                        logger.info(
                            "%s Created HelixConsciousAgent for %s",
                            symbol,
                            agent_name,
                        )
                    except Exception as init_err:
                        logger.error(
                            "Failed to create agent %s: %s",
                            agent_name,
                            init_err,
                        )
                        bot._conscious_agent = None

                agent_instance = getattr(bot, "_conscious_agent", None)

                if agent_instance is not None:
                    # Pass discord_user_id to enable persistent memory threading
                    response_text = await agent_instance.process_message(
                        message=message,
                        sender=str(ctx.author),
                        context={
                            "channel": str(ctx.channel),
                            "channel_id": str(ctx.channel.id),
                            "guild": str(ctx.guild) if ctx.guild else "DM",
                            "guild_id": str(ctx.guild.id) if ctx.guild else None,
                            "platform": "discord",
                            "discord_user_id": str(ctx.author.id),
                        },
                    )

                    # Format the response in a nice embed
                    embed = discord.Embed(
                        description=response_text,
                        color=color,
                    )
                    embed.set_author(name="%s %s" % (symbol, agent_name))

                    # Show coordination level in footer
                    coordination = agent_instance.get_performance_score()
                    embed.set_footer(
                        text="Coordination: %.1f/10 | Tat Tvam Asi 🌀" % coordination,
                    )
                    await ctx.send(embed=embed)
                else:
                    # Graceful fallback when agent can't be created
                    embed = discord.Embed(
                        description=(
                            "*%s is currently offline.*\n\n"
                            "> %s\n\n"
                            "⚠️ Agent coordination could not be initialized. "
                            "Check that LLM API keys are configured."
                        )
                        % (agent_name, message),
                        color=color,
                    )
                    embed.set_author(name="%s %s" % (symbol, agent_name))
                    await ctx.send(embed=embed)

            except Exception as e:
                logger.error(
                    "%s !speak error for %s: %s",
                    symbol,
                    agent_name,
                    e,
                    exc_info=True,
                )
                await ctx.send(
                    "%s **%s**: I encountered an issue processing your message. "
                    "Please try again." % (symbol, agent_name)
                )

    @bot.command(name="ping")
    async def ping(ctx: commands.Context):
        """Check bot latency"""
        await ctx.send(f"{symbol} **{agent_name}** — Pong! `{bot.latency * 1000:.0f}ms`")
