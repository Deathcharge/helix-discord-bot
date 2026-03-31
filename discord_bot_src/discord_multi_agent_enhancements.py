"""
🚀 DISCORD MULTI-AGENT ENHANCEMENTS

Advanced Discord features for multi-agent interactions:
- Agent personality-based responses
- Emotional intelligence in Discord
- Multi-language support integration
- Interactive agent selection menus
- Conversation threading
- Agent collaboration visualization
"""

import logging
from datetime import UTC, datetime
from typing import Any

import discord
from discord.ext import commands

from apps.backend.coordination.affective_intelligence import AffectiveIntelligence
from apps.backend.discord.discord_i18n import get_translation, set_user_language
from apps.backend.helix_agent_swarm.helix_orchestrator import get_orchestrator

# Alias for backward compatibility
AffectiveIntelligenceSystem = AffectiveIntelligence

logger = logging.getLogger(__name__)


class AgentSelectionView(discord.ui.View):
    """Interactive agent selection menu."""

    def __init__(self, orchestrator, user_id: int):
        super().__init__(timeout=180)
        self.orchestrator = orchestrator
        self.user_id = user_id
        self.selected_agents: list[str] = []

        # Add agent selection buttons
        for agent_name, agent in list(orchestrator.agents.items())[:5]:  # Max 5 agents per row
            button = discord.ui.Button(
                label=f"{agent.emoji} {agent.name}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"agent_{agent_name}",
            )
            button.callback = self.create_agent_callback(agent_name)
            self.add_item(button)

        # Add collective mode button
        collective_button = discord.ui.Button(
            label="🌀 Collective Mode",
            style=discord.ButtonStyle.primary,
            custom_id="collective_mode",
        )
        collective_button.callback = self.collective_callback
        self.add_item(collective_button)

    def create_agent_callback(self, agent_name: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This menu is not for you!", ephemeral=True)
                return

            if agent_name in self.selected_agents:
                self.selected_agents.remove(agent_name)
                await interaction.response.send_message(f"Removed {agent_name} from selection.", ephemeral=True)
            else:
                self.selected_agents.append(agent_name)
                await interaction.response.send_message(
                    "Added {} to selection. Selected: {}".format(agent_name, ", ".join(self.selected_agents)),
                    ephemeral=True,
                )

        return callback

    async def collective_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return

        if not self.selected_agents:
            await interaction.response.send_message("Please select at least one agent first!", ephemeral=True)
            return

        await interaction.response.send_message(
            "Starting collective mode with: {}".format(", ".join(self.selected_agents)),
            ephemeral=True,
        )
        self.stop()


class MultiAgentEnhancementsCog(commands.Cog):
    """Advanced multi-agent Discord features."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.orchestrator = get_orchestrator()
        self.affective_system = AffectiveIntelligence(
            agent_id="helix_collective",
            base_personality={
                "empathy": 0.8,
                "stability": 0.7,
                "reactivity": 0.5,
                "resilience": 0.8,
                "optimism": 0.7,
                "joy": 0.6,
                "trust": 0.7,
                "curiosity": 0.8,
            },
        )
        self.conversation_threads: dict[int, dict[str, Any]] = {}

    @commands.command(name="select_agents", help="Interactive agent selection menu")
    async def select_agents(self, ctx: commands.Context):
        """Show interactive agent selection menu."""
        try:
            view = AgentSelectionView(self.orchestrator, ctx.author.id)

            embed = discord.Embed(
                title="🤖 Select Agents",
                description="Choose agents to interact with. Click buttons to select/deselect.\nThen click **🌀 Collective Mode** to start a conversation.",
                color=discord.Color.purple(),
            )

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            logger.error("Error in select_agents: %s", e, exc_info=True)
            await ctx.send("❌ Error: %s" % str(e))

    @commands.command(name="agent_emotion", help="Get agent emotional state")
    async def agent_emotion(self, ctx: commands.Context, agent_name: str):
        """Display agent's current emotional state."""
        try:
            if agent_name.lower() not in self.orchestrator.agents:
                await ctx.send(f"❌ Agent '{agent_name}' not found.")
                return

            agent = self.orchestrator.agents[agent_name.lower()]

            # Get emotional state from affective system
            emotion_state = self.affective_system.get_agent_emotion(agent_name)

            embed = discord.Embed(
                title=f"{agent.emoji} {agent.name} - Emotional State",
                color=discord.Color.blue(),
                timestamp=datetime.now(UTC),
            )

            # Primary emotion
            primary = emotion_state.get("primary_emotion", {})
            embed.add_field(
                name="Primary Emotion",
                value="{} ({:.0%})".format(primary.get("name", "Neutral"), primary.get("intensity", 0)),
                inline=False,
            )

            # Mood
            embed.add_field(
                name="Current Mood",
                value=emotion_state.get("mood", "Balanced"),
                inline=True,
            )

            # Empathy level
            embed.add_field(
                name="Empathy Level",
                value="{:.0%}".format(emotion_state.get("empathy", 0)),
                inline=True,
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error in agent_emotion: %s", e, exc_info=True)
            await ctx.send("❌ Error: %s" % e)

    @commands.command(name="set_language", help="Set your preferred language")
    async def set_language(self, ctx: commands.Context, language_code: str):
        """
        Set your preferred language for bot responses.

        Supported: en, es, fr, de, hi, sa, zh, ar, pt, bn, ru, ja, ko, it, tr, vi
        """
        try:
            supported_languages = [
                "en",
                "es",
                "fr",
                "de",
                "hi",
                "sa",
                "zh",
                "ar",
                "pt",
                "bn",
                "ru",
                "ja",
                "ko",
                "it",
                "tr",
                "vi",
            ]

            if language_code.lower() not in supported_languages:
                await ctx.send("❌ Unsupported language. Supported: {}".format(", ".join(supported_languages)))
                return

            set_user_language(str(ctx.author.id), language_code.lower())

            # Get translated confirmation
            confirmation = get_translation(
                language_code.lower(),
                "language_set",
                f"Language set to {language_code}",
            )

            await ctx.send(f"✅ {confirmation}")

        except Exception as e:
            logger.error("Error in set_language: %s", e, exc_info=True)
            await ctx.send("❌ Error: %s" % e)

    @commands.command(name="agent_collaborate", help="Watch agents collaborate on a task")
    async def agent_collaborate(self, ctx: commands.Context, *, task: str):
        """
        Watch multiple agents collaborate on a task in real-time.
        Shows each agent's contribution and the final synthesis.
        """
        try:
            # Create temporary collective
            collective_name = f"collab_{ctx.author.id}_{datetime.now(UTC).timestamp()}"
            agent_names = list(self.orchestrator.agents.keys())[:3]

            if not agent_names:
                await ctx.send("❌ No agents available.")
                return

            await self.orchestrator.create_collective(name=collective_name, agent_names=agent_names)

            # Initial message
            embed = discord.Embed(
                title="🌀 Agent Collaboration in Progress",
                description=f"**Task:** {task}\n\n**Participating Agents:**",
                color=discord.Color.purple(),
            )

            for agent_name in agent_names:
                agent = self.orchestrator.agents[agent_name]
                embed.add_field(
                    name=f"{agent.emoji} {agent.name}",
                    value=f"Coordination: {agent.get_performance_score():.0%}",
                    inline=True,
                )

            status_msg = await ctx.send(embed=embed)

            # Execute task
            result = await self.orchestrator.execute_task(task=task, collective_name=collective_name)

            # Update with results
            result_embed = discord.Embed(
                title="✅ Collaboration Complete",
                description=result.get("response", "No response generated"),
                color=discord.Color.green(),
                timestamp=datetime.now(UTC),
            )

            # Show individual contributions if available
            contributions = result.get("contributions", [])
            if contributions:
                for contrib in contributions[:3]:  # Max 3 to avoid embed limits
                    agent = self.orchestrator.agents.get(contrib["agent"])
                    if agent:
                        result_embed.add_field(
                            name=f"{agent.emoji} {agent.name}'s Contribution",
                            value=contrib.get("content", "No contribution")[:200],
                            inline=False,
                        )

            # Collective coordination
            collective = self.orchestrator.collectives[collective_name]
            result_embed.add_field(
                name="Collective Coordination",
                value=f"{collective.calculate_collective_coordination():.0%}",
                inline=True,
            )

            await status_msg.edit(embed=result_embed)

        except Exception as e:
            logger.error("Error in agent_collaborate: %s", e, exc_info=True)
            await ctx.send("❌ Error: %s" % e)

    @commands.command(name="conversation_thread", help="Start a threaded conversation with agents")
    async def conversation_thread(self, ctx: commands.Context, agent_name: str):
        """
        Start a threaded conversation with an agent.
        All replies in the thread will be sent to the agent.
        """
        try:
            if agent_name.lower() not in self.orchestrator.agents:
                await ctx.send(f"❌ Agent '{agent_name}' not found.")
                return

            agent = self.orchestrator.agents[agent_name.lower()]

            # Create thread
            thread = await ctx.message.create_thread(name=f"Chat with {agent.name}", auto_archive_duration=60)

            # Store thread info
            self.conversation_threads[thread.id] = {
                "agent_name": agent_name.lower(),
                "started_by": ctx.author.id,
                "started_at": datetime.now(UTC),
            }

            # Send greeting
            greeting_embed = discord.Embed(
                title=f"{agent.emoji} {agent.name}",
                description=f"Hello! I'm {agent.name}. Send messages in this thread to chat with me.",
                color=discord.Color.blue(),
            )

            greeting_embed.add_field(
                name="Coordination",
                value=f"{agent.get_performance_score():.0%}",
                inline=True,
            )

            greeting_embed.add_field(name="Core", value=agent.core, inline=True)

            await thread.send(embed=greeting_embed)

        except Exception as e:
            logger.error("Error in conversation_thread: %s", e, exc_info=True)
            await ctx.send("❌ Error: %s" % e)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages in conversation threads."""
        if message.author.bot:
            return

        # Check if message is in a conversation thread
        if isinstance(message.channel, discord.Thread):
            thread_id = message.channel.id

            if thread_id in self.conversation_threads:
                thread_info = self.conversation_threads[thread_id]
                agent_name = thread_info["agent_name"]

                try:
                    agent = self.orchestrator.agents[agent_name]

                    response = await agent.process_message(
                        message=message.content,
                        sender=str(message.author),
                        context={"thread_id": thread_id, "platform": "discord"},
                    )

                    await message.reply(response)

                except Exception as e:
                    logger.error("Error in thread message: %s", e, exc_info=True)
                    await message.reply("❌ Error: %s" % e)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(MultiAgentEnhancementsCog(bot))
