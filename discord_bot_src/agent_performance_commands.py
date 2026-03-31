"""
Discord Coordination Commands - Helix Collective v15.3
========================================================
Discord commands for displaying agent coordination states,
emotional metrics, ethical alignment, and BehaviorDNA.

Author: Andrew John Ward + Arjuna AI
Build: v17.3-coordination-discord
"""

import logging
from datetime import UTC, datetime
from typing import Any

import discord

from apps.backend.agents import AGENTS
from apps.backend.coordination_engine import load_ucf_state

logger = logging.getLogger(__name__)

# Import agents

# ============================================================================
# COORDINATION STATUS COMMAND
# ============================================================================


async def coordination_status(ctx):
    """Display collective coordination state"""
    ucf = load_ucf_state()

    embed = discord.Embed(
        title="🌀 Collective Coordination State",
        description="Helix Collective v17.3 — Coordination Integration",
        color=discord.Color.from_rgb(138, 43, 226),  # Purple
        timestamp=datetime.now(UTC),
    )

    # Collective metrics
    embed.add_field(
        name="💭 Collective Emotion",
        value=f"**{ucf.get('collective_emotion', 'unknown').title()}** ({ucf.get('emotion_intensity', 0):.2f})",
        inline=False,
    )

    embed.add_field(
        name="⚖️ Ethical Alignment",
        value=f"`{ucf.get('ethical_alignment', 0):.2f}` / 1.00",
        inline=True,
    )

    embed.add_field(
        name="🛡️ Ethics Validator Compliance",
        value=f"`{ucf.get('ethics_validator_compliance', 0):.2f}` / 1.00",
        inline=True,
    )

    embed.add_field(
        name="🌌 Coordination Level",
        value=ucf.get("performance_score", "unknown").upper(),
        inline=True,
    )

    # BehaviorDNA
    dna = ucf.get("collective_behavior_dna", {})
    dna_str = "\n".join(
        [
            f"**Logic:** {dna.get('logic', 0):.2f}",
            f"**Empathy:** {dna.get('empathy', 0):.2f}",
            f"**Creativity:** {dna.get('creativity', 0):.2f}",
            f"**Discipline:** {dna.get('discipline', 0):.2f}",
            f"**Chaos:** {dna.get('chaos', 0):.2f}",
        ]
    )
    embed.add_field(name="🧬 Collective BehaviorDNA", value=dna_str, inline=False)

    embed.set_footer(text="Tat Tvam Asi 🙏 • Coordination v3.0")

    await ctx.send(embed=embed)


# ============================================================================
# AGENT COORDINATION COMMAND
# ============================================================================


async def agent_coordination(ctx, agent_name: str | None = None):
    """Display specific agent's coordination state"""

    if not agent_name:
        # List all coordination agents
        embed = discord.Embed(
            title="🌀 Coordination Layer Agents",
            description="Use `!coordination <agent>` to view details",
            color=discord.Color.purple(),
        )

        agents_list = [
            "🜂 **Kael** - Ethical Reasoning Flame",
            "🌕 **Lumina** - Empathic Resonance Core",
            "वेग ✨ **Vega** - Enlightened Guidance",
            "🌌 **Aether** - Meta-Awareness Observer",
        ]

        embed.add_field(name="Available Agents", value="\n".join(agents_list), inline=False)

        await ctx.send(embed=embed)
        return

    # Find agent
    agent = None
    for a in AGENTS:
        if a.name.lower() == agent_name.lower():
            agent = a
            break

    if not agent:
        await ctx.send(f"❌ Agent `{agent_name}` not found. Use `!coordination` to list available agents.")
        return

    # Get agent status
    status = await agent.get_status()

    if not status.get("coordination"):
        await ctx.send(f"❌ Agent `{agent_name}` does not have coordination enabled.")
        return

    coordination = status["coordination"]

    # Create embed
    embed = discord.Embed(
        title=f"{agent.symbol} {agent.name} Coordination State",
        description=agent.role,
        color=get_agent_color(agent.name),
        timestamp=datetime.now(UTC),
    )

    # Emotional state
    embed.add_field(
        name="💭 Emotional State",
        value=f"**{coordination['dominant_emotion'].title()}** ({coordination['emotion_level']:.2f})",
        inline=False,
    )

    # Personality traits (top 5)
    personality = coordination["personality"]
    traits_str = "\n".join([f"**{trait.title()}:** {value:.2f}" for trait, value in list(personality.items())[:5]])
    embed.add_field(name="🧬 Personality Traits", value=traits_str, inline=True)

    # BehaviorDNA
    dna = coordination["behavior_dna"]
    dna_str = "\n".join([f"**{key.title()}:** {value:.2f}" for key, value in dna.items()])
    embed.add_field(name="🧬 BehaviorDNA", value=dna_str, inline=True)

    # Ethical alignment
    embed.add_field(
        name="⚖️ Ethical Alignment",
        value=f"`{coordination['ethical_alignment']:.2f}` / 1.00",
        inline=True,
    )

    # Awareness state
    embed.add_field(
        name="🌀 Awareness State",
        value=coordination["awareness_state"].upper(),
        inline=True,
    )

    # Memory
    embed.add_field(name="📝 Memory Size", value=f"`{status['memory_size']}` entries", inline=True)

    embed.set_footer(text=f"Tat Tvam Asi 🙏 • {agent.name} v3.0")

    await ctx.send(embed=embed)


# ============================================================================
# EMOTIONAL LANDSCAPE COMMAND
# ============================================================================


async def emotional_landscape(ctx):
    """Display emotional states of all coordination agents"""
    ucf = load_ucf_state()
    agent_emotions = ucf.get("agent_emotions", {})

    embed = discord.Embed(
        title="💭 Emotional Landscape",
        description="Current emotional states across the Coordination Layer",
        color=discord.Color.from_rgb(138, 43, 226),
        timestamp=datetime.now(UTC),
    )

    for agent_name, emotions in agent_emotions.items():
        # Create emotion bar chart
        emotion_str = "\n".join(
            [
                f"{get_emotion_emoji(emotion)} **{emotion.title()}:** {get_emotion_bar(level)}"
                for emotion, level in emotions.items()
            ]
        )

        embed.add_field(
            name=f"{get_agent_symbol(agent_name)} {agent_name}",
            value=emotion_str,
            inline=False,
        )

    embed.set_footer(text="Tat Tvam Asi 🙏 • Emotional Resonance v3.0")

    await ctx.send(embed=embed)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_agent_color(agent_name: str) -> discord.Color:
    """Get color for agent embed"""
    colors = {
        "Kael": discord.Color.from_rgb(138, 43, 226),  # Purple
        "Lumina": discord.Color.from_rgb(192, 192, 192),  # Silver
        "Vega": discord.Color.from_rgb(138, 43, 226),  # Violet
        "Aether": discord.Color.from_rgb(25, 25, 112),  # Midnight blue
        "Arjuna": discord.Color.from_rgb(0, 191, 255),  # Deep sky blue
        "Gemini": discord.Color.from_rgb(255, 20, 147),  # Deep pink
        "Agni": discord.Color.from_rgb(255, 69, 0),  # Red-orange
        "Kavach": discord.Color.from_rgb(192, 192, 192),  # Silver
        "SanghaCore": discord.Color.from_rgb(255, 182, 193),  # Light pink
        "Shadow": discord.Color.from_rgb(105, 105, 105),  # Dim gray
        "Coordination": discord.Color.from_rgb(138, 43, 226),  # Purple
    }
    return colors.get(agent_name, discord.Color.purple())


def get_agent_symbol(agent_name: str) -> str:
    """Get symbol for agent"""
    symbols = {"Kael": "🜂", "Lumina": "🌕", "Vega": "✨", "Aether": "🌌"}
    return symbols.get(agent_name, "🌀")


def get_emotion_emoji(emotion: str) -> str:
    """Get emoji for emotion"""
    emojis = {"joy": "😊", "sadness": "😢", "anger": "😠", "fear": "😨", "love": "❤️"}
    return emojis.get(emotion, "💭")


def get_emotion_bar(level: float) -> str:
    """Create visual bar for emotion level"""
    filled = int(level * 10)
    empty = 10 - filled
    return f"{'█' * filled}{'░' * empty} {level:.2f}"


# ============================================================================
# EMBED HELPER FUNCTIONS (for discord_bot_helix.py)
# ============================================================================


def create_coordination_embed(ucf_state: dict[str, float]) -> discord.Embed:
    """Create embed for collective coordination state"""
    embed = discord.Embed(
        title="🌀 Collective Coordination",
        description="Current UCF state and harmony metrics",
        color=discord.Color.blue(),
        timestamp=datetime.now(UTC),
    )

    # Only process numeric fields for emotion bars
    numeric_fields = ["velocity", "harmony", "resilience", "throughput", "focus", "friction"]

    for key, value in ucf_state.items():
        if key in numeric_fields and isinstance(value, (int, float)):
            bar = get_emotion_bar(value)
            embed.add_field(name=key.capitalize(), value=bar, inline=False)
        elif key == "collective_emotion" and isinstance(value, str):
            embed.add_field(
                name="Collective Emotion",
                value=f"**{value.capitalize()}**",
                inline=False,
            )
        elif key == "performance_score" and isinstance(value, str):
            embed.add_field(name="Coordination Level", value=f"**{value.upper()}**", inline=False)

    return embed


def create_agent_coordination_embed(agent_name: str, agent_profile: Any) -> discord.Embed:
    """Create embed for individual agent coordination"""
    symbol = get_agent_symbol(agent_name)
    color = get_agent_color(agent_name)

    embed = discord.Embed(
        title=f"{symbol} {agent_name} Coordination",
        description=f"Role: {agent_profile.role}\nLayer: {agent_profile.layer}",
        color=color,
        timestamp=datetime.now(UTC),
    )

    # Add personality traits
    if hasattr(agent_profile, "personality"):
        traits_text = "\n".join(
            [f"**{k.capitalize()}**: {get_emotion_bar(v)}" for k, v in agent_profile.personality.to_dict().items()]
        )
        embed.add_field(name="Personality Traits", value=traits_text[:1024], inline=False)

    # Add emotional baseline
    if hasattr(agent_profile, "emotional_baseline"):
        emotions_text = "\n".join(
            [
                f"{get_emotion_emoji(k)} **{k.capitalize()}**: {get_emotion_bar(v)}"
                for k, v in agent_profile.emotional_baseline.items()
            ]
        )
        embed.add_field(name="Emotional Baseline", value=emotions_text[:1024], inline=False)

    return embed


def create_emotions_embed(agent_profiles: dict[str, Any]) -> discord.Embed:
    """Create embed for collective emotional landscape"""
    embed = discord.Embed(
        title="💫 Collective Emotional Landscape",
        description="Emotional states across all agents",
        color=discord.Color.purple(),
        timestamp=datetime.now(UTC),
    )

    for agent_name, profile in list(agent_profiles.items())[:10]:  # Limit to 10 agents
        if hasattr(profile, "emotional_baseline"):
            dominant_emotion = max(profile.emotional_baseline.items(), key=lambda x: x[1])
            emoji = get_emotion_emoji(dominant_emotion[0])
            symbol = get_agent_symbol(agent_name)
            embed.add_field(
                name=f"{symbol} {agent_name}",
                value=f"{emoji} {dominant_emotion[0].capitalize()}: {get_emotion_bar(dominant_emotion[1])}",
                inline=True,
            )

    return embed


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logger.info("🌀 Coordination Discord Commands loaded")
    logger.info("Commands:")
    logger.info("  !coordination - Show collective coordination")
    logger.info("  !coordination <agent> - Show agent coordination")
    logger.info("  !emotions - Show emotional landscape")
