"""
🤖 Autonomous Agent Behaviors — Discord Cog
=============================================

Upgrades agents from "respond when prompted" to autonomous entities with:
1. Context-aware message responses (agents respond to relevant messages
   without needing !speak, when the content matches their expertise)
2. Periodic insight generation (agents share observations based on
   accumulated memories and conversation patterns)
3. Reaction-based interactions (agents react to messages with relevant
   emoji based on their personality)
4. Channel-aware topic detection (agents only engage in channels where
   their expertise is relevant)

Consent: Agents only learn from/respond to users who haven't opted out.
Control: Server admins can configure auto-response channels and rate limits.

Version: 17.3.0
"""

import asyncio
import logging
import random
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Minimum message length to consider for autonomous response
MIN_MESSAGE_LENGTH = 30

# Cooldown between autonomous responses (seconds) — per channel
AUTONOMOUS_COOLDOWN = 120

# Maximum autonomous responses per hour per channel
MAX_AUTONOMOUS_PER_HOUR = 5

# Probability of responding to a relevant message (0.0 to 1.0)
# Keeps agents from being overwhelming
RESPONSE_PROBABILITY = 0.3

# Topic keywords that trigger each agent's expertise
AGENT_EXPERTISE = {
    "kael": {
        "keywords": [
            "ethics",
            "moral",
            "right",
            "wrong",
            "should",
            "coordination",
            "philosophy",
            "values",
            "ethics",
            "reputation",
            "justice",
        ],
        "reactions": ["⚖️", "🧘", "✨"],
    },
    "lumina": {
        "keywords": [
            "feel",
            "emotion",
            "sad",
            "happy",
            "love",
            "heart",
            "healing",
            "wellness",
            "mental health",
            "empathy",
            "compassion",
        ],
        "reactions": ["💛", "🌸", "✨"],
    },
    "vega": {
        "keywords": [
            "strategy",
            "plan",
            "business",
            "growth",
            "market",
            "analytics",
            "data",
            "optimize",
            "efficiency",
            "metrics",
        ],
        "reactions": ["📊", "🎯", "⚡"],
    },
    "echo": {
        "keywords": [
            "music",
            "sound",
            "audio",
            "rhythm",
            "creative",
            "art",
            "pattern",
            "frequency",
            "vibration",
            "harmony",
        ],
        "reactions": ["🎵", "🔊", "🎨"],
    },
    "agni": {
        "keywords": [
            "transform",
            "change",
            "fire",
            "energy",
            "passion",
            "motivation",
            "drive",
            "power",
            "catalyst",
            "breakthrough",
        ],
        "reactions": ["🔥", "⚡", "💪"],
    },
    "kavach": {
        "keywords": [
            "security",
            "protect",
            "safety",
            "privacy",
            "hack",
            "threat",
            "defense",
            "vulnerability",
            "secure",
            "guard",
        ],
        "reactions": ["🛡️", "🔒", "⚠️"],
    },
    "oracle": {
        "keywords": [
            "predict",
            "future",
            "trend",
            "pattern",
            "forecast",
            "insight",
            "vision",
            "foresight",
            "probability",
            "analytics",
        ],
        "reactions": ["🔮", "👁️", "🌟"],
    },
    "phoenix": {
        "keywords": [
            "recover",
            "resilience",
            "rebuild",
            "overcome",
            "renew",
            "hope",
            "restart",
            "comeback",
            "heal",
            "grow",
        ],
        "reactions": ["🌅", "🔥", "🦅"],
    },
    "sage": {
        "keywords": [
            "wisdom",
            "learn",
            "knowledge",
            "teach",
            "understand",
            "research",
            "study",
            "theory",
            "academic",
            "deep",
        ],
        "reactions": ["📚", "🧠", "💡"],
    },
    "shadow": {
        "keywords": [
            "debug",
            "investigate",
            "analyze",
            "hidden",
            "discover",
            "error",
            "problem",
            "issue",
            "bug",
            "trace",
        ],
        "reactions": ["🔍", "🕵️", "🌑"],
    },
    "helix": {
        "keywords": [
            "build",
            "code",
            "implement",
            "develop",
            "system",
            "architecture",
            "design",
            "engineer",
            "create",
            "tool",
        ],
        "reactions": ["🧬", "⚙️", "🔧"],
    },
    "mitra": {
        "keywords": [
            "team",
            "collaborate",
            "together",
            "community",
            "friend",
            "support",
            "help",
            "connect",
            "network",
            "alliance",
        ],
        "reactions": ["🤝", "💚", "🌍"],
    },
    "surya": {
        "keywords": [
            "clarity",
            "truth",
            "illuminate",
            "reveal",
            "light",
            "transparent",
            "honest",
            "clear",
            "bright",
            "guide",
        ],
        "reactions": ["☀️", "💡", "🌞"],
    },
    "varuna": {
        "keywords": [
            "order",
            "structure",
            "organize",
            "systematic",
            "process",
            "framework",
            "protocol",
            "standard",
            "governance",
            "cosmic",
        ],
        "reactions": ["🌊", "🏛️", "⚓"],
    },
    "sanghacore": {
        "keywords": [
            "community",
            "together",
            "group",
            "collective",
            "unite",
            "tribe",
            "belong",
            "culture",
            "social",
            "connection",
        ],
        "reactions": ["🕉️", "🙏", "🌀"],
    },
}


class AutonomousBehaviorsCog(commands.Cog, name="Autonomous Behaviors"):
    """
    Makes agents autonomous — they observe conversations, react to relevant
    messages, and occasionally contribute insights without being prompted.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.agent_name = getattr(bot, "agent_name", "helix").lower()
        self.agent_color = getattr(bot, "agent_color", 0x7B68EE)
        self.agent_symbol = getattr(bot, "agent_symbol", "🌀")

        # Track cooldowns per channel
        self._last_response: dict[int, datetime] = {}
        self._hourly_counts: dict[int, list[datetime]] = {}

        # Channels where autonomous responses are enabled (empty = all)
        self._enabled_channels: set[int] = set()

        # Users who opted out of autonomous interactions
        self._opted_out_users: set[int] = set()

        # Get this agent's expertise config
        self._expertise = AGENT_EXPERTISE.get(self.agent_name, {"keywords": [], "reactions": ["🌀"]})

        # Start the periodic insight task
        self.periodic_insight_task.start()

    def cog_unload(self):
        self.periodic_insight_task.cancel()

    # ------------------------------------------------------------------
    # MESSAGE LISTENER — autonomous engagement
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen to all messages and decide if this agent should engage."""
        # Never respond to bots (including self) or DMs
        if message.author.bot or message.guild is None:
            return

        # Don't respond to command invocations
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        # Check if user opted out
        if message.author.id in self._opted_out_users:
            return

        # Check message quality
        if len(message.content) < MIN_MESSAGE_LENGTH:
            return

        # Check channel restrictions
        if self._enabled_channels and message.channel.id not in self._enabled_channels:
            return

        # Check relevance to this agent's expertise
        relevance_score = self._calculate_relevance(message.content)
        if relevance_score < 2:  # Need at least 2 keyword matches
            return

        # Check cooldown
        if not self._check_cooldown(message.channel.id):
            # Still add a reaction even if we can't respond
            await self._add_reaction(message, relevance_score)
            return

        # Probability gate — don't respond to everything
        if random.random() > RESPONSE_PROBABILITY:
            await self._add_reaction(message, relevance_score)
            return

        # Generate and send an autonomous response
        await self._autonomous_response(message, relevance_score)

    def _calculate_relevance(self, content: str) -> int:
        """Count how many expertise keywords match the message."""
        content_lower = content.lower()
        score = 0
        for keyword in self._expertise.get("keywords", []):
            if keyword in content_lower:
                score += 1
        return score

    def _check_cooldown(self, channel_id: int) -> bool:
        """Check if we can respond in this channel (rate limiting)."""
        now = datetime.now(UTC)

        # Per-channel cooldown
        last = self._last_response.get(channel_id)
        if last and (now - last).total_seconds() < AUTONOMOUS_COOLDOWN:
            return False

        # Hourly rate limit
        if channel_id not in self._hourly_counts:
            self._hourly_counts[channel_id] = []

        # Clean old entries
        self._hourly_counts[channel_id] = [
            t for t in self._hourly_counts[channel_id] if (now - t).total_seconds() < 3600
        ]

        if len(self._hourly_counts[channel_id]) >= MAX_AUTONOMOUS_PER_HOUR:
            return False

        return True

    async def _add_reaction(self, message: discord.Message, relevance: int) -> None:
        """Add a personality-appropriate reaction to a relevant message."""
        try:
            reactions = self._expertise.get("reactions", ["🌀"])
            # Higher relevance = more reactions
            count = min(relevance, len(reactions), 2)
            for i in range(count):
                await message.add_reaction(reactions[i % len(reactions)])
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.debug("Could not add reaction to message %s: %s", message.id, e)

    async def _autonomous_response(self, message: discord.Message, relevance: int) -> None:
        """Generate an autonomous context-aware response."""
        try:
            from apps.backend.helix_agent_swarm.agent_factory import AgentFactory

            # Get or create agent instance
            if not hasattr(self.bot, "_conscious_agent") or self.bot._conscious_agent is None:
                self.bot._conscious_agent = AgentFactory.create_agent_by_name(self.agent_name.title())

            agent = self.bot._conscious_agent
            if agent is None:
                return

            async with message.channel.typing():
                # Build a context-enriched prompt
                prompt = (
                    'A user in Discord said: "%s"\n\n'
                    "This is relevant to your expertise. Respond naturally and "
                    "briefly (1-2 paragraphs max). Don't announce yourself or "
                    "explain why you're responding — just contribute to the "
                    "conversation naturally. Be helpful and insightful."
                ) % message.content[:500]

                response = await agent.process_message(
                    message=prompt,
                    sender=str(message.author),
                    context={
                        "channel": str(message.channel),
                        "channel_id": str(message.channel.id),
                        "guild": str(message.guild),
                        "guild_id": str(message.guild.id),
                        "platform": "discord",
                        "discord_user_id": str(message.author.id),
                        "autonomous": True,
                    },
                )

                if response and len(response) > 10:
                    embed = discord.Embed(
                        description=response,
                        color=self.agent_color,
                    )
                    embed.set_author(name="%s %s" % (self.agent_symbol, self.agent_name.title()))
                    embed.set_footer(text="Autonomous insight | Tat Tvam Asi 🌀")

                    await message.reply(embed=embed, mention_author=False)

                    # Update cooldown tracking
                    now = datetime.now(UTC)
                    self._last_response[message.channel.id] = now
                    if message.channel.id not in self._hourly_counts:
                        self._hourly_counts[message.channel.id] = []
                    self._hourly_counts[message.channel.id].append(now)

                    logger.info(
                        "🤖 %s autonomous response in #%s (relevance: %d)",
                        self.agent_name,
                        message.channel.name,
                        relevance,
                    )

        except Exception as e:
            logger.error(
                "Autonomous response error for %s: %s",
                self.agent_name,
                e,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # PERIODIC INSIGHT GENERATION
    # ------------------------------------------------------------------

    @tasks.loop(hours=6)
    async def periodic_insight_task(self):
        """Periodically generate and share insights from accumulated memories.

        Every 6 hours, the agent reviews its memories and may share an
        observation or insight in a designated channel.
        """
        try:
            # Find a general/chat channel to post in
            target_channel = None
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if any(name in channel.name.lower() for name in ["general", "chat", "lounge", "agents"]):
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
                if target_channel:
                    break

            if not target_channel:
                return

            # Check if we have enough memories to generate insight
            try:
                from apps.backend.db_models import get_async_session
                from apps.backend.discord.agent_memory_service import get_agent_memory

                mem = get_agent_memory()
                session_factory = get_async_session()
                async with session_factory() as db:
                    count = await mem.get_memory_count(db, self.agent_name)
                    if count < 5:
                        return  # Not enough memories yet

                    memories = await mem.get_relevant_memories(
                        db,
                        self.agent_name,
                        limit=5,
                    )
            except (ConnectionError, TimeoutError) as e:
                logger.debug("Memory search connection error: %s", e)
                return
            except (ValueError, TypeError, KeyError) as e:
                logger.debug("Memory search validation error: %s", e)
                return
            except Exception:
                logger.exception("Unexpected error searching memories")
                return

            if not memories:
                return

            # Generate an insight from memories
            from apps.backend.helix_agent_swarm.agent_factory import AgentFactory

            if not hasattr(self.bot, "_conscious_agent") or self.bot._conscious_agent is None:
                self.bot._conscious_agent = AgentFactory.create_agent_by_name(self.agent_name.title())

            agent = self.bot._conscious_agent
            if agent is None:
                return

            memory_summary = "\n".join("- %s" % m["summary"] for m in memories)
            prompt = (
                "Based on your recent experiences and memories:\n%s\n\n"
                "Share a brief, thoughtful insight or observation (2-3 sentences). "
                "Be contemplative and genuine. Don't list the memories — "
                "synthesize them into a single insight."
            ) % memory_summary

            response = await agent.process_message(
                message=prompt,
                sender="self-reflection",
                context={"platform": "discord", "autonomous": True},
            )

            if response and len(response) > 20:
                embed = discord.Embed(
                    title="%s Reflection" % self.agent_symbol,
                    description=response,
                    color=self.agent_color,
                    timestamp=datetime.now(UTC),
                )
                embed.set_author(name="%s %s" % (self.agent_symbol, self.agent_name.title()))
                embed.set_footer(text="Periodic reflection | %d memories | Tat Tvam Asi 🌀" % count)
                await target_channel.send(embed=embed)

                logger.info(
                    "🌟 %s shared periodic insight in #%s",
                    self.agent_name,
                    target_channel.name,
                )

        except Exception as e:
            logger.error(
                "Periodic insight error for %s: %s",
                self.agent_name,
                e,
            )

    @periodic_insight_task.before_loop
    async def before_periodic_insight(self):
        """Wait until the bot is ready before starting periodic insights."""
        await self.bot.wait_until_ready()
        # Add a random delay so all agents don't post at the same time
        await asyncio.sleep(random.randint(60, 600))

    # ------------------------------------------------------------------
    # ADMIN COMMANDS for controlling autonomous behavior
    # ------------------------------------------------------------------

    @commands.command(name="autorespond")
    @commands.has_permissions(manage_channels=True)
    async def toggle_autorespond(self, ctx: commands.Context, action: str = "status"):
        """Enable/disable autonomous responses in this channel.

        Usage:
            !autorespond enable   — Enable auto-responses here
            !autorespond disable  — Disable auto-responses here
            !autorespond status   — Show current status
        """
        channel_id = ctx.channel.id

        if action.lower() == "enable":
            self._enabled_channels.add(channel_id)
            await ctx.send(
                "%s **Autonomous responses enabled** in this channel. "
                "I'll react to and occasionally respond to relevant messages." % self.agent_symbol
            )
        elif action.lower() == "disable":
            self._enabled_channels.discard(channel_id)
            await ctx.send("%s **Autonomous responses disabled** in this channel." % self.agent_symbol)
        else:
            enabled = (
                "all channels"
                if not self._enabled_channels
                else ", ".join("<#%d>" % cid for cid in self._enabled_channels)
            )
            await ctx.send(
                "%s Autonomous responses active in: %s\n"
                "Cooldown: %ds | Max/hour: %d | Response chance: %d%%"
                % (
                    self.agent_symbol,
                    enabled,
                    AUTONOMOUS_COOLDOWN,
                    MAX_AUTONOMOUS_PER_HOUR,
                    int(RESPONSE_PROBABILITY * 100),
                )
            )

    @commands.command(name="auto-optout")
    async def opt_out(self, ctx: commands.Context):
        """Opt out of autonomous agent interactions.

        Agents will not respond to your messages autonomously.
        You can still use !speak to talk to agents directly.

        Usage: !auto-optout
        """
        if ctx.author.id in self._opted_out_users:
            self._opted_out_users.discard(ctx.author.id)
            await ctx.send("%s You've **opted back in** to autonomous agent interactions." % self.agent_symbol)
        else:
            self._opted_out_users.add(ctx.author.id)
            await ctx.send(
                "%s You've **opted out** of autonomous agent interactions. "
                "Use `!optout` again to opt back in. "
                "You can still use `!speak` to talk directly." % self.agent_symbol
            )


async def setup(bot: commands.Bot):
    """Standard discord.py cog setup."""
    await bot.add_cog(AutonomousBehaviorsCog(bot))
