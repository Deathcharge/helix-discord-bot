"""
🔌 DISCORD COG LOADER

Automatically loads all Discord cogs for the Helix bot.
Includes command cogs, agent swarm integration, and multi-agent enhancements.
"""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)

# All cogs to load - organized by category
DISCORD_COGS = [
    # Core Discord integration cogs
    "apps.backend.discord.discord_agent_swarm_integration",
    "apps.backend.discord.discord_multi_agent_enhancements",
    "apps.backend.discord.discord_advanced_commands",
    "apps.backend.discord.discord_voice_features",
    "apps.backend.discord.discord_commands_memory",
    # v17.2 additions
    "apps.backend.discord.discord_memory_commands",
    "apps.backend.discord.discord_autonomous_behaviors",
    "apps.backend.discord.discord_account_commands",
    # v17.4 — slash commands + interactive components
    "apps.backend.discord.discord_slash_commands",
]

# Command cogs from /apps/backend/discord/commands/
COMMAND_COGS = [
    "apps.backend.discord.commands.admin_commands",
    "apps.backend.discord.commands.advanced_commands",
    "apps.backend.discord.commands.performance_commands_ext",
    "apps.backend.discord.commands.content_commands",
    "apps.backend.discord.commands.context_commands",
    "apps.backend.discord.commands.execution_commands",
    "apps.backend.discord.commands.fun_minigames",
    "apps.backend.discord.commands.help_commands",
    "apps.backend.discord.commands.image_commands",
    "apps.backend.discord.commands.monitoring_commands",
    "apps.backend.discord.commands.portal_deployment_commands",
    "apps.backend.discord.commands.optimization_commands",
    "apps.backend.discord.commands.role_system",
    "apps.backend.discord.commands.testing_commands",
    "apps.backend.discord.commands.visualization_commands",
    "apps.backend.discord.commands.scheduled_content_commands",
    "apps.backend.discord.commands.moderation_commands",
    "apps.backend.discord.commands.voice_commands",
]

# Combined list of all cogs
ALL_COGS = DISCORD_COGS + COMMAND_COGS


async def load_helix_cogs(bot: commands.Bot):
    """
    Load all Helix Discord cogs.

    Cogs loaded:
    - Discord integration cogs (agent swarm, multi-agent, voice, memory)
    - Command cogs (admin, advanced, coordination, content, context, etc.)
    - Scheduled content cog (automated channel updates)

    Total: 80+ commands across 22 cog files
    """
    loaded_cogs = []
    failed_cogs = []

    for cog_path in ALL_COGS:
        try:
            await bot.load_extension(cog_path)
            loaded_cogs.append(cog_path)
            logger.info("✅ Loaded cog: %s", cog_path)
        except commands.ExtensionAlreadyLoaded:
            logger.debug("⏭️ Cog already loaded: %s", cog_path)
            loaded_cogs.append(cog_path)
        except commands.ExtensionNotFound:
            logger.warning("⚠️ Cog not found: %s", cog_path)
            failed_cogs.append((cog_path, "Extension not found"))
        except commands.NoEntryPointError:
            logger.warning("⚠️ Cog has no setup function: %s", cog_path)
            failed_cogs.append((cog_path, "No setup() function"))
        except Exception as e:
            failed_cogs.append((cog_path, str(e)))
            logger.error("❌ Failed to load cog %s: %s", cog_path, e, exc_info=True)

    # Log summary
    logger.info(
        "🔌 Cog loading complete: %d loaded, %d failed",
        len(loaded_cogs),
        len(failed_cogs),
    )

    if failed_cogs:
        logger.warning("Failed cogs:")
        for cog_path, error in failed_cogs:
            logger.warning("  - %s: %s", cog_path, error)

    return {"loaded": loaded_cogs, "failed": failed_cogs}


async def reload_helix_cogs(bot: commands.Bot):
    """Reload all Helix cogs (useful for development)."""
    reloaded = []
    failed = []

    for cog_path in ALL_COGS:
        try:
            await bot.reload_extension(cog_path)
            reloaded.append(cog_path)
            logger.info("🔄 Reloaded cog: %s", cog_path)
        except commands.ExtensionNotLoaded:
            # Try loading if not already loaded
            try:
                await bot.load_extension(cog_path)
                reloaded.append(cog_path)
                logger.info("✅ Loaded cog (was not loaded): %s", cog_path)
            except Exception as e:
                failed.append((cog_path, str(e)))
                logger.error("❌ Failed to load cog %s: %s", cog_path, e)
        except Exception as e:
            failed.append((cog_path, str(e)))
            logger.error("❌ Failed to reload cog %s: %s", cog_path, e, exc_info=True)

    return {"reloaded": reloaded, "failed": failed}


async def unload_helix_cogs(bot: commands.Bot):
    """Unload all Helix cogs."""
    unloaded = []
    failed = []

    for cog_path in ALL_COGS:
        try:
            await bot.unload_extension(cog_path)
            unloaded.append(cog_path)
            logger.info("🔻 Unloaded cog: %s", cog_path)
        except commands.ExtensionNotLoaded:
            logger.debug("⏭️ Cog not loaded: %s", cog_path)
        except Exception as e:
            failed.append((cog_path, str(e)))
            logger.error("❌ Failed to unload cog %s: %s", cog_path, e)

    return {"unloaded": unloaded, "failed": failed}


def get_cog_status(bot: commands.Bot) -> dict:
    """Get status of all loaded cogs."""
    loaded_cogs = list(bot.cogs.keys())

    return {
        "loaded_cogs": loaded_cogs,
        "total_commands": len(bot.commands),
        "cog_count": len(bot.cogs),
        "expected_cogs": len(ALL_COGS),
        "missing_cogs": [
            cog for cog in ALL_COGS if cog.split(".")[-1] not in [c.lower().replace("cog", "") for c in loaded_cogs]
        ],
    }


def get_all_cog_paths() -> list:
    """Return list of all cog paths for external use."""
    return ALL_COGS.copy()
