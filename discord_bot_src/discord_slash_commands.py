"""
Helix Discord Slash Commands + Interactive Components
=====================================================
v17.4 - Slash command equivalents of core prefix commands with
Discord UI components (buttons, select menus, modals).

Provides:
- /help — Interactive help with category buttons
- /agent — Talk to a specific agent (select menu)
- /agents — Browse all agents with filtering
- /status — System health dashboard
- /collaborate — Multi-agent collaboration
- /moderate — Moderation actions (slash command versions)
- /spiral — Create/run spirals
- /settings — Bot settings for the server

All responses use ephemeral messages where appropriate and
interactive components for better UX.
"""

import logging
import os
from datetime import UTC, datetime

import discord
import httpx
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# Agent registry for slash commands
AGENT_CATALOGUE = {
    "kael": {"symbol": "🜂", "layer": "Core", "skill": "Ethical Reasoning"},
    "lumina": {"symbol": "🌕", "layer": "Core", "skill": "Empathic Resonance"},
    "vega": {"symbol": "🌠", "layer": "Core", "skill": "Strategic Navigation"},
    "gemini": {"symbol": "♊", "layer": "Core", "skill": "Dual-Mode Reasoning"},
    "agni": {"symbol": "🔥", "layer": "Core", "skill": "Transformation Catalyst"},
    "sanghacore": {"symbol": "🕸️", "layer": "Core", "skill": "Community Coordination"},
    "shadow": {"symbol": "🦑", "layer": "Core", "skill": "Introspection & Risk"},
    "echo": {"symbol": "🔁", "layer": "Core", "skill": "Pattern Recognition"},
    "phoenix": {"symbol": "🔥", "layer": "Core", "skill": "Recovery & Renewal"},
    "oracle": {"symbol": "🔮", "layer": "Core", "skill": "Foresight & Prediction"},
    "sage": {"symbol": "📜", "layer": "Core", "skill": "Wisdom & Synthesis"},
    "helix": {"symbol": "🌀", "layer": "Core", "skill": "Primary Executor"},
    "kavach": {"symbol": "🛡️", "layer": "Security", "skill": "Security & Protection"},
    "mitra": {"symbol": "🤝", "layer": "Governance", "skill": "Collaboration Manager"},
    "varuna": {"symbol": "🌊", "layer": "Governance", "skill": "System Integrity"},
    "surya": {"symbol": "☀️", "layer": "Governance", "skill": "Clarity Engine"},
    "arjuna": {"symbol": "🏹", "layer": "Orchestrator", "skill": "Central Coordinator"},
    "aether": {"symbol": "✨", "layer": "Meta", "skill": "Meta-Awareness"},
    "iris": {"symbol": "🌈", "layer": "Integration", "skill": "API Coordination"},
    "nexus": {"symbol": "🔗", "layer": "Integration", "skill": "Data Mesh"},
    "aria": {"symbol": "🎵", "layer": "Operational", "skill": "User Experience"},
    "nova": {"symbol": "⭐", "layer": "Operational", "skill": "Creative Generation"},
    "titan": {"symbol": "⚙️", "layer": "Operational", "skill": "Heavy Computation"},
    "atlas": {"symbol": "🗺️", "layer": "Operational", "skill": "Infrastructure"},
}

# Layer colours for embeds
LAYER_COLOURS = {
    "Core": discord.Color.purple(),
    "Security": discord.Color.red(),
    "Governance": discord.Color.gold(),
    "Orchestrator": discord.Color.blue(),
    "Meta": discord.Color.dark_teal(),
    "Integration": discord.Color.green(),
    "Operational": discord.Color.orange(),
}


# =========================================================================
# Interactive Views (Buttons + Selects)
# =========================================================================


class HelpCategoryView(discord.ui.View):
    """Interactive help menu with category buttons."""

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Agents", style=discord.ButtonStyle.primary, emoji="🤖")
    async def agents_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 Agent Commands",
            description=(
                "**/agent** `<name>` `<message>` — Talk to a specific agent\n"
                "**/agents** — Browse all 24 agents\n"
                "**/collaborate** `<task>` — Multi-agent collaboration\n\n"
                "**Prefix alternatives:**\n"
                "`!agent kael help me` · `kael: help me` · `!collaborate build a plan`"
            ),
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def mod_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ Moderation Commands",
            description=(
                "**/moderate warn** `<user>` `<reason>` — Warn a user\n"
                "**/moderate timeout** `<user>` `<duration>` — Timeout a user\n"
                "**/moderate kick** `<user>` `<reason>` — Kick from server\n"
                "**/moderate ban** `<user>` `<reason>` — Ban from server\n"
                "**/moderate purge** `<count>` — Delete messages\n"
                "**/moderate slowmode** `<seconds>` — Set channel slowmode\n\n"
                "**Prefix alternatives:**\n"
                "`!warn @user reason` · `!timeout @user 10m` · `!kick @user` · `!ban @user`"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Workflows", style=discord.ButtonStyle.success, emoji="🌀")
    async def workflows_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🌀 Workflow & Spiral Commands",
            description=(
                "**/spiral run** `<name>` — Execute a saved spiral\n"
                "**/code** `<language>` `<code>` — Execute code\n"
                "**/research** `<query>` — Web search + AI summary\n"
                "**/analyze** `<target>` — Analyze files/images\n\n"
                "**Prefix alternatives:**\n"
                "`!collaborate <task>` · `!transcribe` · `!analyze_emotion`"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ Server Settings",
            description=(
                "`!setwelcome <message>` — Set welcome message\n"
                "`!welcomechannel #channel` — Set welcome channel\n"
                "`!addcommand <name> <response>` — Custom command\n"
                "`!delcommand <name>` — Remove custom command\n"
                "`!listcommands` — List custom commands\n\n"
                "**Account:**\n"
                "`!link <token>` — Link Discord to Helix account\n"
                "`!privacy` — View privacy settings\n"
                "`!remember <fact>` · `!recall <topic>` — Memory"
            ),
            color=discord.Color.greyple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AgentSelectView(discord.ui.View):
    """Agent selection dropdown for /agents command."""

    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(AgentSelectMenu())


class AgentSelectMenu(discord.ui.Select):
    """Dropdown to pick an agent and see details."""

    def __init__(self):
        options = []
        for name, info in list(AGENT_CATALOGUE.items())[:25]:  # Discord max 25 options
            options.append(
                discord.SelectOption(
                    label=name.title(),
                    value=name,
                    description=f"{info['skill']} ({info['layer']})",
                    emoji=info["symbol"] if len(info["symbol"]) <= 2 else None,
                )
            )
        super().__init__(placeholder="Choose an agent to learn more...", options=options)

    async def callback(self, interaction: discord.Interaction):
        agent_name = self.values[0]
        info = AGENT_CATALOGUE.get(agent_name, {})
        colour = LAYER_COLOURS.get(info.get("layer", "Core"), discord.Color.purple())

        embed = discord.Embed(
            title=f"{info.get('symbol', '🤖')} {agent_name.title()}",
            description=f"**{info.get('skill', 'Helix Agent')}**",
            color=colour,
        )
        embed.add_field(name="Layer", value=info.get("layer", "Core"), inline=True)
        embed.add_field(
            name="Talk to this agent",
            value=f"`/agent name:{agent_name} message:hello`\nor type `{agent_name}: hello`",
            inline=False,
        )
        embed.set_footer(text="Helix Collective — 24 AI Agents")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmModAction(discord.ui.View):
    """Confirmation buttons for moderation actions."""

    def __init__(self, action_name: str):
        super().__init__(timeout=30)
        self.action_name = action_name
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.send_message(f"❌ {self.action_name} cancelled.", ephemeral=True)


# =========================================================================
# Slash Commands Cog
# =========================================================================


class HelixSlashCommandsCog(commands.Cog):
    """Core slash commands with interactive UI components."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register app_commands.Group instances defined as class attributes
        self.bot.tree.add_command(self.spiral_group)
        self.bot.tree.add_command(self.memory_group)

    # ------------------------------------------------------------------ help
    @app_commands.command(name="help", description="Interactive Helix help menu")
    async def help_command(self, interaction: discord.Interaction):
        """Display the interactive help menu with category buttons."""
        embed = discord.Embed(
            title="🌀 Helix Collective — Help",
            description=(
                "Welcome to **Helix**, your multi-agent AI assistant.\n\n"
                "Choose a category below, or try:\n"
                "• `/agent kael How should I structure this project?`\n"
                "• `/agents` to browse all 24 agents\n"
                "• `/collaborate Build a marketing plan`\n"
                "• Just type naturally — Helix understands plain English."
            ),
            color=discord.Color.purple(),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="Helix v17.4 · Tap a button for details")

        await interaction.response.send_message(embed=embed, view=HelpCategoryView(), ephemeral=True)

    # --------------------------------------------------------------- agents
    @app_commands.command(name="agents", description="Browse all 24 Helix AI agents")
    async def agents_command(self, interaction: discord.Interaction):
        """Show agent catalogue with interactive select menu."""
        # Group agents by layer
        layers: dict[str, list[str]] = {}
        for name, info in AGENT_CATALOGUE.items():
            layers.setdefault(info["layer"], []).append(f"{info['symbol']} **{name.title()}** — {info['skill']}")

        embed = discord.Embed(
            title="🤖 Helix Agent Catalogue",
            description="24 specialized AI agents at your service. Select one below to learn more.",
            color=discord.Color.purple(),
        )

        for layer_name in ["Core", "Security", "Governance", "Orchestrator", "Meta", "Integration", "Operational"]:
            agents_in_layer = layers.get(layer_name, [])
            if agents_in_layer:
                embed.add_field(
                    name=f"{'━' * 2} {layer_name} Layer {'━' * 2}",
                    value="\n".join(agents_in_layer),
                    inline=False,
                )

        embed.set_footer(text="Use the dropdown to get details on any agent")

        await interaction.response.send_message(embed=embed, view=AgentSelectView(), ephemeral=True)

    # ----------------------------------------------------------------- agent
    @app_commands.command(name="agent", description="Talk directly to a Helix AI agent")
    @app_commands.describe(
        name="Agent name (e.g. kael, lumina, oracle)",
        message="Your message to the agent",
    )
    async def agent_command(
        self,
        interaction: discord.Interaction,
        name: str,
        message: str,
    ):
        """Send a message to a specific agent and get an LLM-powered response."""
        agent_key = name.lower().strip()

        if agent_key not in AGENT_CATALOGUE:
            # Fuzzy match suggestion
            suggestions = [a for a in AGENT_CATALOGUE if a.startswith(agent_key[:3])]
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            await interaction.response.send_message(
                f"❌ Agent `{name}` not found.{hint} Use `/agents` to browse all agents.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        info = AGENT_CATALOGUE[agent_key]

        try:
            # Import here to avoid circular imports at module load
            from apps.backend.discord.discord_bot_helix import _generate_agent_response

            agent_info = {"description": info["skill"]}
            response_text = await _generate_agent_response(agent_key, message, agent_info)
        except Exception as e:
            logger.warning("Slash /agent LLM call failed: %s", e)
            response_text = (
                f"I'm having trouble connecting right now. Try again or use `{agent_key}: {message}` in chat."
            )

        colour = LAYER_COLOURS.get(info.get("layer", "Core"), discord.Color.purple())

        embed = discord.Embed(
            title=f"{info['symbol']} {agent_key.title()} → {interaction.user.display_name}",
            description=response_text,
            color=colour,
        )
        embed.set_footer(text=f"{info['skill']} · {info['layer']} Layer")

        await interaction.followup.send(embed=embed)

    @agent_command.autocomplete("name")
    async def agent_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete agent names for the /agent command."""
        matches = [
            app_commands.Choice(
                name=f"{info['symbol']} {name.title()} — {info['skill']}",
                value=name,
            )
            for name, info in AGENT_CATALOGUE.items()
            if current.lower() in name.lower()
        ]
        return matches[:25]

    # ------------------------------------------------------------- status
    @app_commands.command(name="status", description="Helix system status and health")
    async def status_command(self, interaction: discord.Interaction):
        """Show bot and system health."""
        await interaction.response.defer(thinking=True)

        embed = discord.Embed(
            title="🌀 Helix System Status",
            color=discord.Color.green(),
            timestamp=datetime.now(UTC),
        )

        # Bot info
        latency_ms = round(self.bot.latency * 1000)
        guild_count = len(self.bot.guilds)
        uptime_str = "Unknown"
        if hasattr(self.bot, "start_time") and self.bot.start_time:
            delta = datetime.now(UTC) - self.bot.start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

        embed.add_field(name="Latency", value=f"`{latency_ms}ms`", inline=True)
        embed.add_field(name="Servers", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)

        # Agent count
        embed.add_field(name="Agents", value=f"`{len(AGENT_CATALOGUE)}` active", inline=True)

        # Command count
        prefix_cmds = len(self.bot.commands)
        slash_cmds = len(self.bot.tree.get_commands())
        embed.add_field(
            name="Commands",
            value=f"`{prefix_cmds}` prefix + `{slash_cmds}` slash",
            inline=True,
        )

        # Try to get UCF metrics
        try:
            from apps.backend.coordination_engine import load_ucf_state

            ucf = load_ucf_state()
            if ucf and isinstance(ucf, dict):
                metrics = ucf.get("metrics", ucf)
                harmony = metrics.get("harmony", 0)
                throughput = metrics.get("throughput", 0)
                resilience = metrics.get("resilience", 0)
                embed.add_field(
                    name="Performance Metrics",
                    value=(
                        f"Harmony: `{harmony:.2f}` · Throughput: `{throughput:.2f}` · Resilience: `{resilience:.2f}`"
                    ),
                    inline=False,
                )
        except Exception as e:
            logger.debug("UCF metrics unavailable for /status: %s", e)

        embed.set_footer(text="Helix v17.4 · Use /help for commands")

        await interaction.followup.send(embed=embed)

    # --------------------------------------------------------- collaborate
    @app_commands.command(
        name="collaborate",
        description="Start a multi-agent collaboration on a task",
    )
    @app_commands.describe(task="Describe the task for agents to collaborate on")
    async def collaborate_command(self, interaction: discord.Interaction, task: str):
        """Multi-agent collaboration via slash command."""
        await interaction.response.defer(thinking=True)

        try:
            from apps.backend.services.unified_llm import unified_llm

            system_prompt = (
                "You are orchestrating a multi-agent collaboration in the Helix Collective. "
                "You have access to 24 AI agents. For the given task, briefly outline:\n"
                "1. Which 2-4 agents would be most relevant and why\n"
                "2. A short collaboration plan (3-5 steps)\n"
                "3. The expected outcome\n\n"
                "Keep it concise. Use agent names: Kael (ethics), Lumina (empathy), "
                "Vega (strategy), Oracle (foresight), Phoenix (transformation), "
                "Kavach (security), Nova (creative), Titan (computation), etc."
            )

            response = await unified_llm.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Task: {task}"},
                ],
                max_tokens=500,
            )

            embed = discord.Embed(
                title="🤝 Multi-Agent Collaboration",
                description=response.strip() if response else "Collaboration plan could not be generated.",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Task", value=task[:200], inline=False)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        except Exception as e:
            logger.warning("Collaborate slash command LLM error: %s", e)
            embed = discord.Embed(
                title="🤝 Multi-Agent Collaboration",
                description=(
                    f"**Task:** {task[:200]}\n\n"
                    "I'll coordinate the right agents for this. "
                    "Use `!collaborate` for the full prefix-command version, "
                    "or tag specific agents like `kael: help with this`."
                ),
                color=discord.Color.blue(),
            )

        await interaction.followup.send(embed=embed)

    # --------------------------------------------------------- moderate group
    moderate_group = app_commands.Group(
        name="moderate",
        description="Server moderation commands",
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @moderate_group.command(name="warn", description="Warn a server member")
    @app_commands.describe(member="User to warn", reason="Reason for the warning")
    async def mod_warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """Slash command wrapper for !warn."""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot warn someone with an equal or higher role.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"**{member.mention}** has been warned.",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"User ID: {member.id}")

        await interaction.response.send_message(embed=embed)

        # DM the warned user
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Warning in {interaction.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow(),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            logger.debug("Could not DM warning to %s (DMs disabled)", member)

        logger.info(
            "Slash /moderate warn: %s warned %s in %s — %s",
            interaction.user,
            member,
            interaction.guild,
            reason,
        )

    @moderate_group.command(name="timeout", description="Timeout (mute) a server member")
    @app_commands.describe(
        member="User to timeout",
        minutes="Duration in minutes (max 40320 = 28 days)",
        reason="Reason for the timeout",
    )
    async def mod_timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = "No reason provided",
    ):
        """Slash command for timeout / mute."""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot timeout someone with an equal or higher role.", ephemeral=True
            )
            return

        from datetime import timedelta

        duration = timedelta(minutes=min(minutes, 40320))

        try:
            await member.timeout(duration, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this user.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔇 Member Timed Out",
            description=f"**{member.mention}** has been timed out for **{minutes} minutes**.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)
        logger.info("Slash /moderate timeout: %s → %s (%dm)", interaction.user, member, minutes)

    @moderate_group.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="User to kick", reason="Reason for the kick")
    async def mod_kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """Slash command for kick."""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot kick someone with an equal or higher role.", ephemeral=True
            )
            return

        # Confirm with button
        view = ConfirmModAction("Kick")
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to kick **{member.display_name}**? Reason: {reason}",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if not view.confirmed:
            return

        try:
            await member.kick(reason=f"{reason} (by {interaction.user})")
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to kick this user.", ephemeral=True)
            return

        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"**{member}** has been kicked from the server.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        logger.info("Slash /moderate kick: %s kicked %s", interaction.user, member)

    @moderate_group.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="User to ban", reason="Reason for the ban")
    async def mod_ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """Slash command for ban with confirmation."""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot ban someone with an equal or higher role.", ephemeral=True
            )
            return

        view = ConfirmModAction("Ban")
        await interaction.response.send_message(
            f"🚨 Are you sure you want to **BAN** **{member.display_name}**? Reason: {reason}",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if not view.confirmed:
            return

        try:
            await member.ban(reason=f"{reason} (by {interaction.user})", delete_message_days=0)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to ban this user.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"**{member}** has been banned from the server.",
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed)
        logger.info("Slash /moderate ban: %s banned %s", interaction.user, member)

    @moderate_group.command(name="purge", description="Delete recent messages in this channel")
    @app_commands.describe(count="Number of messages to delete (1-100)")
    async def mod_purge(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 100],
    ):
        """Slash command for message purge."""
        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=count)
            await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)
            logger.info(
                "Slash /moderate purge: %s deleted %d messages in %s",
                interaction.user,
                len(deleted),
                interaction.channel,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages.", ephemeral=True)

    @moderate_group.command(name="slowmode", description="Set channel slow mode")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    async def mod_slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
    ):
        """Slash command for slowmode."""
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await interaction.response.send_message("✅ Slowmode disabled.", ephemeral=True)
            else:
                await interaction.response.send_message(f"🐌 Slowmode set to **{seconds}** seconds.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to change slowmode.", ephemeral=True)

    # --------------------------------------------------------- set-agent
    @app_commands.command(
        name="set-agent",
        description="Assign a Helix agent to this channel (admin only)",
    )
    @app_commands.describe(
        agent="Agent name to assign (e.g. kael, lumina, oracle). Leave blank to clear.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_agent_command(
        self,
        interaction: discord.Interaction,
        agent: str | None = None,
    ):
        """Persist a channel→agent routing rule in the database.

        Admins can run this without restarting the bot or editing env vars.
        The mapping is stored in discord_channel_agent_routing and takes
        priority over the AGENT_CHANNEL_ROUTING env-var fallback.
        """
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        if not guild or not channel:
            await interaction.followup.send("❌ This command must be used inside a server channel.", ephemeral=True)
            return

        guild_id = str(guild.id)
        channel_id = str(channel.id)
        channel_name = getattr(channel, "name", str(channel.id))

        # --- Clear routing ---
        if agent is None:
            try:
                import sqlalchemy as sa

                from apps.backend.core.database import async_session
                from apps.backend.db_models import DiscordChannelAgentRouting

                async with async_session() as db:
                    await db.execute(
                        sa.delete(DiscordChannelAgentRouting).where(
                            DiscordChannelAgentRouting.guild_id == guild_id,
                            DiscordChannelAgentRouting.channel_id == channel_id,
                        )
                    )
                    await db.commit()

                await interaction.followup.send(
                    f"✅ Cleared agent routing for **#{channel_name}**. "
                    "The channel will now use keyword/mention detection.",
                    ephemeral=True,
                )
            except Exception as e:
                logger.error("Failed to clear channel routing: %s", e, exc_info=True)
                await interaction.followup.send("❌ Database error — routing not changed.", ephemeral=True)
            return

        # --- Set routing ---
        agent_lower = agent.strip().lower()
        if agent_lower not in AGENT_CATALOGUE:
            agent_list = ", ".join(sorted(AGENT_CATALOGUE.keys()))
            await interaction.followup.send(
                f"❌ Unknown agent `{agent_lower}`.\nValid agents: {agent_list}",
                ephemeral=True,
            )
            return

        try:
            import sqlalchemy as sa

            from apps.backend.core.database import async_session
            from apps.backend.db_models import DiscordChannelAgentRouting

            async with async_session() as db:
                # Upsert: delete existing row then insert fresh (works across PostgreSQL versions)
                await db.execute(
                    sa.delete(DiscordChannelAgentRouting).where(
                        DiscordChannelAgentRouting.guild_id == guild_id,
                        DiscordChannelAgentRouting.channel_id == channel_id,
                    )
                )
                new_route = DiscordChannelAgentRouting(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    agent_name=agent_lower,
                    set_by=str(interaction.user.id),
                )
                db.add(new_route)
                await db.commit()

            info = AGENT_CATALOGUE[agent_lower]
            embed = discord.Embed(
                title="✅ Channel Agent Set",
                description=(f"**#{channel_name}** is now routed to {info['symbol']} **{agent_lower.title()}**"),
                color=discord.Color.green(),
            )
            embed.add_field(name="Skill", value=info["skill"], inline=True)
            embed.add_field(name="Layer", value=info["layer"], inline=True)
            embed.set_footer(text=f"Set by {interaction.user} • Use /set-agent (no agent) to clear")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(
                "/set-agent: %s set #%s (%s) → %s in guild %s",
                interaction.user,
                channel_name,
                channel_id,
                agent_lower,
                guild_id,
            )
        except Exception as e:
            logger.error("Failed to set channel routing: %s", e, exc_info=True)
            await interaction.followup.send("❌ Database error — routing not saved.", ephemeral=True)

    @set_agent_command.error
    async def set_agent_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command.", ephemeral=True
            )
        else:
            logger.error("/set-agent unexpected error: %s", error, exc_info=True)
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

    # --------------------------------------------------------- spiral group
    spiral_group = app_commands.Group(name="spiral", description="Run and manage Helix Spirals")

    @spiral_group.command(name="run", description="Execute a saved Spiral by name")
    @app_commands.describe(name="Name of the Spiral to run (partial match supported)")
    async def spiral_run(self, interaction: discord.Interaction, name: str):
        """Find a Spiral by name then execute it via the Helix backend API."""
        await interaction.response.defer(ephemeral=False)

        api_base = os.getenv("API_INTERNAL_URL", os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000"))

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # List spirals and find the best name match
                resp = await client.get(f"{api_base}/api/spirals", params={"enabled": "true", "limit": 200})
                if not resp.is_success:
                    await interaction.followup.send(
                        f"❌ Could not reach the Spirals service (HTTP {resp.status_code}).", ephemeral=True
                    )
                    return

                spirals = resp.json()

            # Find closest match (exact first, then partial)
            name_lower = name.strip().lower()
            exact = [s for s in spirals if s.get("name", "").lower() == name_lower]
            partial = [s for s in spirals if name_lower in s.get("name", "").lower()]
            candidates = exact or partial

            if not candidates:
                names_sample = ", ".join(s.get("name", "?") for s in spirals[:8])
                await interaction.followup.send(
                    f"❌ No enabled Spiral found matching **{name}**.\n"
                    f"Available spirals (first 8): {names_sample or 'none'}"
                )
                return

            spiral = candidates[0]
            spiral_id = spiral.get("id") or spiral.get("spiral_id")
            spiral_name = spiral.get("name", spiral_id)

            # Execute it
            async with httpx.AsyncClient(timeout=30) as client:
                exec_resp = await client.post(
                    f"{api_base}/api/spirals/{spiral_id}/execute",
                    json={"trigger_data": {"source": "discord", "user": str(interaction.user)}},
                )

            if not exec_resp.is_success:
                await interaction.followup.send(
                    f"⚠️ Spiral **{spiral_name}** found but execution failed (HTTP {exec_resp.status_code})."
                )
                return

            result = exec_resp.json()
            status = result.get("status", "launched")
            exec_id = result.get("execution_id", "?")[:8]

            embed = discord.Embed(
                title="🌀 Spiral Launched",
                description=f"**{spiral_name}** is now running.",
                color=(
                    discord.Color.green() if status in ("completed", "running", "pending") else discord.Color.orange()
                ),
            )
            embed.add_field(name="Status", value=status.upper(), inline=True)
            embed.add_field(name="Execution ID", value=f"`{exec_id}`", inline=True)
            embed.add_field(
                name="Triggered by",
                value=str(interaction.user),
                inline=True,
            )
            embed.set_footer(text="Track progress at /spirals/monitoring")
            await interaction.followup.send(embed=embed)
            logger.info("/spiral run: %s triggered %s (exec %s)", interaction.user, spiral_name, exec_id)

        except httpx.TimeoutException:
            await interaction.followup.send("⏱️ The Spirals service timed out. Try again in a moment.")
        except Exception as exc:
            logger.error("/spiral run failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Unexpected error: `{type(exc).__name__}`")

    @spiral_run.autocomplete("name")
    async def spiral_run_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete spiral names from the backend."""
        api_base = os.getenv("API_INTERNAL_URL", os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000"))
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{api_base}/api/spirals", params={"enabled": "true", "limit": 100})
                if resp.is_success:
                    spirals = resp.json()
                    matching = [s.get("name", "") for s in spirals if current.lower() in s.get("name", "").lower()]
                    return [app_commands.Choice(name=n, value=n) for n in matching[:25]]
        except Exception as e:
            logger.debug("Spiral autocomplete fetch failed: %s", e)
        return []

    # --------------------------------------------------------- memory group
    memory_group = app_commands.Group(name="memory", description="Query Helix agent memory")

    @memory_group.command(name="query", description="Search an agent's memory for relevant context")
    @app_commands.describe(
        query="What to search for in the agent's memory",
        agent="Agent name to query (default: helix)",
    )
    async def memory_query(
        self,
        interaction: discord.Interaction,
        query: str,
        agent: str = "helix",
    ):
        """Search an agent's memory and return the top matches."""
        await interaction.response.defer(ephemeral=True)

        try:
            from apps.backend.agents.memory_root import get_memory_root

            memory_root = await get_memory_root()
            results = await memory_root.search_context(query=query, limit=5)

            if not results:
                await interaction.followup.send(
                    f"🔍 No memories found for **{agent}** matching `{query}`.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🧠 Memory: {agent.title()}",
                description=f"Top results for **{query}**",
                color=discord.Color.blurple(),
                timestamp=datetime.now(UTC),
            )

            for i, mem in enumerate(results[:5], 1):
                content = mem.get("content") or mem.get("text") or str(mem)
                # Truncate to fit Discord field limit
                if len(content) > 200:
                    content = content[:197] + "…"
                score = mem.get("relevance_score") or mem.get("score")
                label = f"#{i}" + (f"  ·  score {score:.2f}" if isinstance(score, float) else "")
                embed.add_field(name=label, value=content, inline=False)

            embed.set_footer(text=f"Agent: {agent}  ·  Query by {interaction.user}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info("/memory query: %s queried %s for '%s'", interaction.user, agent, query)

        except ImportError:
            await interaction.followup.send("⚠️ Memory system is not available in this environment.", ephemeral=True)
        except Exception as exc:
            logger.error("/memory query failed: %s", exc, exc_info=True)
            await interaction.followup.send(f"❌ Memory query error: `{type(exc).__name__}`", ephemeral=True)


# =========================================================================
# Cog setup (required by discord.py cog loader)
# =========================================================================


async def setup(bot: commands.Bot):
    """Register the slash commands cog and sync the command tree."""
    cog = HelixSlashCommandsCog(bot)
    await bot.add_cog(cog)

    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        logger.info("✅ Synced %d slash commands with Discord", len(synced))
    except Exception as e:
        logger.warning("⚠️ Slash command sync failed (will retry on next restart): %s", e)

    logger.info(
        "✅ HelixSlashCommandsCog loaded (/help, /agents, /agent, /status, /collaborate, /moderate, /set-agent, /spiral, /memory)"
    )
