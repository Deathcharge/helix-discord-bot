"""
Helix Discord Integration Package
=================================

This package contains all Discord-related functionality for the Helix platform:
- Discord bot implementations (helix, production, system)
- Discord cog loader and command system
- Webhook senders and channel management
- Voice features and coordination commands
- Multi-agent Discord integration

Modules are imported lazily - use direct imports from submodules:
    # from discord_bot_src.discord_bot_helix import bot
    # from discord_bot_src.discord_webhook_sender import DiscordWebhookSender

NOTE: This package name shadows the 'discord.py' PyPI package.
PYTHONPATH must be set to '.' (project root), NOT '.:apps/backend'.
If PYTHONPATH includes 'apps/backend', then 'import discord' resolves
to this local package instead of the PyPI discord.py package.
"""

__all__ = [
    "agent_bot_factory",
    "discord_bot_helix",
    "discord_cog_loader",
    "discord_webhook_sender",
    "discord_webhook_sender_hybrid",
    "discord_embeds",
    "discord_channel_manager",
    "agent_performance_commands",
    "discord_agentic_commands",
    "discord_bot_system",
    "discord_commands_memory",
    "discord_advanced_commands",
    "discord_agent_swarm_integration",
    "discord_bot_enhancements",
    "discord_i18n",
    "discord_multi_agent_enhancements",
    "discord_voice_features",
    "discord_web_bridge",
    # v17.2 additions
    "discord_memory_commands",
    "discord_autonomous_behaviors",
    "discord_account_commands",
]
