"""
Database-backed storage for Discord guild custom commands and welcome configs.

Replaces the ephemeral JSON-file storage that was lost on every Railway redeploy.
Falls back to in-memory dicts if DATABASE_URL is not configured (local dev).

Usage from the bot:
    from apps.backend.discord.discord_guild_storage import guild_storage
    await guild_storage.load()
    cmds = guild_storage.custom_commands          # {guild_id: {cmd_name: response}}
    cfgs = guild_storage.welcome_configs          # {guild_id: {enabled, title, message, channel}}
    await guild_storage.save_custom_command(guild_id, name, response, created_by=user_id)
    await guild_storage.delete_custom_command(guild_id, name)
    await guild_storage.save_welcome_config(guild_id, config_dict)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GuildStorage:
    """Manages per-guild custom commands and welcome configs with DB persistence."""

    def __init__(self) -> None:
        self.custom_commands: dict[int, dict[str, str]] = {}
        self.welcome_configs: dict[int, dict[str, Any]] = {}
        self._db_available = False
        self._loaded = False

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load(self) -> None:
        """Load both custom commands and welcome configs from database (or JSON fallback)."""
        if self._loaded:
            return

        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            try:
                await self._load_from_db()
                self._db_available = True
                self._loaded = True
                logger.info(
                    "Guild storage loaded from DB: %s guilds with commands, %s with welcome configs",
                    len(self.custom_commands),
                    len(self.welcome_configs),
                )
                return
            except Exception as e:
                logger.warning("DB load failed, falling back to JSON files: %s", e)

        # Fallback: JSON files on disk
        self._load_commands_from_json()
        self._load_welcome_from_json()
        self._loaded = True

    async def _load_from_db(self) -> None:
        """Load from PostgreSQL via SQLAlchemy async session."""
        from sqlalchemy import select

        from apps.backend.db_models import DiscordGuildCustomCommand, DiscordGuildWelcomeConfig, get_async_session

        session_factory = get_async_session()
        async with session_factory() as session:
            # Custom commands
            result = await session.execute(select(DiscordGuildCustomCommand))
            rows = result.scalars().all()
            for row in rows:
                gid = int(row.guild_id)
                if gid not in self.custom_commands:
                    self.custom_commands[gid] = {}
                self.custom_commands[gid][row.command_name] = row.response

            # Welcome configs
            result = await session.execute(select(DiscordGuildWelcomeConfig))
            rows = result.scalars().all()
            for row in rows:
                gid = int(row.guild_id)
                self.welcome_configs[gid] = {
                    "enabled": row.enabled,
                    "title": row.title or "",
                    "message": row.message or "",
                    "channel": row.channel_name or "",
                }

    # ------------------------------------------------------------------
    # Custom command CRUD
    # ------------------------------------------------------------------

    async def save_custom_command(
        self, guild_id: int, command_name: str, response: str, created_by: str | None = None
    ) -> None:
        """Add or update a custom command, persisting to DB if available."""
        if guild_id not in self.custom_commands:
            self.custom_commands[guild_id] = {}
        self.custom_commands[guild_id][command_name] = response

        if self._db_available:
            try:
                await self._upsert_command_db(guild_id, command_name, response, created_by)
            except Exception as e:
                logger.warning("DB write failed for custom command, using in-memory only: %s", e)
                self._save_commands_to_json()
        else:
            self._save_commands_to_json()

    async def delete_custom_command(self, guild_id: int, command_name: str) -> None:
        """Delete a custom command."""
        if guild_id in self.custom_commands:
            self.custom_commands[guild_id].pop(command_name, None)

        if self._db_available:
            try:
                await self._delete_command_db(guild_id, command_name)
            except Exception as e:
                logger.warning("DB delete failed for custom command: %s", e)
                self._save_commands_to_json()
        else:
            self._save_commands_to_json()

    async def _upsert_command_db(
        self, guild_id: int, command_name: str, response: str, created_by: str | None = None
    ) -> None:
        from sqlalchemy import select

        from apps.backend.db_models import DiscordGuildCustomCommand, get_async_session

        session_factory = get_async_session()
        async with session_factory() as session, session.begin():
            result = await session.execute(
                select(DiscordGuildCustomCommand).where(
                    DiscordGuildCustomCommand.guild_id == str(guild_id),
                    DiscordGuildCustomCommand.command_name == command_name,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.response = response
            else:
                session.add(
                    DiscordGuildCustomCommand(
                        guild_id=str(guild_id),
                        command_name=command_name,
                        response=response,
                        created_by=created_by,
                    )
                )

    async def _delete_command_db(self, guild_id: int, command_name: str) -> None:
        from sqlalchemy import delete

        from apps.backend.db_models import DiscordGuildCustomCommand, get_async_session

        session_factory = get_async_session()
        async with session_factory() as session, session.begin():
            await session.execute(
                delete(DiscordGuildCustomCommand).where(
                    DiscordGuildCustomCommand.guild_id == str(guild_id),
                    DiscordGuildCustomCommand.command_name == command_name,
                )
            )

    # ------------------------------------------------------------------
    # Welcome config CRUD
    # ------------------------------------------------------------------

    async def save_welcome_config(self, guild_id: int, config: dict[str, Any]) -> None:
        """Save a guild's welcome config, persisting to DB if available."""
        self.welcome_configs[guild_id] = config

        if self._db_available:
            try:
                await self._upsert_welcome_db(guild_id, config)
            except Exception as e:
                logger.warning("DB write failed for welcome config: %s", e)
                self._save_welcome_to_json()
        else:
            self._save_welcome_to_json()

    async def _upsert_welcome_db(self, guild_id: int, config: dict[str, Any]) -> None:
        from sqlalchemy import select

        from apps.backend.db_models import DiscordGuildWelcomeConfig, get_async_session

        session_factory = get_async_session()
        async with session_factory() as session, session.begin():
            result = await session.execute(
                select(DiscordGuildWelcomeConfig).where(DiscordGuildWelcomeConfig.guild_id == str(guild_id))
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.enabled = config.get("enabled", True)
                existing.title = config.get("title", "")
                existing.message = config.get("message", "")
                existing.channel_name = config.get("channel", "")
            else:
                session.add(
                    DiscordGuildWelcomeConfig(
                        guild_id=str(guild_id),
                        enabled=config.get("enabled", True),
                        title=config.get("title", ""),
                        message=config.get("message", ""),
                        channel_name=config.get("channel", ""),
                    )
                )

    # ------------------------------------------------------------------
    # Redis fallback (for Railway/production without DATABASE_URL)
    # ------------------------------------------------------------------

    async def _get_redis(self):
        """Get Redis client for fallback storage."""
        try:
            from apps.backend.core.redis_client import get_redis

            return await get_redis()
        except Exception:
            return None

    def _load_commands_from_json(self) -> None:
        """Load custom commands from Redis (primary) or JSON file (legacy fallback)."""
        # Try Redis first
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule async Redis load
                asyncio.create_task(self._load_commands_from_redis())
                return
        except Exception as e:
            logger.debug("Could not schedule async Redis command load, falling back to JSON: %s", e)

        # Fallback to JSON file (local dev only)
        path = self._state_dir() / "custom_commands.json"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.custom_commands = {int(k): v for k, v in raw.items()}
                logger.info("Loaded custom commands for %s guilds from JSON (legacy)", len(self.custom_commands))
            except Exception as e:
                logger.error("Failed to load custom_commands.json: %s", e)

        # Also check env var
        env_json = os.getenv("CUSTOM_COMMANDS_JSON")
        if env_json and not self.custom_commands:
            try:
                self.custom_commands = {int(k): v for k, v in json.loads(env_json).items()}
                logger.info("Loaded custom commands for %s guilds from env", len(self.custom_commands))
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Failed to parse CUSTOM_COMMANDS_JSON: %s", e)

    async def _load_commands_from_redis(self) -> None:
        """Load custom commands from Redis."""
        redis = await self._get_redis()
        if not redis:
            logger.warning("Redis not available for guild storage, using in-memory only")
            return

        try:
            keys = await redis.keys("helix:guild:*:commands")
            for key in keys:
                try:
                    guild_id = int(key.split(":")[2])
                    commands_json = await redis.get(key)
                    if commands_json:
                        self.custom_commands[guild_id] = json.loads(commands_json)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning("Failed to parse Redis key %s: %s", key, e)

            logger.info("Loaded custom commands for %s guilds from Redis", len(self.custom_commands))
        except Exception as e:
            logger.warning("Failed to load commands from Redis: %s", e)

    def _save_commands_to_json(self) -> None:
        """Save custom commands to Redis (primary) or JSON file (legacy fallback)."""
        # Try Redis first
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._save_commands_to_redis())
                return
        except Exception as e:
            logger.debug("Could not schedule async Redis command save, falling back to JSON: %s", e)

        # Fallback to JSON file (local dev only)
        try:
            path = self._state_dir() / "custom_commands.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({str(k): v for k, v in self.custom_commands.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not persist custom commands to JSON: %s", e)

    async def _save_commands_to_redis(self) -> None:
        """Save custom commands to Redis."""
        redis = await self._get_redis()
        if not redis:
            logger.warning("Redis not available for guild storage, using in-memory only")
            return

        try:
            for guild_id, commands in self.custom_commands.items():
                key = f"helix:guild:{guild_id}:commands"
                await redis.set(key, json.dumps(commands), ex=30 * 24 * 3600)  # 30 days TTL
            logger.debug("Saved custom commands for %s guilds to Redis", len(self.custom_commands))
        except Exception as e:
            logger.warning("Failed to save commands to Redis: %s", e)

    def _load_welcome_from_json(self) -> None:
        """Load welcome configs from Redis (primary) or JSON file (legacy fallback)."""
        # Try Redis first
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule async Redis load
                asyncio.create_task(self._load_welcome_from_redis())
                return
        except Exception as e:
            logger.debug("Could not schedule async Redis welcome load, falling back to JSON: %s", e)

        # Fallback to JSON file (local dev only)
        path = self._state_dir() / "welcome_configs.json"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.welcome_configs = {int(k): v for k, v in raw.items()}
                logger.info("Loaded welcome configs for %s guilds from JSON (legacy)", len(self.welcome_configs))
            except Exception as e:
                logger.error("Failed to load welcome_configs.json: %s", e)

    async def _load_welcome_from_redis(self) -> None:
        """Load welcome configs from Redis."""
        redis = await self._get_redis()
        if not redis:
            logger.warning("Redis not available for guild storage, using in-memory only")
            return

        try:
            keys = await redis.keys("helix:guild:*:welcome")
            for key in keys:
                try:
                    guild_id = int(key.split(":")[2])
                    config_json = await redis.get(key)
                    if config_json:
                        self.welcome_configs[guild_id] = json.loads(config_json)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning("Failed to parse Redis key %s: %s", key, e)

            logger.info("Loaded welcome configs for %s guilds from Redis", len(self.welcome_configs))
        except Exception as e:
            logger.warning("Failed to load welcome configs from Redis: %s", e)

    def _save_welcome_to_json(self) -> None:
        """Save welcome configs to Redis (primary) or JSON file (legacy fallback)."""
        # Try Redis first
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._save_welcome_to_redis())
                return
        except Exception as e:
            logger.debug("Could not schedule async Redis welcome save, falling back to JSON: %s", e)

        # Fallback to JSON file (local dev only)
        try:
            path = self._state_dir() / "welcome_configs.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({str(k): v for k, v in self.welcome_configs.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not persist welcome configs to JSON: %s", e)

    async def _save_welcome_to_redis(self) -> None:
        """Save welcome configs to Redis."""
        redis = await self._get_redis()
        if not redis:
            logger.warning("Redis not available for guild storage, using in-memory only")
            return

        try:
            for guild_id, config in self.welcome_configs.items():
                key = f"helix:guild:{guild_id}:welcome"
                await redis.set(key, json.dumps(config), ex=30 * 24 * 3600)  # 30 days TTL
            logger.debug("Saved welcome configs for %s guilds to Redis", len(self.welcome_configs))
        except Exception as e:
            logger.warning("Failed to save welcome configs to Redis: %s", e)

    @staticmethod
    def _state_dir() -> Path:
        base = Path(__file__).resolve().parent.parent
        return base / "Helix" / "state"


# Module-level singleton
guild_storage = GuildStorage()
