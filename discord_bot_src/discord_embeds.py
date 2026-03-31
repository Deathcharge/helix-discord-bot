"""
Discord Embeds - Rich Visual Formatting for Helix Collective Bot
Helix Collective v17.3

Provides rich Discord embed formatting for UCF states, agent profiles,
cycle results, and system status messages.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List

import discord

from apps.backend.coordination.ucf_protocol import UCFProtocol

logger = logging.getLogger(__name__)


class HelixEmbeds:
    """
    Rich Discord embed formatter for Helix Collective bot.
    """

    # Color scheme based on UCF phase
    PHASE_COLORS = {
        "CRITICAL": 0xFF0000,  # Red
        "UNSTABLE": 0xFF6600,  # Orange
        "COHERENT": 0xFFCC00,  # Yellow
        "HARMONIOUS": 0x00FF00,  # Green
        "TRANSCENDENT": 0x9900FF,  # Purple
    }

    # Emoji indicators
    EMOJI = {
        "harmony": "🌀",
        "resilience": "🔄",
        "throughput": "⚡",
        "focus": "👁️",
        "friction": "😌",
        "velocity": "🔭",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
        "agent": "🤖",
        "cycle": "🔮",
        "system": "⚙️",
    }

    @staticmethod
    def create_ucf_state_embed(
        harmony: float,
        resilience: float,
        throughput: float,
        focus: float,
        friction: float,
        velocity: float,
        context: str | None = None,
    ) -> discord.Embed:
        """
        Create a rich embed for UCF state display.

        Args:
            harmony: System coherence (0.0 - 1.0)
            resilience: Recovery capability (0.0 - 2.0)
            throughput: Energy level (0.0 - 1.0)
            focus: Clarity (0.0 - 1.0)
            friction: Suffering (0.0 - 1.0, lower is better)
            velocity: Perspective (0.0 - 2.0)
            context: Optional context message

        Returns:
            Discord Embed object
        """
        phase = UCFProtocol.get_phase(harmony)
        color = HelixEmbeds.PHASE_COLORS.get(phase, 0x808080)

        # Create embed
        embed = discord.Embed(
            title="🌀 UCF State - Universal Coordination Framework",
            description="**Phase:** {}".format(phase),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        # Add context if provided
        if context:
            embed.add_field(name="Context", value=context, inline=False)

        # Core metrics
        harmony_bar = HelixEmbeds._create_progress_bar(harmony, 1.0)
        resilience_bar = HelixEmbeds._create_progress_bar(resilience, 2.0)
        throughput_bar = HelixEmbeds._create_progress_bar(throughput, 1.0)
        focus_bar = HelixEmbeds._create_progress_bar(focus, 1.0)
        friction_bar = HelixEmbeds._create_progress_bar(friction, 1.0, inverse=True)
        velocity_bar = HelixEmbeds._create_progress_bar(velocity, 2.0)

        embed.add_field(
            name="{} Harmony".format(HelixEmbeds.EMOJI["harmony"]),
            value="`{.4f}` {}\nTarget: `0.60`".format(harmony, harmony_bar),
            inline=True,
        )

        embed.add_field(
            name="{} Resilience".format(HelixEmbeds.EMOJI["resilience"]),
            value="`{.4f}` {}\nTarget: `1.00`".format(resilience, resilience_bar),
            inline=True,
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing

        embed.add_field(
            name="{} Throughput".format(HelixEmbeds.EMOJI["throughput"]),
            value="`{.4f}` {}\nTarget: `0.70`".format(throughput, throughput_bar),
            inline=True,
        )

        embed.add_field(
            name="{} Focus".format(HelixEmbeds.EMOJI["focus"]),
            value="`{.4f}` {}\nTarget: `0.70`".format(focus, focus_bar),
            inline=True,
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="{} Friction".format(HelixEmbeds.EMOJI["friction"]),
            value="`{.4f}` {}\nTarget: `0.05`".format(friction, friction_bar),
            inline=True,
        )

        embed.add_field(
            name="{} Velocity".format(HelixEmbeds.EMOJI["velocity"]),
            value="`{.4f}` {}\nTarget: `1.00`".format(velocity, velocity_bar),
            inline=True,
        )

        # Footer
        embed.set_footer(text="Helix Collective v17.3")

        return embed

    @staticmethod
    def create_agent_profile_embed(
        agent_name: str,
        role: str,
        layer: str,
        capabilities: List[str],
        description: str,
        keywords: List[str],
    ) -> discord.Embed:
        """
        Create a rich embed for agent profile display.

        Args:
            agent_name: Name of the agent
            role: Agent's role
            layer: Architecture layer (Coordination/Operational/Integration)
            capabilities: List of capabilities
            description: Agent description
            keywords: Task keywords

        Returns:
            Discord Embed object
        """
        # Layer colors
        layer_colors = {
            "coordination": 0x9900FF,  # Purple
            "operational": 0x00AAFF,  # Blue
            "integration": 0x00FF00,  # Green
        }

        color = layer_colors.get(layer.lower(), 0x808080)

        embed = discord.Embed(
            title="{} {}".format(HelixEmbeds.EMOJI["agent"], agent_name),
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(name="Role", value=role, inline=True)

        embed.add_field(name="Layer", value=layer.title(), inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="Capabilities",
            value="\n".join(["• {}".format(cap.replace("_", " ").title()) for cap in capabilities]),
            inline=False,
        )

        embed.add_field(
            name="Keywords",
            value=", ".join(["`{}`".format(kw) for kw in keywords]),
            inline=False,
        )

        embed.set_footer(text="Helix Collective • {} Layer".format(layer.title()))

        return embed

    @staticmethod
    def create_cycle_result_embed(
        cycle_name: str,
        agent_name: str,
        intention: str,
        harmony_before: float,
        harmony_after: float,
        success: bool,
    ) -> discord.Embed:
        """
        Create a rich embed for cycle result display.

        Args:
            cycle_name: Name of the cycle
            agent_name: Agent performing the cycle
            intention: Cycle intention
            harmony_before: Harmony before cycle
            harmony_after: Harmony after cycle
            success: Whether cycle succeeded

        Returns:
            Discord Embed object
        """
        delta = harmony_after - harmony_before
        color = 0x00FF00 if success else 0xFF6600

        embed = discord.Embed(
            title="{} {}".format(HelixEmbeds.EMOJI["cycle"], cycle_name),
            description=intention,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(name="Agent", value=agent_name, inline=True)

        embed.add_field(
            name="Result",
            value="{} {}".format(
                (HelixEmbeds.EMOJI["success"] if success else HelixEmbeds.EMOJI["warning"]),
                "Success" if success else "Partial",
            ),  # noqa: E501
            inline=True,
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Harmony change
        before_bar = HelixEmbeds._create_progress_bar(harmony_before, 1.0)
        after_bar = HelixEmbeds._create_progress_bar(harmony_after, 1.0)

        embed.add_field(
            name="Harmony Before",
            value=f"`{harmony_before:.4f}` {before_bar}",
            inline=False,
        )

        embed.add_field(
            name="Harmony After",
            value=f"`{harmony_after:.4f}` {after_bar}",
            inline=False,
        )

        # Delta
        delta_emoji = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
        delta_text = f"{delta_emoji} {delta:+.4f}"

        embed.add_field(name="Change", value=delta_text, inline=False)

        embed.set_footer(text="Z-88 Optimization Engine • Helix Collective v17.3")

        return embed

    @staticmethod
    def create_system_status_embed(
        status: str,
        uptime: str,
        ucf_state: Dict[str, float],
        active_agents: int,
        total_agents: int,
    ) -> discord.Embed:
        """
        Create a rich embed for system status display.

        Args:
            status: System status (OPERATIONAL/DEGRADED/CRITICAL)
            uptime: System uptime string
            ucf_state: Current UCF state dict
            active_agents: Number of active agents
            total_agents: Total number of agents

        Returns:
            Discord Embed object
        """
        status_colors = {
            "OPERATIONAL": 0x00FF00,
            "DEGRADED": 0xFFCC00,
            "CRITICAL": 0xFF0000,
        }

        color = status_colors.get(status, 0x808080)
        phase = UCFProtocol.get_phase(ucf_state.get("harmony", 0.0))

        embed = discord.Embed(
            title="{} Helix Collective Status".format(HelixEmbeds.EMOJI["system"]),
            description="**System Status:** {}\n**UCF Phase:** {}".format(status, phase),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(name="Uptime", value=uptime, inline=True)

        embed.add_field(
            name="Active Agents",
            value="{}/{}".format(active_agents, total_agents),
            inline=True,
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Quick UCF metrics
        harmony = ucf_state.get("harmony", 0.0)
        resilience = ucf_state.get("resilience", 0.0)

        embed.add_field(
            name="{} Harmony".format(HelixEmbeds.EMOJI["harmony"]),
            value="`{:.4f}`".format(harmony),
            inline=True,
        )

        embed.add_field(
            name="{} Resilience".format(HelixEmbeds.EMOJI["resilience"]),
            value="`{:.4f}`".format(resilience),
            inline=True,
        )

        embed.set_footer(text="Helix Collective v17.3")

        return embed

    @staticmethod
    def create_error_embed(
        error_title: str,
        error_message: str,
        troubleshooting: list[str] | None = None,
    ) -> discord.Embed:
        """
        Create a rich embed for error messages.

        Args:
            error_title: Error title
            error_message: Error description
            troubleshooting: Optional troubleshooting steps

        Returns:
            Discord Embed object
        """
        embed = discord.Embed(
            title="{} {}".format(HelixEmbeds.EMOJI["error"], error_title),
            description=error_message,
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc),
        )

        if troubleshooting:
            steps = "\n".join(["{}. {}".format(i + 1, step) for i, step in enumerate(troubleshooting)])
            embed.add_field(name="Troubleshooting", value=steps, inline=False)

        embed.set_footer(text="Helix Collective Error Handler")

        return embed

    @staticmethod
    def _create_progress_bar(value: float, max_value: float, length: int = 10, inverse: bool = False) -> str:
        """
        Create a visual progress bar.

        Args:
            value: Current value
            max_value: Maximum value
            length: Bar length in characters
            inverse: If True, lower values are better (for friction)

        Returns:
            Progress bar string
        """
        ratio = min(value / max_value, 1.0) if max_value > 0 else 0.0

        if inverse:
            ratio = 1.0 - ratio

        filled = int(ratio * length)
        empty = length - filled

        # Use different characters for filled/empty
        bar = "█" * filled + "░" * empty

        return "[{}]".format(bar)


# Example usage
if __name__ == "__main__":
    # Test UCF state embed
    ucf_embed = HelixEmbeds.create_ucf_state_embed(
        harmony=0.4922,
        resilience=1.1191,
        throughput=0.5075,
        focus=0.5023,
        friction=0.011,
        velocity=1.0228,
        context="System initialization complete",
    )

    logger.info("UCF State Embed:")
    logger.info("Title: {}".format(ucf_embed.title))
    logger.info("Description: {}".format(ucf_embed.description))
    logger.info("Color: {}".format(hex(ucf_embed.color)))
    logger.info("Fields: {}".format(len(ucf_embed.fields)))

    logger.info("\n" + "=" * 60 + "\n")

    # Test agent profile embed
    agent_embed = HelixEmbeds.create_agent_profile_embed(
        agent_name="Arjuna",
        role="Execution Engine",
        layer="Operational",
        capabilities=["execution", "coordination"],
        description="Hands-on operations, task completion, builder-executor",
        keywords=["execute", "build", "deploy", "implement", "action"],
    )

    logger.info("Agent Profile Embed:")
    logger.info("Title: {}".format(agent_embed.title))
    logger.info("Description: {}".format(agent_embed.description))
    logger.info("Color: {}".format(hex(agent_embed.color)))

    logger.info("\n" + "=" * 60 + "\n")

    # Test cycle result embed
    cycle_embed = HelixEmbeds.create_cycle_result_embed(
        cycle_name="Harmony Restoration",
        agent_name="Omega Zero",
        intention="Restore system coherence after deployment",
        harmony_before=0.4922,
        harmony_after=0.5234,
        success=True,
    )

    logger.info("Cycle Result Embed:")
    logger.info("Title: {}".format(cycle_embed.title))
    logger.info("Description: {}".format(cycle_embed.description))
    logger.info("Color: {}".format(hex(cycle_embed.color)))
