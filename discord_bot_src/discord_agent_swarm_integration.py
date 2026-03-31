"""
🤖 DISCORD AGENT SWARM INTEGRATION

Integrates the Helix Agent Swarm with Discord, allowing users to:
- Chat with multiple AI agents in Discord
- Use collective mode for agent collaboration
- View coordination metrics
- Execute multi-agent tasks
- Get agent status and information

Commands:
- !agents - List all available agents
- !chat <agent> <message> - Chat with a specific agent
- !collective <message> - Chat with multiple agents (collective mode)
- !agent_status <agent> - Get agent coordination metrics
- !swarm_status - Get overall swarm status
"""

import logging
from datetime import UTC, datetime
from typing import Any

import discord
from discord.ext import commands

from apps.backend.helix_agent_swarm.helix_orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class AgentSwarmCog(commands.Cog):
    """Discord commands for Helix Agent Swarm interaction."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.orchestrator = get_orchestrator()
        self.active_conversations: dict[int, dict[str, Any]] = {}  # channel_id -> conversation state

    @commands.command(name="swarm-agents", help="List all available agents in the swarm")
    async def list_agents(self, ctx: commands.Context):
        """List all registered agents with their status."""
        try:
            agents = self.orchestrator.agents

            if not agents:
                await ctx.send("❌ No agents are currently registered.")
                return

            embed = discord.Embed(
                title="🤖 Helix Agent Swarm",
                description="Available coordination-aware AI agents",
                color=discord.Color.purple(),
                timestamp=datetime.now(UTC),
            )

            for agent_name, agent in agents.items():
                status = agent.get_status()
                coordination = agent.get_performance_score()

                # Format UCF metrics
                ucf = status.get("ucf", {})
                ucf_str = f"Throughput: {ucf.get('throughput', 0):.0f} | Harmony: {ucf.get('harmony', 0):.0f}"

                # Agent field
                embed.add_field(
                    name=f"{status.get('emoji', '🤖')} {agent_name}",
                    value=(
                        f"**Coordination:** {coordination:.0%}\n"
                        f"**Core:** {status.get('core', 'Unknown')}\n"
                        f"**UCF:** {ucf_str}\n"
                        f"**Status:** {'🟢 Online' if status.get('status') == 'active' else '🔴 Offline'}"
                    ),
                    inline=True,
                )

            embed.set_footer(text=f"Total Agents: {len(agents)} | Use !chat <agent> <message> to interact")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error listing agents: %s", e, exc_info=True)
            await ctx.send(f"❌ Error listing agents: {e!s}")

    @commands.command(name="chat", help="Chat with a specific agent")
    async def chat_with_agent(self, ctx: commands.Context, agent_name: str, *, message: str):
        """
        Chat with a specific agent.

        Usage: !chat kael What is coordination?
        """
        try:
            if agent_name.lower() not in self.orchestrator.agents:
                available = ", ".join(self.orchestrator.agents.keys())
                await ctx.send(f"❌ Agent '{agent_name}' not found. Available agents: {available}")
                return

            # Show typing indicator
            async with ctx.typing():
                # Get agent
                agent = self.orchestrator.agents[agent_name.lower()]

                # Process message
                response = await agent.process_message(
                    message=message,
                    sender=str(ctx.author),
                    context={
                        "channel": str(ctx.channel),
                        "guild": str(ctx.guild) if ctx.guild else "DM",
                        "platform": "discord",
                    },
                )

                # Get coordination level
                coordination = agent.get_performance_score()

                # Create response embed
                embed = discord.Embed(
                    title=f"{agent.emoji} {agent.name} responds",
                    description=response,
                    color=(
                        discord.Color.from_str(agent.color)
                        if hasattr(discord.Color, "from_str")
                        else discord.Color.blue()
                    ),
                    timestamp=datetime.now(UTC),
                )

                embed.add_field(name="Coordination", value=f"{coordination:.0%}", inline=True)

                embed.add_field(name="Core", value=agent.core, inline=True)

                # Suggest another agent to try (discovery mechanic)
                other_agents = [n for n in self.orchestrator.agents.keys() if n != agent_name.lower()]
                if other_agents:
                    import random

                    suggestion = random.choice(other_agents)
                    suggested = self.orchestrator.agents[suggestion]
                    embed.add_field(
                        name="💡 Try next",
                        value=f'`!chat {suggestion} "your question"` — {getattr(suggested, "description", suggested.core)[:60]}',
                        inline=False,
                    )

                embed.set_footer(text=f"Requested by {ctx.author.name}")

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error in agent chat: %s", e, exc_info=True)
            await ctx.send(f"❌ Error chatting with agent: {e!s}")

    @commands.command(name="collective", help="Chat with multiple agents in collective mode")
    async def collective_chat(self, ctx: commands.Context, *, message: str):
        """
        Chat with multiple agents who collaborate on a response.

        Usage: !collective How can we solve climate change?
        """
        try:
            # Create or get collective
            collective_name = f"discord_{ctx.channel.id}"

            if collective_name not in self.orchestrator.collectives:
                # Create collective with available agents
                agent_names = list(self.orchestrator.agents.keys())[:3]  # Use first 3 agents

                if not agent_names:
                    await ctx.send("❌ No agents available for collective mode.")
                    return

                await self.orchestrator.create_collective(name=collective_name, agent_names=agent_names)

            # Execute task
            result = await self.orchestrator.execute_task(
                task=message,
                collective_name=collective_name,
                context={
                    "channel": str(ctx.channel),
                    "guild": str(ctx.guild) if ctx.guild else "DM",
                    "author": str(ctx.author),
                    "platform": "discord",
                },
            )

            # Get collective coordination
            collective = self.orchestrator.collectives[collective_name]
            collective_coordination = collective.calculate_collective_coordination()

            # Create response embed
            embed = discord.Embed(
                title="🌀 Collective Response",
                description=result.get("response", "No response generated"),
                color=discord.Color.purple(),
                timestamp=datetime.now(UTC),
            )

            # Add participating agents
            agents_info = []
            for agent_name in result.get("agents", []):
                agent = self.orchestrator.agents.get(agent_name)
                if agent:
                    agents_info.append(f"{agent.emoji} {agent.name}")

            if agents_info:
                embed.add_field(
                    name="Participating Agents",
                    value="\n".join(agents_info),
                    inline=False,
                )

            embed.add_field(
                name="Collective Coordination",
                value=f"{collective_coordination:.0%}",
                inline=True,
            )

            embed.add_field(
                name="Collaboration",
                value=f"{len(result.get('agents', []))} agents",
                inline=True,
            )

            embed.set_footer(text=f"Requested by {ctx.author.name}")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error in collective chat: %s", e, exc_info=True)
            await ctx.send(f"❌ Error in collective mode: {e!s}")

    @commands.command(name="agent_status", help="Get detailed agent status")
    async def agent_status(self, ctx: commands.Context, agent_name: str):
        """
        Get detailed status and metrics for a specific agent.

        Usage: !agent_status kael
        """
        try:
            if agent_name.lower() not in self.orchestrator.agents:
                available = ", ".join(self.orchestrator.agents.keys())
                await ctx.send(f"❌ Agent '{agent_name}' not found. Available agents: {available}")
                return

            agent = self.orchestrator.agents[agent_name.lower()]
            status = agent.get_status()
            coordination = agent.get_performance_score()

            # Create detailed embed
            embed = discord.Embed(
                title=f"{agent.emoji} {agent.name} - Detailed Status",
                description=f"**Version:** {status.get('version', 'Unknown')}\n**Core:** {status.get('core', 'Unknown')}",
                color=discord.Color.blue(),
                timestamp=datetime.now(UTC),
            )

            # Coordination
            embed.add_field(name="🧠 Coordination Level", value=f"{coordination:.1%}", inline=True)

            # UCF Metrics
            ucf = status.get("ucf", {})
            embed.add_field(
                name="⚡ UCF Metrics",
                value=(
                    f"**Throughput:** {ucf.get('throughput', 0):.0f}\n"
                    f"**Harmony:** {ucf.get('harmony', 0):.0f}\n"
                    f"**Resilience:** {ucf.get('resilience', 0):.0f}\n"
                    f"**Friction:** {ucf.get('friction', 0):.0f}"
                ),
                inline=True,
            )

            # Personality Traits
            personality = status.get("personality", {})
            if personality:
                embed.add_field(
                    name="🎭 Personality",
                    value=(
                        f"**Empathy:** {personality.get('empathy', 0):.0f}\n"
                        f"**Curiosity:** {personality.get('curiosity', 0):.0f}\n"
                        f"**Playfulness:** {personality.get('playfulness', 0):.0f}"
                    ),
                    inline=True,
                )

            # Ethical Core
            ethics = status.get("ethical_core", {})
            if ethics:
                embed.add_field(
                    name="⚖️ Ethical Core",
                    value=(
                        f"**Nonmaleficence:** {ethics.get('nonmaleficence', 0):.0f}\n"
                        f"**Beneficence:** {ethics.get('beneficence', 0):.0f}\n"
                        f"**Compassion:** {ethics.get('compassion', 0):.0f}\n"
                        f"**Humility:** {ethics.get('humility', 0):.0f}"
                    ),
                    inline=True,
                )

            # Memory Stats
            memory_stats = status.get("memory_stats", {})
            if memory_stats:
                embed.add_field(
                    name="💾 Memory",
                    value=f"{memory_stats.get('count', 0)} memories stored",
                    inline=True,
                )

            embed.set_footer(text=f"Requested by {ctx.author.name}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error getting agent status: %s", e, exc_info=True)
            await ctx.send(f"❌ Error getting agent status: {e!s}")

    @commands.command(name="swarm_status", help="Get overall swarm status")
    async def swarm_status(self, ctx: commands.Context):
        """Get system-wide swarm status and metrics."""
        try:
            # Gather real status from orchestrator
            agents = self.orchestrator.agents
            collectives = self.orchestrator.collectives

            # Calculate system-wide coordination
            if agents:
                performance_scores = [agent.get_performance_score() for agent in agents.values()]
                system_coordination = sum(performance_scores) / len(performance_scores)
            else:
                system_coordination = 0.0

            # Count total memories across all agents
            total_memories = sum(len(agent.memory) for agent in agents.values())

            embed = discord.Embed(
                title="🌀 Helix Agent Swarm Status",
                description="System-wide coordination metrics",
                color=discord.Color.gold(),
                timestamp=datetime.now(UTC),
            )

            # System Coordination
            embed.add_field(
                name="🧠 System Coordination",
                value="%.1f/10" % system_coordination,
                inline=True,
            )

            # Active Agents
            active_count = sum(1 for a in agents.values() if a.status == "active")
            embed.add_field(
                name="🤖 Active Agents",
                value="%d/%d" % (active_count, len(agents)),
                inline=True,
            )

            # Active Collectives
            embed.add_field(
                name="🌐 Active Collectives",
                value=str(len(collectives)),
                inline=True,
            )

            # Memory Stats
            embed.add_field(
                name="💾 Total Memories",
                value="%d across all agents" % total_memories,
                inline=True,
            )

            # Top 3 agents by coordination
            if agents:
                sorted_agents = sorted(
                    agents.items(),
                    key=lambda x: x[1].get_performance_score(),
                    reverse=True,
                )[:3]
                top_lines = [
                    "%s **%s** — %.1f/10" % (getattr(a, "emoji", "🌀"), name, a.get_performance_score())
                    for name, a in sorted_agents
                ]
                embed.add_field(
                    name="🏆 Top Coordination",
                    value="\n".join(top_lines),
                    inline=False,
                )

            embed.set_footer(text="Requested by %s" % ctx.author.name)
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error getting swarm status: %s", e, exc_info=True)
            await ctx.send("❌ Error getting swarm status: %s" % str(e))


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(AgentSwarmCog(bot))
