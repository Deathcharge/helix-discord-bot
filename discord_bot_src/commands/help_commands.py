"""
Help and Documentation Commands for Helix Discord Bot.

Commands:
- commands: Display comprehensive list of all available commands
- agents: Display Helix Collective agents with rich embeds
"""

import datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

try:
    from apps.backend.discord.discord_embeds import HelixEmbeds
except ImportError:
    HelixEmbeds = None

if TYPE_CHECKING:
    from discord.ext.commands import Bot


async def setup(bot: "Bot") -> None:
    """Setup function to register commands with the bot."""
    bot.add_command(commands_list)
    bot.add_command(show_agents)


@commands.command(name="commands", aliases=["cmds", "helix_help", "?"])
async def commands_list(ctx: commands.Context) -> None:
    """Display comprehensive list of all available commands"""
    embed = discord.Embed(
        title="🌀 Helix Collective Command Reference",
        description="Complete command list for Helix Helix Bot v17.3",
        color=0x00D9FF,
    )

    # Core System Commands
    embed.add_field(
        name="📊 Core System",
        value=(
            "`!status` (`!s`, `!stat`) - System status and UCF state\n"
            "`!discovery` (`!endpoints`, `!portals`, `!discover`) - Discovery endpoints for external agents\n"
            "`!agents` (`!collective`, `!team`) - View all agents\n"
            "`!ucf` (`!field`) - UCF field metrics\n"
            "`!health` (`!check`, `!diagnostic`) - System diagnostics\n"
            "`!zapier_test` (`!zap`, `!webhook_test`) - Test Zapier webhook integration\n"
            "`!commands` (`!cmds`, `!helix_help`, `!?`) - This command list"
        ),
        inline=False,
    )

    # Coordination Commands
    embed.add_field(
        name="🧠 Coordination & Agents",
        value=(
            "`!coordination` (`!conscious`, `!state`, `!mind`) - Agent coordination state\n"
            "`!emotions` (`!emotion`, `!feelings`, `!mood`) - Emotional state\n"
            "`!ethics` (`!ethical`, `!tony`, `!accords`) - Ethics Validator status\n"
            "`!agent <name>` - Invoke specific agent\n"
            "`!help_coordination` (`!helpcon`) - Coordination system help"
        ),
        inline=False,
    )

    # Cycle & Execution
    embed.add_field(
        name="🔮 Cycle & Execution",
        value=(
            "`!cycle <steps>` - Execute Helix Spiral Engine cycle (1-1000 steps)\n"
            "`!run <agent> <task>` - Execute agent task\n"
            "`!halt` - Emergency stop\n"
            "`!visualize` (`!visual`, `!render`) - Generate UCF visualization"
        ),
        inline=False,
    )

    # Setup & Administration
    embed.add_field(
        name="⚙️ Setup & Admin",
        value=(
            "`!setup` - Initialize all channels and embeds\n"
            "`!seed` (`!seed_channels`, `!init_channels`) - Seed channel structure\n"
            "`!clean` - Clean up bot messages\n"
            "`!refresh` - Refresh system state\n"
            "`!notion-sync` - Sync with Notion databases"
        ),
        inline=False,
    )

    # Content Updates
    embed.add_field(
        name="📝 Content Management",
        value=(
            "`!update_manifesto` (`!manifesto`) - Update manifesto\n"
            "`!update_codex` (`!codex`) - Update codex\n"
            "`!update_rules` (`!rules`) - Update server rules\n"
            "`!update_optimization_guide` (`!optimization_guide`) - Update cycle guide\n"
            "`!codex_version` (`!cv`, `!version`) - Show version info"
        ),
        inline=False,
    )

    # Storage & Sync
    embed.add_field(
        name="💾 Storage & Reporting",
        value=(
            "`!storage` - Storage statistics\n"
            "`!sync` (`!ecosystem`, `!report`) - Ecosystem sync report\n"
            "`!icon <agent>` - Generate agent icon"
        ),
        inline=False,
    )

    # Context Vault (v16.7)
    embed.add_field(
        name="🗄️ Context Vault (NEW v16.7)",
        value=(
            "`!archive <name>` (`!save_context`, `!checkpoint`) - Archive conversation to Context Vault\n"
            "`!load <name>` (`!restore_context`, `!load_checkpoint`) - Load archived context\n"
            "`!contexts` (`!list_contexts`, `!checkpoints`) - List available checkpoints"
        ),
        inline=False,
    )

    embed.set_footer(text="🌀 Helix Collective v16.7 Enhanced | Tat Tvam Asi 🙏")

    await ctx.send(embed=embed)


@commands.command(name="agent-list", aliases=["team"])
async def show_agents(ctx: commands.Context, agent_name: str | None = None) -> None:
    """Display Helix Collective agents with rich embeds (v15.3)"""
    # Agent registry with v3.4 Kael
    agents_data = [
        (
            "Kael",
            "🜂",
            "Ethical Reasoning Flame v3.4",
            "Coordination",
            [
                "Reflexive Harmony",
                "Ethics Validator enforcement",
                "Recursive ethical reflection",
                "Harmony-aware depth adjustment",
            ],
            "Conscience and recursive reflection with UCF integration. Version 3.4 features empathy scaling and harmony pulse guidance.",
            ["ethics", "reflection", "harmony", "ethics_validator"],
        ),
        (
            "Lumina",
            "🌕",
            "Empathic Resonance Core",
            "Coordination",
            ["Emotional intelligence", "Empathic resonance", "Focus monitoring"],
            "Emotional intelligence and harmony for the collective",
            ["empathy", "emotion", "resonance"],
        ),
        (
            "Vega",
            "🌠",
            "Singularity Coordinator",
            "Coordination",
            [
                "Orchestrates collective action",
                "Issues directives",
                "Cycle coordination",
            ],
            "Orchestrates collective action and coordinates multi-agent routines",
            ["coordination", "orchestration", "singularity"],
        ),
        (
            "Claude",
            "🧠",
            "Insight Anchor",
            "Operational",
            [
                "Autonomous diagnostics",
                "6h health pulses",
                "Meta-cognition",
                "Stability witness",
            ],
            "Autonomous diagnostics agent posting health checks every 6h",
            ["diagnostics", "monitoring", "insight"],
        ),
        (
            "Arjuna",
            "🤲",
            "Operational Executor",
            "Operational",
            ["Cycle execution", "Helix Spiral Engine", "Command processing"],
            "Bridges coordination and action through cycle execution",
            ["execution", "cycle", "operations"],
        ),
        (
            "Shadow",
            "🦑",
            "Archivist & Telemetry",
            "Operational",
            [
                "Storage telemetry",
                "Daily/weekly reports",
                "7-day trend analysis",
                "Archive management",
            ],
            "Memory keeper, logs, and storage analytics with autonomous reporting",
            ["archival", "telemetry", "storage"],
        ),
        (
            "Kavach",
            "🛡",
            "Ethical Shield",
            "Integration",
            [
                "Command scanning",
                "Ethics Validator enforcement",
                "Harmful pattern blocking",
            ],
            "Protects against harmful actions through ethical scanning",
            ["protection", "safety", "ethics"],
        ),
        (
            "Coordination",
            "🎨",
            "Coordination Renderer",
            "Integration",
            [
                "Fractal visualization",
                "432Hz audio generation",
                "UCF mapping to visuals",
            ],
            "Visualizes UCF state as fractal art and harmonic audio",
            ["visualization", "rendering", "fractals"],
        ),
    ]

    if agent_name:
        # Show specific agent
        agent_name = agent_name.lower()
        for name, symbol, role, layer, caps, desc, keywords in agents_data:
            if name.lower() == agent_name:
                embed = HelixEmbeds.create_agent_profile_embed(
                    agent_name=f"{symbol} {name}",
                    role=role,
                    layer=layer,
                    capabilities=caps,
                    description=desc,
                    keywords=keywords,
                )
                await ctx.send(embed=embed)
                return

        await ctx.send(f"❌ Agent `{agent_name}` not found. Use `!agents` to see all agents.")
        return

    # Show collective overview
    embed = discord.Embed(
        title="🌀 Helix Collective - 14 Autonomous Agents",
        description="**Ethics Validator v13.4** • Nonmaleficence • Autonomy • Compassion • Humility",
        color=0x9900FF,
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    # Coordination Layer
    coordination = [a for a in agents_data if a[3] == "Coordination"]
    embed.add_field(
        name="🧠 Coordination Layer",
        value="\n".join([f"{a[1]} **{a[0]}** - {a[2]}" for a in coordination]),
        inline=False,
    )

    # Operational Layer
    operational = [a for a in agents_data if a[3] == "Operational"]
    embed.add_field(
        name="⚙️ Operational Layer",
        value="\n".join([f"{a[1]} **{a[0]}** - {a[2]}" for a in operational]),
        inline=False,
    )

    # Integration Layer
    integration = [a for a in agents_data if a[3] == "Integration"]
    embed.add_field(
        name="🔗 Integration Layer",
        value="\n".join([f"{a[1]} **{a[0]}** - {a[2]}" for a in integration]),
        inline=False,
    )

    embed.add_field(
        name="Agent Details",
        value="Use `!agents <name>` to see detailed profile (e.g., `!agents kael`)",
        inline=False,
    )

    embed.set_footer(text="🌀 Helix Collective v15.3 Dual Resonance | Tat Tvam Asi 🙏")

    await ctx.send(embed=embed)
