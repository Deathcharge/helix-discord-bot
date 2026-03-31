"""
🧠 Discord Memory & LLM Preference Commands
=============================================

Cog that provides users with controls over:
- Their LLM model preferences (!model, !provider, !settings)
- Conversation management (!reset, !history, !memory)
- Agent memory inspection (!memories)

Add to any bot via: bot.add_cog(MemoryCommandsCog(bot))

Version: 17.3.0
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# Available LLM models by provider
AVAILABLE_MODELS = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o1",
        "o3-mini",
    ],
    "xai": [
        "grok-3-mini",
        "grok-3",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-2.5-pro-preview-06-05",
    ],
    "perplexity": [
        "sonar-pro",
        "sonar",
    ],
}

# Flat list for display
ALL_MODELS = []
for provider, models in AVAILABLE_MODELS.items():
    for m in models:
        ALL_MODELS.append((provider, m))


class MemoryCommandsCog(commands.Cog, name="Memory & Settings"):
    """User-facing commands for LLM preferences and memory management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.agent_name = getattr(bot, "agent_name", "Helix")
        self.agent_color = getattr(bot, "agent_color", 0x7B68EE)
        self.agent_symbol = getattr(bot, "agent_symbol", "🌀")

    def _get_memory_service(self):
        """Lazy-load the persistent memory service."""
        from apps.backend.discord.agent_memory_service import get_agent_memory

        return get_agent_memory()

    async def _get_db(self):
        """Get a database session."""
        from apps.backend.db_models import get_async_session

        return get_async_session()()

    # ------------------------------------------------------------------
    # !model — Change preferred LLM model
    # ------------------------------------------------------------------

    @commands.command(name="model")
    async def set_model(self, ctx: commands.Context, *, model_name: str | None = None):
        """Set your preferred LLM model.

        Usage:
            !model                     — Show current model and available options
            !model gpt-4o              — Switch to GPT-4o
            !model claude-sonnet-4-20250514  — Switch to Claude Sonnet 4
            !model grok-3-mini         — Switch to Grok 3 Mini
        """
        discord_user_id = str(ctx.author.id)
        mem = self._get_memory_service()

        if model_name is None:
            # Show current preference and available models
            async with await self._get_db() as db:
                prefs = await mem.get_user_llm_prefs(db, discord_user_id)

            current = prefs.get("model", "default") if prefs else "default"
            current_provider = prefs.get("provider", "auto") if prefs else "auto"

            embed = discord.Embed(
                title="🤖 LLM Model Settings",
                description=("**Current model:** `%s`\n**Current provider:** `%s`\n\nUse `!model <name>` to switch.")
                % (current, current_provider),
                color=self.agent_color,
            )

            for provider, models in AVAILABLE_MODELS.items():
                model_list = "\n".join("• `%s` %s" % (m, "← current" if m == current else "") for m in models)
                embed.add_field(
                    name=provider.title(),
                    value=model_list,
                    inline=True,
                )

            embed.set_footer(text="Your preference applies to all agents")
            await ctx.send(embed=embed)
            return

        # Validate model name
        matched_provider = None
        matched_model = None
        for provider, models in AVAILABLE_MODELS.items():
            for m in models:
                if model_name.lower() in m.lower() or m.lower() in model_name.lower():
                    matched_provider = provider
                    matched_model = m
                    break
            if matched_model:
                break

        if not matched_model:
            await ctx.send(
                "%s Model `%s` not found. Use `!model` to see available options." % (self.agent_symbol, model_name)
            )
            return

        # Save preference
        async with await self._get_db() as db:
            await mem.set_user_llm_prefs(
                db,
                discord_user_id,
                provider=matched_provider,
                model=matched_model,
            )

        await ctx.send(
            "%s **Model updated!** Now using `%s` (provider: %s)" % (self.agent_symbol, matched_model, matched_provider)
        )

    # ------------------------------------------------------------------
    # !temperature — Adjust response creativity
    # ------------------------------------------------------------------

    @commands.command(name="temperature")
    async def set_temperature(self, ctx: commands.Context, value: float | None = None):
        """Set the LLM temperature (creativity level).

        Usage:
            !temperature       — Show current temperature
            !temperature 0.3   — More focused/deterministic
            !temperature 0.7   — Balanced (default)
            !temperature 1.0   — More creative/varied
        """
        discord_user_id = str(ctx.author.id)
        mem = self._get_memory_service()

        if value is None:
            async with await self._get_db() as db:
                prefs = await mem.get_user_llm_prefs(db, discord_user_id)
            current = prefs.get("temperature", 0.7) if prefs else 0.7
            await ctx.send(
                "%s **Temperature:** `%.1f` — Use `!temperature <0.0-1.5>` to change." % (self.agent_symbol, current)
            )
            return

        if not 0.0 <= value <= 1.5:
            await ctx.send("%s Temperature must be between 0.0 and 1.5." % self.agent_symbol)
            return

        async with await self._get_db() as db:
            await mem.set_user_llm_prefs(db, discord_user_id, temperature=value)

        creativity = "focused" if value < 0.4 else "balanced" if value < 0.8 else "creative"
        await ctx.send("%s **Temperature set to `%.1f`** (%s responses)" % (self.agent_symbol, value, creativity))

    # ------------------------------------------------------------------
    # !settings — Show all preferences
    # ------------------------------------------------------------------

    @commands.command(name="settings")
    async def show_settings(self, ctx: commands.Context):
        """Show all your current LLM and conversation settings."""
        discord_user_id = str(ctx.author.id)
        mem = self._get_memory_service()

        async with await self._get_db() as db:
            prefs = await mem.get_user_llm_prefs(db, discord_user_id)
            memory_count = await mem.get_memory_count(db, self.agent_name)

        embed = discord.Embed(
            title="⚙️ Your Helix Settings",
            color=self.agent_color,
        )

        if prefs:
            embed.add_field(
                name="LLM Model",
                value="`%s`" % (prefs.get("model") or "default"),
                inline=True,
            )
            embed.add_field(
                name="Provider",
                value="`%s`" % (prefs.get("provider") or "auto"),
                inline=True,
            )
            embed.add_field(
                name="Temperature",
                value="`%.1f`" % (prefs.get("temperature") or 0.7),
                inline=True,
            )
            embed.add_field(
                name="Max Tokens",
                value="`%d`" % (prefs.get("max_tokens") or 2048),
                inline=True,
            )
        else:
            embed.add_field(
                name="LLM Settings",
                value="Using defaults. Use `!model` to customize.",
                inline=False,
            )

        embed.add_field(
            name="Agent Memories",
            value="%d stored for %s" % (memory_count, self.agent_name),
            inline=True,
        )

        embed.set_footer(text="Use !model, !temperature, !reset to configure")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # !reset — Start fresh conversation
    # ------------------------------------------------------------------

    @commands.command(name="reset")
    async def reset_conversation(self, ctx: commands.Context):
        """Reset your conversation history with this agent.

        Your long-term memories are preserved — only the conversation
        thread is cleared so you start fresh.
        """
        discord_user_id = str(ctx.author.id)
        mem = self._get_memory_service()

        async with await self._get_db() as db:
            success = await mem.reset_conversation(db, discord_user_id, self.agent_name)

        if success:
            await ctx.send(
                "%s **Conversation reset.** Long-term memories are preserved. Let's start fresh!" % self.agent_symbol
            )
        else:
            await ctx.send("%s No active conversation to reset." % self.agent_symbol)

    # ------------------------------------------------------------------
    # !memories — Inspect agent's memories
    # ------------------------------------------------------------------

    @commands.command(name="memories")
    async def show_memories(self, ctx: commands.Context, count: int = 5):
        """Show this agent's most important memories.

        Usage:
            !memories      — Show top 5 memories
            !memories 10   — Show top 10 memories
        """
        discord_user_id = str(ctx.author.id)
        mem = self._get_memory_service()

        async with await self._get_db() as db:
            memories = await mem.get_relevant_memories(
                db,
                self.agent_name,
                limit=min(count, 10),
                discord_user_id=discord_user_id,
            )

        if not memories:
            await ctx.send(
                "%s **%s** has no stored memories yet. "
                "Chat with me using `!speak` to build my memory!" % (self.agent_symbol, self.agent_name)
            )
            return

        embed = discord.Embed(
            title="🧠 %s %s — Memories" % (self.agent_symbol, self.agent_name),
            color=self.agent_color,
        )

        for i, mem_entry in enumerate(memories, 1):
            embed.add_field(
                name="%d. [%s] %s"
                % (
                    i,
                    mem_entry["type"],
                    mem_entry.get("created_at", "")[:10],
                ),
                value=mem_entry["summary"][:200],
                inline=False,
            )

        embed.set_footer(text="Showing %d memories | Coordination: %.1f" % (len(memories), memories[0].get("score", 0)))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Standard discord.py cog setup."""
    await bot.add_cog(MemoryCommandsCog(bot))
