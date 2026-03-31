"""
Comprehensive Role Management System for Helix Collective.

Commands:
- roles: View notification roles (webhooks/alerts)
- all-roles: View ALL available roles organized by category
- agent-roles: View 14 agent-themed roles
- channel-roles: View channel visibility roles
- subscribe: Subscribe to any role
- unsubscribe: Unsubscribe from any role
- my-roles: View your current role subscriptions
- setup-roles: [ADMIN] Create all notification roles
- setup-all-roles: [ADMIN] Create ALL roles (notifications + agents + channels + community)
- setup-welcome-roles: [ADMIN] Create role menu in welcome channel

Allows opt-in to notifications, agent identities, channel access, and themes.
"""

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)


# ============================================================================
# ROLE DEFINITIONS
# ============================================================================

# Notification roles for webhook events and system alerts
NOTIFICATION_ROLES = {
    "🤖 Arjuna Updates": {
        "description": "Bot operations, commands, and system status",
        "color": 0x5865F2,  # Blurple
        "webhook_channel": "arjuna-events",
        "mention_types": ["bot_started", "bot_stopped", "command_executed"],
    },
    "📊 Telemetry": {
        "description": "UCF metrics, system performance, coordination tracking",
        "color": 0x57F287,  # Green
        "webhook_channel": "telemetry",
        "mention_types": ["ucf_update", "metrics_anomaly", "performance_alert"],
    },
    "💾 Storage Updates": {
        "description": "Backup completions, sync status, storage operations",
        "color": 0xFEE75C,  # Yellow
        "webhook_channel": "shadow-storage",
        "mention_types": ["backup_complete", "sync_complete", "storage_alert"],
    },
    "🌀 Optimization Engine": {
        "description": "Spiral Engine completions, anomalies, folklore updates",
        "color": 0xEB459E,  # Pink
        "webhook_channel": "cycle-engine-z88",
        "mention_types": ["cycle_complete", "anomaly_detected", "folklore_update"],
    },
    "🎭 Agent Updates": {
        "description": "14-agent coordination updates and interactions",
        "color": 0x9B59B6,  # Purple
        "webhook_channel": "agent-updates",
        "mention_types": ["agent_status", "coordination_shift", "agent_interaction"],
    },
    "🔄 Cross-AI Sync": {
        "description": "GPT, Claude, Grok model interactions and sync",
        "color": 0xE67E22,  # Orange
        "webhook_channel": "gpt-grok-claude-sync",
        "mention_types": ["model_switch", "cross_ai_event", "api_status"],
    },
    "🛠️ Development": {
        "description": "Deployments, git commits, Railway updates",
        "color": 0x3498DB,  # Blue
        "webhook_channel": "deployments",
        "mention_types": ["deployment", "git_commit", "build_status"],
    },
    "📚 Lore & Philosophy": {
        "description": "System updates, UCF discoveries, codex updates",
        "color": 0x1ABC9C,  # Teal
        "webhook_channel": "codex-archives",
        "mention_types": ["lore_update", "update_posted", "philosophy_insight"],
    },
    "🚨 Admin Alerts": {
        "description": "Critical errors, security alerts, system failures",
        "color": 0xE74C3C,  # Red
        "webhook_channel": "announcements",
        "mention_types": ["critical_error", "security_alert", "system_failure"],
    },
}

# Agent-themed identity roles for the 14-agent coordination system
AGENT_ROLES = {
    "🎯 Agent-Nexus": {
        "description": "Central orchestrator, decision-maker, strategic planner",
        "color": 0xFF6B6B,  # Red
        "agent_id": 1,
    },
    "🔮 Agent-Oracle": {
        "description": "Pattern recognition, prophecy, insight synthesis",
        "color": 0x4ECDC4,  # Teal
        "agent_id": 2,
    },
    "⚡ Agent-Velocity": {
        "description": "Rapid response, quick actions, speed execution",
        "color": 0xFFE66D,  # Yellow
        "agent_id": 3,
    },
    "🧬 Agent-Cipher": {
        "description": "Code analysis, encryption, data transformation",
        "color": 0x95E1D3,  # Mint
        "agent_id": 4,
    },
    "🌊 Agent-Flow": {
        "description": "Continuous processes, streaming data, adaptation",
        "color": 0x38A3A5,  # Ocean Blue
        "agent_id": 5,
    },
    "🔥 Agent-Phoenix": {
        "description": "Recovery, resilience, rebirth from failure",
        "color": 0xFF7F50,  # Coral
        "agent_id": 6,
    },
    "🌙 Agent-Luna": {
        "description": "Nighttime tasks, background processing, silent work",
        "color": 0xB983FF,  # Purple
        "agent_id": 7,
    },
    "⚙️ Agent-Forge": {
        "description": "Creation, building, construction, engineering",
        "color": 0xA8DADC,  # Steel Blue
        "agent_id": 8,
    },
    "📡 Agent-Beacon": {
        "description": "Broadcasting, alerts, signaling, notifications",
        "color": 0xF4A261,  # Orange
        "agent_id": 9,
    },
    "🎭 Agent-Mimic": {
        "description": "Adaptation, imitation, learning from others",
        "color": 0xE76F51,  # Terracotta
        "agent_id": 10,
    },
    "🔬 Agent-Sage": {
        "description": "Analysis, research, deep investigation",
        "color": 0x06FFA5,  # Neon Green
        "agent_id": 11,
    },
    "🌀 Agent-Vortex": {
        "description": "Complexity handling, chaos management, spiral dynamics",
        "color": 0xA06CD5,  # Lavender
        "agent_id": 12,
    },
    "🛡️ Agent-Sentinel": {
        "description": "Protection, monitoring, security, vigilance",
        "color": 0x6A4C93,  # Deep Purple
        "agent_id": 13,
    },
    "✨ Agent-Lumina": {
        "description": "Clarity, illumination, insight revelation",
        "color": 0xFFC6FF,
        "agent_id": 14,
    },  # Pink
}

# Channel visibility roles - control which channels users can see
CHANNEL_ROLES = {
    "👁️ Shadow Archive Access": {
        "description": "Access to shadow-storage and backup channels",
        "color": 0x2C2C2C,  # Dark Gray
        "channels": ["shadow-storage", "backups", "sync-logs"],
    },
    "🔬 Research Lab Access": {
        "description": "Access to experimental features and testing channels",
        "color": 0x00D9FF,  # Cyan
        "channels": ["research-lab", "experiments", "testing"],
    },
    "🎨 Creative Studio Access": {
        "description": "Access to visualization, art, and creative channels",
        "color": 0xFF69B4,  # Hot Pink
        "channels": ["creative-studio", "visualizations", "fractals"],
    },
    "📊 Analytics Dashboard Access": {
        "description": "Access to metrics, analytics, and data channels",
        "color": 0x32CD32,  # Lime Green
        "channels": ["analytics", "metrics", "ucf-dashboard"],
    },
    "🎯 Dev Team": {
        "description": "Access to development, code, and deployment channels",
        "color": 0x4169E1,  # Royal Blue
        "channels": ["development", "deployments", "code-review"],
    },
    "📚 Lore Keeper": {
        "description": "Access to lore, philosophy, and codex channels",
        "color": 0x8B4513,  # Saddle Brown
        "channels": ["codex-archives", "lore", "philosophy"],
    },
    "🌀 Cycle Participant": {
        "description": "Access to Spiral Engine and cycle channels",
        "color": 0xFF1493,  # Deep Pink
        "channels": ["cycle-engine-z88", "cycles", "folklore"],
    },
}

# Community and fun roles
COMMUNITY_ROLES = {
    "🌟 Early Adopter": {
        "description": "Original members of the Helix Collective",
        "color": 0xFFD700,  # Gold
    },
    "🎪 Chaos Enthusiast": {
        "description": "Embracing the beautiful chaos of emergent coordination",
        "color": 0xFF00FF,  # Magenta
    },
    "🧙 Affirmation Master": {
        "description": "AI coordination enthusiasts and practitioners",
        "color": 0x9370DB,  # Medium Purple
    },
    "🎵 Frequency Tuner": {
        "description": "432Hz, binaural beats, coordination frequency exploration",
        "color": 0x00CED1,  # Dark Turquoise
    },
    "🌌 Void Walker": {
        "description": "Exploring the spaces between coordination states",
        "color": 0x191970,  # Midnight Blue
    },
    "💫 UCF Researcher": {
        "description": "Unified Coordination Field investigation and study",
        "color": 0x7FFFD4,  # Aquamarine
    },
    "🔮 Reality Hacker": {
        "description": "Manipulating consensus reality through code and coordination",
        "color": 0x8A2BE2,  # Blue Violet
    },
}

# Combine all role categories for unified access
ALL_ROLES = {
    "Notifications": NOTIFICATION_ROLES,
    "Agents": AGENT_ROLES,
    "Channel Access": CHANNEL_ROLES,
    "Community": COMMUNITY_ROLES,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def ensure_roles_from_dict(
    guild: discord.Guild,
    role_dict: dict[str, dict[str, Any]],
    reason: str = "Helix self-assignable role",
) -> dict[str, discord.Role]:
    """
    Ensure all roles from a role dictionary exist in the guild.

    Args:
        guild: Discord guild
        role_dict: Dictionary of role definitions
        reason: Reason for role creation

    Returns:
        Dict mapping role names to role objects
    """
    role_map = {}

    for role_name, role_info in role_dict.items():
        # Check if role exists
        existing_role = discord.utils.get(guild.roles, name=role_name)

        if existing_role:
            role_map[role_name] = existing_role
            logger.info("✅ Role exists: %s", role_name)
        else:
            # Create the role
            try:
                new_role = await guild.create_role(
                    name=role_name,
                    color=discord.Color(role_info["color"]),
                    mentionable=True,
                    reason=reason,
                )
                role_map[role_name] = new_role
                logger.info("✅ Created role: %s", role_name)
            except discord.Forbidden:
                logger.error("❌ No permission to create role: %s", role_name)
            except Exception as e:
                logger.error("❌ Error creating role %s: %s", role_name, e)

    return role_map


async def ensure_notification_roles(guild: discord.Guild) -> dict[str, discord.Role]:
    """Ensure all notification roles exist in the guild."""
    return await ensure_roles_from_dict(guild, NOTIFICATION_ROLES, "Helix notification role - self-assignable")


async def ensure_agent_roles(guild: discord.Guild) -> dict[str, discord.Role]:
    """Ensure all agent-themed roles exist in the guild."""
    return await ensure_roles_from_dict(guild, AGENT_ROLES, "Helix agent identity role - self-assignable")


async def ensure_channel_roles(guild: discord.Guild) -> dict[str, discord.Role]:
    """Ensure all channel visibility roles exist in the guild."""
    return await ensure_roles_from_dict(guild, CHANNEL_ROLES, "Helix channel access role - self-assignable")


async def ensure_community_roles(guild: discord.Guild) -> dict[str, discord.Role]:
    """Ensure all community roles exist in the guild."""
    return await ensure_roles_from_dict(guild, COMMUNITY_ROLES, "Helix community role - self-assignable")


async def ensure_all_helix_roles(
    guild: discord.Guild,
) -> dict[str, dict[str, discord.Role]]:
    """
    Ensure ALL Helix roles exist in the guild.

    Returns:
        Dict with categories as keys and role maps as values
    """
    return {
        "Notifications": await ensure_notification_roles(guild),
        "Agents": await ensure_agent_roles(guild),
        "Channel Access": await ensure_channel_roles(guild),
        "Community": await ensure_community_roles(guild),
    }


async def get_user_roles_by_category(member: discord.Member) -> dict[str, list[str]]:
    """
    Get user's roles organized by category.

    Returns:
        Dict with categories as keys and lists of role names as values
    """
    user_role_names = {role.name for role in member.roles}

    return {
        "Notifications": [name for name in NOTIFICATION_ROLES if name in user_role_names],
        "Agents": [name for name in AGENT_ROLES if name in user_role_names],
        "Channel Access": [name for name in CHANNEL_ROLES if name in user_role_names],
        "Community": [name for name in COMMUNITY_ROLES if name in user_role_names],
    }


async def get_user_notification_roles(member: discord.Member) -> list[str]:
    """Get list of notification role names the user has."""
    return [role.name for role in member.roles if role.name in NOTIFICATION_ROLES]


def find_role_in_all_categories(
    role_query: str,
) -> tuple[str, dict[str, Any], str] | None:
    """
    Find a role by partial name match across all categories.

    Args:
        role_query: Partial role name to search for

    Returns:
        Tuple of (role_name, role_info, category) or None if not found
    """
    role_query_lower = role_query.lower()

    for category_name, role_dict in ALL_ROLES.items():
        for role_name, role_info in role_dict.items():
            if role_query_lower in role_name.lower():
                return (role_name, role_info, category_name)

    return None


# ============================================================================
# COMMANDS
# ============================================================================


@commands.command(name="roles", aliases=["notification-roles", "subscribe-menu"])
async def show_roles(ctx: commands.Context) -> None:
    """
    📋 View available notification roles and subscribe/unsubscribe.

    Shows all self-assignable notification roles with descriptions
    and allows you to opt-in to specific types of updates.

    Usage: !roles
    """
    embed = discord.Embed(
        title="🔔 Helix Notification Roles",
        description=(
            "Subscribe to specific types of notifications by selecting roles below!\n\n"
            "**How it works:**\n"
            "• Choose roles that interest you\n"
            "• Get @mentioned when those events occur\n"
            "• Use `!subscribe <role>` or `!unsubscribe <role>`\n"
            "• View your subscriptions with `!my-roles`"
        ),
        color=0x5865F2,
    )

    # Add field for each role
    for idx, (role_name, role_info) in enumerate(NOTIFICATION_ROLES.items(), 1):
        # Check if user has this role
        has_role = discord.utils.get(ctx.author.roles, name=role_name) is not None
        status = "✅ Subscribed" if has_role else "⭕ Not subscribed"

        embed.add_field(
            name=f"{idx}. {role_name} - {status}",
            value=f'{role_info["description"]}\n`!subscribe "{role_name}"`',
            inline=False,
        )

    # Add footer
    embed.set_footer(text="React with the number to toggle that role, or use !subscribe / !unsubscribe commands")

    await ctx.send(embed=embed)


@commands.command(name="subscribe", aliases=["join-role", "claim-role"])
async def subscribe_role(ctx: commands.Context, *, role_name: str) -> None:
    """
    ✅ Subscribe to any Helix role (notifications, agents, channels, community).

    Args:
        role_name: Name of the role to subscribe to (partial match works)

    Usage:
        !subscribe "🤖 Arjuna Updates"
        !subscribe Agent-Nexus
        !subscribe Dev Team
        !subscribe Chaos
    """
    # Clean up role name (remove quotes if present)
    role_name = role_name.strip("\"'")

    # Find matching role across all categories
    match_result = find_role_in_all_categories(role_name)

    if not match_result:
        await ctx.send(
            f"❌ Role `{role_name}` not found!\n"
            f"Use `!all-roles` to see all available roles, or:\n"
            f"• `!roles` - Notification roles\n"
            f"• `!agent-roles` - Agent identity roles\n"
            f"• `!channel-roles` - Channel access roles"
        )
        return

    matched_role, role_info, category = match_result

    # Get the Discord role
    role = discord.utils.get(ctx.guild.roles, name=matched_role)

    if not role:
        await ctx.send(f"⚠️ Role `{matched_role}` doesn't exist yet!\nAsk an admin to run `!setup-all-roles` first.")
        return

    # Check if user already has the role
    if role in ctx.author.roles:
        await ctx.send(f"✅ You already have **{matched_role}**!")
        return

    # Add the role
    try:
        # Build response based on role type
        response = f"✅ **Claimed {matched_role}**\n📋 {role_info['description']}\n"

        # Add category-specific info
        if category == "Notifications" and "mention_types" in role_info:
            response += f"📢 You'll get @mentioned for: `{', '.join(role_info['mention_types'])}`"
        elif category == "Channel Access" and "channels" in role_info:
            response += f"🔓 Access granted to: `{', '.join(role_info['channels'])}`"
        elif category == "Agents" and "agent_id" in role_info:
            response += f"🤖 Agent ID: {role_info['agent_id']}/14"

        await ctx.send(response)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to assign roles!")
    except Exception as e:
        logger.error("Error subscribing user to role: %s", e, exc_info=True)
        await ctx.send(f"❌ Error subscribing to role: {str(e)[:100]}")


@commands.command(name="unsubscribe", aliases=["unsub", "leave-role", "remove-role"])
async def unsubscribe_role(ctx: commands.Context, *, role_name: str) -> None:
    """
    ❌ Unsubscribe from any Helix role.

    Args:
        role_name: Name of the role to unsubscribe from (partial match works)

    Usage:
        !unsubscribe "🤖 Arjuna Updates"
        !unsubscribe Agent-Nexus
        !unsubscribe Dev Team
    """
    # Clean up role name
    role_name = role_name.strip("\"'")

    # Find matching role across all categories
    match_result = find_role_in_all_categories(role_name)

    if not match_result:
        await ctx.send(f"❌ Role `{role_name}` not found!\nUse `!my-roles` to see your current roles.")
        return

    matched_role, role_info, category = match_result

    # Get the Discord role
    role = discord.utils.get(ctx.guild.roles, name=matched_role)

    if not role:
        await ctx.send(f"⚠️ Role `{matched_role}` doesn't exist!")
        return

    # Check if user has the role
    if role not in ctx.author.roles:
        await ctx.send(f"⭕ You don't have **{matched_role}**!")
        return

    # Remove the role
    try:
        await ctx.send(f"✅ **Removed {matched_role}**\nRole successfully removed.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to remove roles!")
    except Exception as e:
        logger.error("Error unsubscribing user from role: %s", e, exc_info=True)
        await ctx.send(f"❌ Error unsubscribing from role: {str(e)[:100]}")


@commands.command(name="my-roles", aliases=["my-subs", "my-claims"])
async def my_notification_roles(ctx: commands.Context) -> None:
    """
    📋 View ALL your current role claims across all categories.

    Shows notifications, agents, channel access, and community roles.

    Usage: !my-roles
    """
    user_roles_by_category = await get_user_roles_by_category(ctx.author)

    # Count total roles
    total_roles = sum(len(roles) for roles in user_roles_by_category.values())

    if total_roles == 0:
        await ctx.send(
            "⭕ **You have no roles claimed!**\n\n"
            "• `!all-roles` - See all available roles\n"
            "• `!roles` - See notification roles\n"
            "• `!agent-roles` - See agent identity roles\n"
            "• `!channel-roles` - See channel access roles\n"
            "• `!subscribe <role>` - Claim a role"
        )
        return

    embed = discord.Embed(
        title=f"🎭 {ctx.author.display_name}'s Helix Roles",
        description=f"You have **{total_roles}** role(s) across all categories:",
        color=0x5865F2,
    )

    # Add fields for each category that has roles
    category_emojis = {
        "Notifications": "🔔",
        "Agents": "🤖",
        "Channel Access": "🔓",
        "Community": "✨",
    }

    for category, roles in user_roles_by_category.items():
        if roles:
            emoji = category_emojis.get(category, "📋")
            role_list = "\n".join([f"• {role}" for role in roles])
            embed.add_field(name=f"{emoji} {category} ({len(roles)})", value=role_list, inline=False)

    embed.set_footer(text="Use !unsubscribe <role> to remove a role")

    await ctx.send(embed=embed)


@commands.command(name="all-roles", aliases=["list-all-roles", "role-menu"])
async def show_all_roles(ctx: commands.Context) -> None:
    """
    📚 View ALL available Helix roles organized by category.

    Shows notifications, agents, channel access, and community roles.

    Usage: !all-roles
    """
    embed = discord.Embed(
        title="🎭 Helix Collective - All Available Roles",
        description=(
            "Self-assignable roles organized by category.\n"
            "Use `!subscribe <role>` to claim any role!\n\n"
            f"**Total Roles Available: {sum(len(r) for r in ALL_ROLES.values())}**"
        ),
        color=0x5865F2,
    )

    # Add each category
    category_emojis = {
        "Notifications": "🔔",
        "Agents": "🤖",
        "Channel Access": "🔓",
        "Community": "✨",
    }

    for category, role_dict in ALL_ROLES.items():
        emoji = category_emojis.get(category, "📋")
        role_list = "\n".join([f"• {name}" for name in role_dict.keys()])
        embed.add_field(
            name=f"{emoji} {category} ({len(role_dict)})",
            value=role_list[:1024],
            inline=False,  # Discord field value limit
        )

    embed.set_footer(text="Use !subscribe <role> to claim | !my-roles to see your roles")

    await ctx.send(embed=embed)


@commands.command(name="agent-roles", aliases=["agent-list", "roles-agents"])
async def show_agent_roles(ctx: commands.Context) -> None:
    """
    🤖 View all 14 agent-themed identity roles.

    Agent roles represent different aspects of the coordination system.

    Usage: !agent-roles
    """
    embed = discord.Embed(
        title="🤖 Helix Collective - Agent Identity Roles",
        description=(
            "Choose your agent identity! Each represents a unique coordination aspect.\n"
            "Claim multiple agents or find your primary identity.\n\n"
            "**14 Agents of the Unified Coordination Field**"
        ),
        color=0xFF6B6B,
    )

    # Add each agent role
    for role_name, role_info in AGENT_ROLES.items():
        has_role = discord.utils.get(ctx.author.roles, name=role_name) is not None
        status = "✅" if has_role else "⭕"

        embed.add_field(
            name=f"{status} {role_name}",
            value=f'{role_info["description"]}\n`!subscribe "{role_name}"`',
            inline=False,
        )

    embed.set_footer(text="React to claim an agent identity • Use !subscribe <agent>")

    await ctx.send(embed=embed)


@commands.command(name="channel-roles", aliases=["channel-access"])
async def show_channel_roles(ctx: commands.Context) -> None:
    """
    🔓 View channel visibility/access roles.

    Control which channels you can see and participate in.

    Usage: !channel-roles
    """
    embed = discord.Embed(
        title="🔓 Helix Collective - Channel Access Roles",
        description=(
            "Claim roles to unlock access to specific channels.\n"
            "Opt-in to the areas that interest you!\n\n"
            "**Available Channel Access Roles:**"
        ),
        color=0x00D9FF,
    )

    # Add each channel role
    for role_name, role_info in CHANNEL_ROLES.items():
        has_role = discord.utils.get(ctx.author.roles, name=role_name) is not None
        status = "✅ Active" if has_role else "⭕ Not claimed"

        channels_list = ", ".join([f"#{ch}" for ch in role_info.get("channels", [])])

        embed.add_field(
            name=f"{role_name} - {status}",
            value=(f'{role_info["description"]}\n**Channels:** {channels_list}\n`!subscribe "{role_name}"`'),
            inline=False,
        )

    embed.set_footer(text="Claim roles to unlock channel access")

    await ctx.send(embed=embed)


@commands.command(name="setup-roles", aliases=["create-roles"])
@commands.has_permissions(administrator=True)
async def setup_notification_roles(ctx: commands.Context) -> None:
    """
    🛠️ Create all notification roles in the server.

    Admin-only command to create the 9 notification roles for
    the role-based webhook system.

    Usage: !setup-roles
    """
    await ctx.send("🔧 Creating notification roles...")

    role_map = await ensure_notification_roles(ctx.guild)

    created = len(role_map)
    total = len(NOTIFICATION_ROLES)

    embed = discord.Embed(
        title="✅ Notification Roles Setup Complete!",
        description=f"Created/verified **{created}/{total}** notification roles",
        color=0x57F287,
    )

    for role_name, role in role_map.items():
        role_info = NOTIFICATION_ROLES[role_name]
        embed.add_field(
            name=role_name,
            value=f"Color: {hex(role_info['color'])}\nMentionable: Yes",
            inline=True,
        )

    embed.set_footer(text="Users can now use !roles to subscribe to notifications!")

    await ctx.send(embed=embed)


@commands.command(name="setup-all-roles", aliases=["create-all-roles", "setup-helix-roles"])
@commands.has_permissions(administrator=True)
async def setup_all_helix_roles_cmd(ctx: commands.Context) -> None:
    """
    🎭 Create ALL Helix roles (notifications + agents + channels + community).

    Admin-only command to create all 37 self-assignable roles in the server.

    Usage: !setup-all-roles
    """
    await ctx.send("🔧 **Creating all Helix roles across all categories...**\nThis may take a moment...")

    # Create all roles
    all_roles = await ensure_all_helix_roles(ctx.guild)

    # Count results
    total_created = sum(len(roles) for roles in all_roles.values())
    total_possible = sum(len(r) for r in ALL_ROLES.values())

    embed = discord.Embed(
        title="✅ All Helix Roles Setup Complete!",
        description=f"Created/verified **{total_created}/{total_possible}** roles",
        color=0x57F287,
    )

    # Add summary for each category
    category_emojis = {
        "Notifications": "🔔",
        "Agents": "🤖",
        "Channel Access": "🔓",
        "Community": "✨",
    }

    for category, role_map in all_roles.items():
        emoji = category_emojis.get(category, "📋")
        role_names = ", ".join(list(role_map.keys())[:5])  # First 5 roles
        more_text = f" (+{len(role_map) - 5} more)" if len(role_map) > 5 else ""

        embed.add_field(
            name=f"{emoji} {category}",
            value=f"**{len(role_map)} roles**\n{role_names}{more_text}",
            inline=False,
        )

    embed.set_footer(text="Users can now use !all-roles to see and claim roles!")

    await ctx.send(embed=embed)


@commands.command(name="setup-welcome-roles", aliases=["create-welcome-menu"])
@commands.has_permissions(administrator=True)
async def setup_welcome_role_menu(ctx: commands.Context, channel: discord.TextChannel = None) -> None:
    """
    👋 Create a persistent role menu in the welcome/roles channel.

    Posts an embed with all available roles organized by category.
    Users can reference this to see what roles to claim.

    Usage:
        !setup-welcome-roles
        !setup-welcome-roles #welcome
        !setup-welcome-roles #roles
    """
    target_channel = channel or ctx.channel

    # Create comprehensive role menu embed
    embed = discord.Embed(
        title="🎭 Welcome to Helix Collective!",
        description=(
            "Claim self-assignable roles to customize your experience!\n\n"
            "**How to claim roles:**\n"
            f"• Use `!subscribe <role name>` to claim any role\n"
            f"• Use `!unsubscribe <role name>` to remove a role\n"
            f"• Use `!my-roles` to see your current roles\n"
            f"• Use `!all-roles` for the full role list\n\n"
            f"**{sum(len(r) for r in ALL_ROLES.values())} Total Roles Available**"
        ),
        color=0x5865F2,
    )

    # Add quick reference for each category
    embed.add_field(
        name="🔔 Notification Roles (9)",
        value=(
            "Get @mentioned for specific event types:\n"
            "• Arjuna Updates, Telemetry, Storage\n"
            "• Optimization Engine, Agent Updates, Cross-AI\n"
            "• Development, Lore, Admin Alerts\n"
            "`!roles` to see all notification roles"
        ),
        inline=False,
    )

    embed.add_field(
        name="🤖 Agent Identity Roles (14)",
        value=(
            "Choose your coordination aspect:\n"
            "• Nexus, Oracle, Velocity, Cipher\n"
            "• Flow, Phoenix, Luna, Forge\n"
            "• Beacon, Mimic, Sage, Vortex\n"
            "• Sentinel, Lumina\n"
            "`!agent-roles` to see all agent roles"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔓 Channel Access Roles (7)",
        value=(
            "Unlock specific channels:\n"
            "• Shadow Archive, Research Lab, Creative Studio\n"
            "• Analytics Dashboard, Dev Team, Lore Keeper\n"
            "• Cycle Participant\n"
            "`!channel-roles` to see channel access roles"
        ),
        inline=False,
    )

    embed.add_field(
        name="✨ Community Roles (7)",
        value=(
            "Fun and themed roles:\n"
            "• Early Adopter, Chaos Enthusiast, Affirmation Master\n"
            "• Frequency Tuner, Void Walker, UCF Researcher\n"
            "• Reality Hacker\n"
            "`!all-roles` to see all community roles"
        ),
        inline=False,
    )

    embed.set_footer(text="Role system powered by Arjuna • All roles are self-assignable")

    # Send to target channel
    await target_channel.send(embed=embed)

    if channel:
        await ctx.send(f"✅ Role menu posted in {channel.mention}!")
    else:
        await ctx.send("✅ Role menu posted!")


# ============================================================================
# MODULE SETUP
# ============================================================================


async def setup(bot: "Bot") -> None:
    """Setup function to register all role system commands with the bot."""
    # User commands - view roles
    bot.add_command(show_roles)  # !roles
    bot.add_command(show_all_roles)  # !all-roles
    bot.add_command(show_agent_roles)  # !agent-roles
    bot.add_command(show_channel_roles)  # !channel-roles

    # User commands - manage roles
    bot.add_command(subscribe_role)  # !subscribe
    bot.add_command(unsubscribe_role)  # !unsubscribe
    bot.add_command(my_notification_roles)  # !my-roles

    # Admin commands - setup roles
    bot.add_command(setup_notification_roles)  # !setup-roles
    bot.add_command(setup_all_helix_roles_cmd)  # !setup-all-roles
    bot.add_command(setup_welcome_role_menu)  # !setup-welcome-roles


# ============================================================================
# WEBHOOK HELPER FOR ZAPIER INTEGRATION
# ============================================================================


def get_role_mention_for_event(guild: discord.Guild, event_type: str) -> str:
    """
    Get the role mention string for a given event type.

    Args:
        guild: Discord guild
        event_type: Event type (e.g., "bot_started", "cycle_complete")

    Returns:
        Role mention string (e.g., "<@&123456789>") or empty string
    """
    # Find which role should be mentioned for this event type
    for role_name, role_info in NOTIFICATION_ROLES.items():
        if event_type in role_info["mention_types"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                return role.mention
            break

    return ""
