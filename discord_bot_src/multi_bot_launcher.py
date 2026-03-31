"""
Multi-Bot Launcher — Run Multiple Agent Discord Bots From One Process
=====================================================================

Discovers DISCORD_TOKEN_<AGENT> environment variables and launches a
discord.py Bot instance for each one, all running concurrently via asyncio.

Environment Variables:
    DISCORD_TOKEN               — Legacy single-bot token (Arjuna/main bot)
    DISCORD_TOKEN_KAEL          — Token for Kael's bot application
    DISCORD_TOKEN_LUMINA        — Token for Lumina's bot application
    DISCORD_TOKEN_VEGA          — Token for Vega's bot application
    ...                         — Any DISCORD_TOKEN_<AGENT> pattern

If only DISCORD_TOKEN is set (no agent-specific tokens), the launcher
falls back to running the original single Arjuna bot via discord_bot_helix.

Usage (standalone):
    python -m apps.backend.discord.multi_bot_launcher

Usage (from code):
    from apps.backend.discord.multi_bot_launcher import run_all_bots
    run_all_bots()

Railway Config:
    startCommand = "PYTHONPATH=. python -m apps.backend.discord.multi_bot_launcher"

Author: Andrew John Ward (Architect)
Version: v1.0 Multi-Agent Discord
"""

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

from apps.backend.agents import AGENTS
from apps.backend.discord.agent_bot_factory import create_agent_bot

logger = logging.getLogger(__name__)

# All known agent names (used for token discovery)
KNOWN_AGENTS = list(AGENTS.keys())


async def load_customer_tokens() -> list[tuple[str, str, str]]:
    """
    Load active customer Discord bot configs from the database.

    Returns a list of (guild_id, raw_token, label) tuples for all active rows.
    Returns an empty list if the DB is unavailable or the table doesn't exist yet.
    """
    try:
        from sqlalchemy import select

        from apps.backend.byok_management import decrypt_api_key
        from apps.backend.db_models import UserDiscordConfig, get_async_session

        session_factory = get_async_session()
        async with session_factory() as db:
            result = await db.execute(
                select(UserDiscordConfig).where(UserDiscordConfig.is_active == True)  # noqa: E712
            )
            rows = result.scalars().all()

        configs: list[tuple[str, str, str]] = []
        for row in rows:
            try:
                token = decrypt_api_key(row.bot_token)
                label = f"customer:{row.user_id[:8]}:{row.server_name}"
                configs.append((row.guild_id, token, label))
            except Exception as exc:
                logger.warning("⚠️ Could not decrypt token for config %s: %s", row.id, exc)

        if configs:
            logger.info("🗄️  Loaded %d customer Discord bot config(s) from DB", len(configs))
        return configs

    except Exception as exc:
        logger.warning("⚠️  Could not load customer Discord configs from DB: %s", exc)
        return []


def discover_agent_tokens() -> dict[str, str]:
    """
    Discover DISCORD_TOKEN_<AGENT> environment variables.

    Scans for env vars matching the pattern DISCORD_TOKEN_<NAME> where <NAME>
    is an agent name (case-insensitive). Returns a dict mapping agent names
    to their tokens.

    Returns
    -------
    Dict[str, str]
        Mapping of agent name -> Discord bot token.
    """
    tokens: dict[str, str] = {}

    # Check for known agent names
    for agent_name in KNOWN_AGENTS:
        env_key = f"DISCORD_TOKEN_{agent_name.upper()}"
        token = os.getenv(env_key)
        if token:
            tokens[agent_name] = token
            logger.info("🔑 Found token for %s (%s)", agent_name, env_key)

    # Also scan for any DISCORD_TOKEN_ prefixed vars we might have missed
    for key, value in os.environ.items():
        if key.startswith("DISCORD_TOKEN_") and key != "DISCORD_TOKEN_":
            agent_suffix = key[len("DISCORD_TOKEN_") :]
            # Try to match case-insensitively to known agents
            matched = False
            for known in KNOWN_AGENTS:
                if known.upper() == agent_suffix.upper():
                    if known not in tokens:
                        tokens[known] = value
                        logger.info("🔑 Found token for %s (%s)", known, key)
                    matched = True
                    break
            if not matched and agent_suffix:
                # Unknown agent name — still allow it
                tokens[agent_suffix.title()] = value
                logger.info(
                    "🔑 Found token for custom agent %s (%s)",
                    agent_suffix.title(),
                    key,
                )

    return tokens


async def _run_bot(bot: commands.Bot, token: str, agent_name: str) -> None:
    """Run a single bot instance, handling login and connection."""
    try:
        logger.info("🚀 Starting %s bot...", agent_name)
        async with bot:
            await bot.start(token)
    except discord.LoginFailure:
        logger.error(
            "❌ %s: Invalid Discord token — check DISCORD_TOKEN_%s",
            agent_name,
            agent_name.upper(),
        )
    except Exception as e:
        logger.error("❌ %s bot crashed: %s", agent_name, e)


async def launch_multi_bot(
    tokens: dict[str, str],
    *,
    include_main_bot: bool = True,
    main_bot_token: str | None = None,
    customer_tokens: list[tuple[str, str, str]] | None = None,
) -> None:
    """
    Launch multiple agent bots concurrently.

    Parameters
    ----------
    tokens : Dict[str, str]
        Mapping of agent name -> Discord bot token (from env vars).
    include_main_bot : bool
        If True and main_bot_token is provided, also launch the original
        Arjuna bot from discord_bot_helix alongside agent bots.
    main_bot_token : str, optional
        Token for the main Arjuna bot (DISCORD_TOKEN).
    customer_tokens : list of (guild_id, token, label), optional
        Additional bots loaded from the database for customer Discord servers.
    """
    tasks: list[asyncio.Task] = []

    # Create and launch agent bots (from env vars)
    for agent_name, token in tokens.items():
        bot = create_agent_bot(agent_name)
        task = asyncio.create_task(
            _run_bot(bot, token, agent_name),
            name=f"bot-{agent_name}",
        )
        tasks.append(task)

    # Launch customer bots (from DB) — each is an Arjuna-style bot
    for _guild_id, token, label in customer_tokens or []:
        try:
            bot = create_agent_bot("Arjuna")  # Use primary agent persona for customer servers
            task = asyncio.create_task(
                _run_bot(bot, token, label),
                name=f"bot-{label}",
            )
            tasks.append(task)
        except Exception as exc:
            logger.error("❌ Could not create bot for %s: %s", label, exc)

    # Optionally include the main Arjuna bot
    if include_main_bot and main_bot_token:
        try:
            from apps.backend.discord.discord_bot_helix import bot as arjuna_bot

            task = asyncio.create_task(
                _run_bot(arjuna_bot, main_bot_token, "Arjuna (main)"),
                name="bot-Arjuna-main",
            )
            tasks.append(task)
        except ImportError as e:
            logger.warning("⚠️ Could not import main bot: %s", e)

    if not tasks:
        logger.error("❌ No bot tokens found — nothing to launch")
        logger.error("   Set DISCORD_TOKEN and/or DISCORD_TOKEN_<AGENT> env vars")
        return

    agent_list = ", ".join(t.get_name().replace("bot-", "") for t in tasks)
    logger.info(
        "🌀 Launching %d bot(s): %s",
        len(tasks),
        agent_list,
    )

    # Wait for all bots — if one crashes, others continue
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(
                "❌ %s exited with error: %s",
                task.get_name(),
                result,
            )


async def _run_all_bots_async() -> None:
    """Async core of run_all_bots — loads DB customer tokens then launches everything."""
    agent_tokens = discover_agent_tokens()
    main_token = os.getenv("DISCORD_TOKEN")

    # Load customer-supplied bot tokens from DB
    customer_tokens = await load_customer_tokens()

    if not agent_tokens and not main_token and not customer_tokens:
        logger.error("❌ No Discord tokens found in environment or database")
        logger.error("   Set DISCORD_TOKEN for single bot mode")
        logger.error("   Set DISCORD_TOKEN_<AGENT> for multi-bot mode")
        logger.error("   Or add Discord bots via Settings → Integrations in the dashboard")
        sys.exit(1)

    if not agent_tokens and not customer_tokens and main_token:
        # No agent-specific tokens — fall back to single Arjuna bot
        logger.info("📌 Single bot mode (only DISCORD_TOKEN found)")
        logger.info("   To enable multi-bot, set DISCORD_TOKEN_<AGENT> env vars")
        try:
            from apps.backend.discord.discord_bot_helix import main as arjuna_main

            arjuna_main()
        except ImportError:
            logger.error("❌ Could not import discord_bot_helix")
            sys.exit(1)
        return

    # Multi-bot mode
    logger.info("🌀 Multi-bot mode: %d agent token(s) + %d customer bot(s)", len(agent_tokens), len(customer_tokens))

    # Also include main bot if DISCORD_TOKEN is set alongside agent tokens
    include_main = main_token is not None and main_token not in agent_tokens.values()

    if include_main:
        logger.info("   + Arjuna main bot (DISCORD_TOKEN)")

    await launch_multi_bot(
        agent_tokens,
        include_main_bot=include_main,
        main_bot_token=main_token,
        customer_tokens=customer_tokens,
    )


def run_all_bots() -> None:
    """
    Main entry point — discover tokens and launch all agent bots.

    This function:
    1. Discovers DISCORD_TOKEN_<AGENT> env vars
    2. Loads customer Discord bot configs from the database
    3. Falls back to single DISCORD_TOKEN if no agent tokens found
    4. Launches all discovered bots concurrently
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(_run_all_bots_async())


if __name__ == "__main__":
    run_all_bots()
