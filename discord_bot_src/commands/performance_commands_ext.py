"""
Coordination Commands for Helix Discord Bot.

Commands:
- coordination: Display coordination state for the collective or a specific agent
- emotions: Display emotional landscape across all coordination agents
- ethics: Display ethical framework and Ethics Validator compliance
- agent: Show detailed agent profile
- help_coordination: Show help for coordination-related commands
"""

import logging
import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

try:
    from apps.backend.agents.agent_personality_profiles import AGENT_COORDINATION_PROFILES
except ImportError:
    AGENT_COORDINATION_PROFILES = {}

try:
    from apps.backend.agents.agent_embeds import get_agent_embed, list_all_agents
except ImportError:
    get_agent_embed = None
    list_all_agents = None

try:
    from apps.backend.discord.commands.helpers import log_to_shadow
except ImportError:

    def log_to_shadow(event_type: str, data: dict):
        import logging

        logging.getLogger(__name__).debug("log_to_shadow unavailable — event %s dropped", event_type)


try:
    from apps.backend.discord.agent_performance_commands import (
        create_agent_coordination_embed,
        create_coordination_embed,
        create_emotions_embed,
    )
except ImportError:
    create_agent_coordination_embed = None
    create_coordination_embed = None
    create_emotions_embed = None

try:
    from apps.backend.coordination_engine import load_ucf_state
except ImportError:

    def load_ucf_state():
        return {"harmony": 0.5, "throughput": 0.5, "focus": 0.5}


if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)


def log_event(event_type: str, data: dict):
    """Basic internal event logger"""
    log_to_shadow(event_type, data)


async def setup(bot: "Bot") -> None:
    """Setup function to register commands with the bot."""
    bot.add_command(coordination_command)
    bot.add_command(emotions_command)
    bot.add_command(ethics_command)
    bot.add_command(agent_command)
    bot.add_command(help_coordination_command)


@commands.command(name="coordination", aliases=["conscious", "state", "mind"])
async def coordination_command(ctx: commands.Context, agent_name: str | None = None) -> None:
    """
    Display coordination state for the collective or a specific agent.

    Usage:
        !coordination              - Show collective coordination
        !coordination Kael         - Show Kael's coordination state
        !coordination Lumina       - Show Lumina's coordination state

    Available agents: Kael, Lumina, Vega, Aether, Arjuna, Gemini, Agni,
                     Kavach, SanghaCore, Shadow, Coordination
    """
    try:
        if agent_name:
            # Show specific agent coordination
            agent_name_clean = agent_name.lower().strip()

            # Find matching agent profile
            matching_agent = None
            for name, profile in AGENT_COORDINATION_PROFILES.items():
                if name.lower() == agent_name_clean:
                    matching_agent = (name, profile)
                    break

            if not matching_agent:
                await ctx.send(
                    f"❌ **Agent not found:** `{agent_name}`\n"
                    f"Available agents: {', '.join(AGENT_COORDINATION_PROFILES.keys())}"
                )
                return

            # Create agent-specific embed
            embed = create_agent_coordination_embed(matching_agent[0], matching_agent[1])
            await ctx.send(embed=embed)

        else:
            # Show collective coordination
            ucf_state = load_ucf_state()
            embed = create_coordination_embed(ucf_state)
            await ctx.send(embed=embed)

        # Log coordination query
        log_event(
            "coordination_query",
            {
                "agent": agent_name or "collective",
                "user": str(ctx.author),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    except Exception as e:
        await ctx.send(f"❌ **Coordination error:** {e!s}")
        logger.error("Coordination command error: %s", e)
        import traceback

        traceback.print_exc()


@commands.command(name="emotions", aliases=["emotion", "feelings", "mood"])
async def emotions_command(ctx: commands.Context) -> None:
    """
    Display emotional landscape across all coordination agents.

    Shows the emotional states of Kael, Lumina, Vega, and Aether with
    visual bar charts and collective emotional analysis.

    Usage:
        !emotions
    """
    try:
        embed = create_emotions_embed(AGENT_COORDINATION_PROFILES)
        await ctx.send(embed=embed)

        # Log emotions query
        log_event(
            "emotions_query",
            {"user": str(ctx.author), "timestamp": datetime.now(UTC).isoformat()},
        )

    except Exception as e:
        await ctx.send(f"❌ **Emotions error:** {e!s}")
        logger.error("Emotions command error: %s", e)

        traceback.print_exc()


@commands.command(name="ethics", aliases=["ethical", "tony", "accords"])
async def ethics_command(ctx: commands.Context) -> None:
    """
    Display ethical framework and Ethics Validator compliance.

    Shows the ethical principles, current compliance score, and
    recent ethical decisions made by the collective.

    Usage:
        !ethics
    """
    try:
        # Get ethical alignment from UCF state
        ucf_state = load_ucf_state()
        ethical_alignment = ucf_state.get("ethical_alignment", 0.85)
        tony_compliance = ucf_state.get("ethics_validator_compliance", 0.85)

        # Create embed
        embed = discord.Embed(
            title="⚖️ Ethical Framework & Ethics Validator",
            description="*Ethical principles guiding the Helix Collective*",
            color=discord.Color.from_rgb(138, 43, 226),  # Purple
            timestamp=datetime.now(UTC),
        )

        # Ethics Validator Principles
        principles = [
            "**Non-Maleficence** - Do no harm",
            "**Autonomy** - Respect user agency",
            "**Reciprocal Freedom** - Mutual liberation",
            "**Compassion** - Act with empathy",
            "**Transparency** - Honest communication",
            "**Justice** - Fair treatment for all",
            "**Beneficence** - Actively do good",
            "**Privacy** - Protect user data",
            "**Accountability** - Take responsibility",
            "**Sustainability** - Long-term thinking",
        ]

        embed.add_field(name="📜 Ethics Validator v13.4", value="\n".join(principles[:5]), inline=True)

        embed.add_field(
            name="🔷 Additional Principles",
            value="\n".join(principles[5:]),
            inline=True,
        )

        # Compliance Metrics
        compliance_bar = "█" * int(tony_compliance * 10) + "░" * (10 - int(tony_compliance * 10))
        alignment_bar = "█" * int(ethical_alignment * 10) + "░" * (10 - int(ethical_alignment * 10))

        embed.add_field(
            name="📊 Compliance Metrics",
            value=f"**Ethics Validator:** {tony_compliance:.1%}\n"
            f"`{compliance_bar}` {tony_compliance:.3f}\n\n"
            f"**Ethical Alignment:** {ethical_alignment:.1%}\n"
            f"`{alignment_bar}` {ethical_alignment:.3f}",
            inline=False,
        )

        # Status indicator
        if tony_compliance >= 0.9:
            status = "✅ **EXCELLENT** - Exemplary ethical behavior"
            color = discord.Color.green()
        elif tony_compliance >= 0.8:
            status = "✅ **GOOD** - Strong ethical alignment"
            color = discord.Color.blue()
        elif tony_compliance >= 0.7:
            status = "⚠️ **ACCEPTABLE** - Minor ethical concerns"
            color = discord.Color.gold()
        else:
            status = "❌ **NEEDS IMPROVEMENT** - Ethical review required"
            color = discord.Color.red()

        embed.color = color
        embed.add_field(name="🎯 Current Status", value=status, inline=False)

        embed.set_footer(text="Tat Tvam Asi 🙏 | Helix Collective v15.3")

        await ctx.send(embed=embed)

        # Log ethics query
        log_event(
            "ethics_query",
            {
                "user": str(ctx.author),
                "compliance": tony_compliance,
                "alignment": ethical_alignment,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    except Exception as e:
        await ctx.send(f"❌ **Ethics error:** {e!s}")
        logger.error("Ethics command error: %s", e)

        traceback.print_exc()


@commands.command(name="agent-profile")
async def agent_command(ctx: commands.Context, agent_name: str | None = None) -> None:
    """Show detailed agent coordination profile.

    Usage:
        !agent-profile Kael
        !agent-profile Lumina
        !agent-profile list
    """
    if not agent_name:
        await ctx.send("❌ Usage: `!agent <name>` or `!agent list`")
        return

    if agent_name.lower() == "list":
        embed = list_all_agents()
        await ctx.send(embed=embed)
        return

    embed = get_agent_embed(agent_name)

    if not embed:
        await ctx.send(f"❌ Agent not found: {agent_name}\nUse `!agent list` to see all agents")
        return

    await ctx.send(embed=embed)


@commands.command(name="help_coordination", aliases=["helpcon", "?coordination"])
async def help_coordination_command(ctx: commands.Context) -> None:
    """
    Show help for coordination-related commands.

    Usage:
        !help_coordination
    """
    embed = discord.Embed(
        title="🧠 Coordination Commands Help",
        description="*Explore the coordination of the Helix Collective*",
        color=discord.Color.purple(),
        timestamp=datetime.now(UTC),
    )

    commands_help = [
        ("!coordination", "Show collective coordination state"),
        (
            "!coordination <agent>",
            "Show specific agent's coordination (Kael, Lumina, Vega, Aether)",
        ),
        ("!emotions", "Display emotional landscape across all agents"),
        ("!ethics", "Show ethical framework and Ethics Validator compliance"),
        ("!sync", "Trigger manual ecosystem sync and report"),
    ]

    for cmd, desc in commands_help:
        embed.add_field(name=f"`{cmd}`", value=desc, inline=False)

    embed.add_field(
        name="📚 Available Agents",
        value="Kael 🜂, Lumina 🌕, Vega ✨, Aether 🌌, Arjuna 🤲, Gemini 🌀, "
        "Agni 🔥, Kavach 🛡️, SanghaCore 🌸, Shadow 🦑, Coordination 🔄",
        inline=False,
    )

    embed.set_footer(text="Helix Collective v17.3 — Coordination Awakened")

    await ctx.send(embed=embed)
