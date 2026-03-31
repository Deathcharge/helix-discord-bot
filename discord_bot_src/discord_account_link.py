"""
Discord Account Linking Service

Provides utilities for linking Discord accounts to Helix platform accounts,
looking up subscription tiers for Discord users, and managing consent
preferences from Discord.

This module is used by:
- Backend API routes (POST /api/discord/link, GET /api/discord/status)
- Discord bot commands (!link, !privacy, !subscription)
"""

import json
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.db_models import User

logger = logging.getLogger(__name__)

# ============================================================================
# LINK TOKEN MANAGEMENT (Redis-backed with in-memory fallback)
# ============================================================================

# Redis key prefix for link tokens — each token stored as its own key with TTL
_REDIS_LINK_TOKEN_PREFIX = "helix:discord:link:"

# Write-through cache over Redis
# Key: token (str), Value: dict with user_id, created_at, expires_at
_pending_link_tokens: dict[str, dict] = {}

# Token validity duration
LINK_TOKEN_TTL = timedelta(minutes=15)
_LINK_TOKEN_TTL_SECONDS = int(LINK_TOKEN_TTL.total_seconds())


async def _link_token_redis_set(token: str, data: dict) -> bool:
    """Store a link token in Redis with automatic TTL expiry."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            serializable = {
                "user_id": data["user_id"],
                "created_at": data["created_at"].isoformat(),
                "expires_at": data["expires_at"].isoformat(),
            }
            await r.setex(
                _REDIS_LINK_TOKEN_PREFIX + token,
                _LINK_TOKEN_TTL_SECONDS,
                json.dumps(serializable),
            )
            return True
    except Exception as e:
        logger.warning("Redis write failed for link token: %s", e)
    return False


async def _link_token_redis_get(token: str) -> dict | None:
    """Load a link token from Redis. Returns None if expired or missing."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            val = await r.get(_REDIS_LINK_TOKEN_PREFIX + token)
            if val:
                raw = val if isinstance(val, str) else val.decode()
                data = json.loads(raw)
                # Reconstruct datetimes
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["expires_at"] = datetime.fromisoformat(data["expires_at"])
                return data
    except Exception as e:
        logger.debug("Redis read failed for link token: %s", e)
    return None


async def _link_token_redis_delete(token: str) -> None:
    """Delete a consumed link token from Redis."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            await r.delete(_REDIS_LINK_TOKEN_PREFIX + token)
    except Exception as e:
        logger.debug("Redis delete failed for link token: %s", e)


async def generate_link_token(user_id: str) -> str:
    """
    Generate a one-time token that the user pastes into Discord to link accounts.

    Args:
        user_id: The Helix platform user ID (from JWT auth).

    Returns:
        A URL-safe token string.
    """
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)

    token_data = {
        "user_id": user_id,
        "created_at": now,
        "expires_at": now + LINK_TOKEN_TTL,
    }

    # Persist to Redis (with automatic TTL expiry)
    stored = await _link_token_redis_set(token, token_data)
    if not stored:
        # Fall back to in-memory if Redis is unavailable
        _pending_link_tokens[token] = token_data

    # Expire old in-memory tokens periodically
    _cleanup_expired_tokens()

    logger.info("Generated link token for user %s (expires in %s min)", user_id, LINK_TOKEN_TTL.seconds // 60)
    return token


async def consume_link_token(token: str) -> str | None:
    """
    Validate and consume a link token. Returns the user_id if valid, None otherwise.

    The token is deleted after use (one-time).
    """
    # Try Redis first
    entry = await _link_token_redis_get(token)
    if entry:
        await _link_token_redis_delete(token)
        if datetime.now(UTC) > entry["expires_at"]:
            logger.info("Link token expired for user %s", entry["user_id"])
            return None
        return entry["user_id"]

    # Fall back to in-memory store
    _cleanup_expired_tokens()
    entry = _pending_link_tokens.pop(token, None)
    if entry is None:
        return None

    if datetime.now(UTC) > entry["expires_at"]:
        logger.info("Link token expired for user %s", entry["user_id"])
        return None

    return entry["user_id"]


def _cleanup_expired_tokens() -> None:
    """Remove expired tokens from memory."""
    now = datetime.now(UTC)
    expired = [t for t, v in _pending_link_tokens.items() if now > v["expires_at"]]
    for t in expired:
        del _pending_link_tokens[t]


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================


async def link_discord_account(db: AsyncSession, user_id: str, discord_id: str) -> tuple[bool, str]:
    """
    Link a Discord account to a Helix platform user.

    Returns:
        (success: bool, message: str)
    """
    # Check if this Discord ID is already linked to another account
    result = await db.execute(select(User).where(User.discord_id == discord_id))
    existing = result.scalar_one_or_none()

    if existing and existing.id != user_id:
        return False, "This Discord account is already linked to another Helix account."

    if existing and existing.id == user_id:
        return True, "Your Discord account is already linked."

    # Check target user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False, "Helix user account not found."

    # Link
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            discord_id=discord_id,
            discord_linked_at=datetime.now(UTC),
        )
    )
    await db.commit()

    logger.info(
        "Linked Discord %s to Helix user %s (%s)",
        discord_id,
        user_id,
        user.email,
    )
    return True, "Discord account linked successfully!"


async def unlink_discord_account(db: AsyncSession, user_id: str) -> tuple[bool, str]:
    """
    Unlink a Discord account from a Helix platform user.

    Returns:
        (success: bool, message: str)
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False, "Helix user account not found."

    if not user.discord_id:
        return False, "No Discord account is currently linked."

    await db.execute(update(User).where(User.id == user_id).values(discord_id=None, discord_linked_at=None))
    await db.commit()

    logger.info("Unlinked Discord from Helix user %s", user_id)
    return True, "Discord account unlinked."


async def get_user_by_discord_id(db: AsyncSession, discord_id: str) -> User | None:
    """
    Look up a Helix User by their linked Discord ID.

    Returns None if no account is linked.
    """
    result = await db.execute(select(User).where(User.discord_id == discord_id))
    return result.scalar_one_or_none()


async def get_subscription_tier_for_discord(db: AsyncSession, discord_id: str) -> str | None:
    """
    Get the subscription tier for a Discord user's linked Helix account.

    Returns:
        Tier string ('free', 'hobby', 'starter', 'pro', 'enterprise') or None if unlinked.
    """
    user = await get_user_by_discord_id(db, discord_id)
    if user is None:
        return None

    return user.subscription_tier or "free"


async def get_discord_link_status(db: AsyncSession, user_id: str) -> dict:
    """
    Get Discord link status for a Helix user (used by web dashboard).

    Returns dict with linked, discord_id, linked_at fields.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return {"linked": False, "discord_id": None, "linked_at": None}

    return {
        "linked": user.discord_id is not None,
        "discord_id": user.discord_id,
        "linked_at": user.discord_linked_at.isoformat() if user.discord_linked_at else None,
    }
