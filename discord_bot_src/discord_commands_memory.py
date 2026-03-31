# 🌀 Helix Collective v14.5 — System Handshake
# backend/discord_commands_memory.py — Memory Root Discord Commands
# Author: Andrew John Ward (Architect)

import discord
from discord.ext import commands

from apps.backend.agents.memory_root import get_memory_root
from apps.backend.logging.helix_logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# MEMORY ROOT COMMAND GROUP
# ============================================================================


class MemoryRootCommands(commands.Cog):
    """Discord commands for Memory Root agent (GPT4o)."""

    def __init__(self, bot):
        self.bot = bot

    # ========================================================================
    # MEMORY RECALL COMMANDS
    # ========================================================================

    @commands.command(name="recall", aliases=["memory", "remember"])
    async def recall_memory(self, ctx, *, query: str):
        """
        Ask Memory Root to recall information from collective memory.

        Usage: !recall What happened during Phase 6?
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Synthesize memory
            response = await memory_root.synthesize_memory(query)
            if not response:
                await ctx.send(f"⚠ No memories found for: {query}")
                return

            # Format response
            embed = discord.Embed(
                title="🧠 Memory Root Synthesis",
                description=response[:2000],  # Discord message limit
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Query: {query}")

            await ctx.send(embed=embed)

    @commands.command(name="history", aliases=["agent-history"])
    async def agent_history(self, ctx, agent_name: str, days: int = 7):
        """
        Retrieve history of an agent's actions.

        Usage: !history Arjuna 7
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Get agent history
            history = await memory_root.retrieve_agent_history(agent_name, days)
            if not history:
                await ctx.send(f"⚠ No history found for agent {agent_name}")
                return

            # Format response
            embed = discord.Embed(
                title=f"📜 {agent_name} History (Last {days} days)",
                color=discord.Color.green(),
            )

            for i, event in enumerate(history[:10], 1):
                embed.add_field(
                    name="{}. {}".format(i, event["title"]),
                    value="**Type:** {}\n**Time:** {}".format(event["type"], event["timestamp"][:10]),
                    inline=False,
                )

            embed.set_footer(text=f"Total events: {len(history)}")
            await ctx.send(embed=embed)

    @commands.command(name="session", aliases=["context"])
    async def get_session_context(self, ctx, session_id: str):
        """
        Retrieve context from a specific session.

        Usage: !session claude-2025-10-21-helix-v14.5
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Get session context
            context = await memory_root.retrieve_session_context(session_id)
            if not context:
                await ctx.send(f"⚠ Session not found: {session_id}")
                return

            # Format response
            embed = discord.Embed(title="📸 Session Context", color=discord.Color.purple())

            embed.add_field(name="Session ID", value=session_id, inline=False)
            embed.add_field(name="AI System", value=context.get("ai_system", "Unknown"), inline=True)
            embed.add_field(
                name="Created",
                value=context.get("created", "Unknown")[:10],
                inline=True,
            )
            embed.add_field(
                name="Summary",
                value=context.get("summary", "No summary")[:500],
                inline=False,
            )
            embed.add_field(
                name="Key Decisions",
                value=context.get("decisions", "No decisions")[:500],
                inline=False,
            )
            embed.add_field(
                name="Next Steps",
                value=context.get("next_steps", "No next steps")[:500],
                inline=False,
            )

            await ctx.send(embed=embed)

    @commands.command(name="search", aliases=["find"])
    async def search_context(self, ctx, *, query: str):
        """
        Search context snapshots for a topic.

        Usage: !search Notion integration
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Search context
            results = await memory_root.search_context(query, limit=5)
            if not results:
                await ctx.send(f"⚠ No context found for: {query}")
                return

            # Format response
            embed = discord.Embed(
                title=f"🔍 Search Results: {query}",
                color=discord.Color.orange(),
            )

            for i, snapshot in enumerate(results, 1):
                embed.add_field(
                    name="{}. {}".format(i, snapshot["session_id"]),
                    value="**System:** {}\n**Date:** {}\n**Summary:** {}...".format(
                        snapshot["ai_system"],
                        snapshot["created"][:10],
                        snapshot["summary"][:200],
                    ),
                    inline=False,
                )

            embed.set_footer(text=f"Found {len(results)} matching sessions")
            await ctx.send(embed=embed)

    # ========================================================================
    # SYSTEM STATUS COMMANDS
    # ========================================================================

    @commands.command(name="roster", aliases=["memory-agents"])
    async def list_agents(self, ctx):
        """
        List all agents from Memory Root/Notion.

        Usage: !roster or !memory-agents
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Get all agents
            agents = await memory_root.notion_client.get_all_agents() if memory_root.notion_client else []
            if not agents:
                await ctx.send("⚠ No agents found")
                return

            # Format response
            embed = discord.Embed(title="👥 Helix Collective Roster", color=discord.Color.gold())

            active = [a for a in agents if a["status"] == "Active"]
            pending = [a for a in agents if a["status"] == "Pending"]
            offline = [a for a in agents if a["status"] == "Offline"]

            if active:
                embed.add_field(
                    name=f"🟢 Active ({len(active)})",
                    value="\n".join(["• {} (Health: {}%)".format(a["name"], a["health"]) for a in active]),
                    inline=False,
                )

            if pending:
                embed.add_field(
                    name=f"🟡 Pending ({len(pending)})",
                    value="\n".join(["• {}".format(a["name"]) for a in pending]),
                    inline=False,
                )

            if offline:
                embed.add_field(
                    name=f"🔴 Offline ({len(offline)})",
                    value="\n".join(["• {}".format(a["name"]) for a in offline]),
                    inline=False,
                )

            embed.set_footer(text=f"Total agents: {len(agents)}")
            await ctx.send(embed=embed)

    @commands.command(name="memory-health", aliases=["memory-status"])
    async def memory_health(self, ctx):
        """
        Check Memory Root health and connectivity.

        Usage: !memory-health
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Get health
            health = await memory_root.health_check()

            # Format response
            embed = discord.Embed(title="🧠 Memory Root Health", color=discord.Color.blue())

            embed.add_field(
                name="Status",
                value=health.get("status", "Unknown").upper(),
                inline=True,
            )
            embed.add_field(
                name="OpenAI",
                value=("✅ Connected" if health.get("openai_available") else "❌ Unavailable"),
                inline=True,
            )
            embed.add_field(
                name="Notion",
                value=("✅ Connected" if health.get("notion_available") else "❌ Unavailable"),
                inline=True,
            )
            embed.add_field(name="Timestamp", value=health.get("timestamp", "Unknown"), inline=False)

            await ctx.send(embed=embed)

    # ========================================================================
    # REFLECTION COMMANDS
    # ========================================================================

    @commands.command(name="reflect", aliases=["meditation"])
    async def memory_reflection(self, ctx):
        """
        Hear Memory Root's reflection on the collective.

        Usage: !reflect
        """
        async with ctx.typing():
            memory_root = await get_memory_root()
            if not memory_root:
                await ctx.send("❌ Memory Root unavailable")
                return

            # Get reflection
            reflection = await memory_root.reflect()

            # Format response
            embed = discord.Embed(
                title="🧠 Memory Root Reflection",
                description=reflection,
                color=discord.Color.purple(),
            )

            await ctx.send(embed=embed)


# ============================================================================
# SETUP
# ============================================================================


async def setup(bot):
    """Setup Memory Root commands."""
    await bot.add_cog(MemoryRootCommands(bot))
    logger.info("✅ Memory Root commands loaded")
