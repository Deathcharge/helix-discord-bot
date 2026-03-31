"""
🛡️ Moderation Commands for Helix Discord Bot.

Server management and moderation tools:
- warn: Issue warnings to users
- mute/timeout: Temporarily silence users
- kick/ban: Remove users from server
- purge: Bulk delete messages
- slowmode: Manage channel slowmode
- mod-log: View moderation history
- serverinfo: Server statistics
- userinfo: User information
"""

import datetime
import json
import logging
import os
from collections import defaultdict

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# In-memory moderation log (persisted to file when available)
MOD_LOG_FILE = os.environ.get("MOD_LOG_FILE", "")
MOD_LOG_CHANNEL_ID = int(os.environ.get("DISCORD_MOD_LOG_CHANNEL_ID", "0"))

# Warn thresholds
WARN_THRESHOLD_MUTE = 3  # Auto-mute after 3 warnings
WARN_THRESHOLD_KICK = 5  # Auto-kick after 5 warnings

# Redis keys
_REDIS_KEY_WARNINGS = "helix:discord:mod:warnings"
_REDIS_KEY_MOD_ACTIONS = "helix:discord:mod:actions"

# In-memory caches (populated from Redis on read, always written through)
_warnings: dict[int, list[dict]] = defaultdict(list)
_mod_actions: list[dict] = []


async def _mod_redis_get_warnings(member_id: int) -> list[dict] | None:
    """Load warnings for a member from Redis."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            val = await r.hget(_REDIS_KEY_WARNINGS, str(member_id))
            if val:
                raw = val if isinstance(val, str) else val.decode()
                return json.loads(raw)
    except Exception as e:
        logger.debug("Redis read failed for warnings[%s]: %s", member_id, e)
    return None


async def _mod_redis_set_warnings(member_id: int, data: list[dict]) -> None:
    """Persist warnings for a member to Redis."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            await r.hset(_REDIS_KEY_WARNINGS, str(member_id), json.dumps(data))
        else:
            logger.warning("Redis unavailable — warnings for member %s will not persist", member_id)
    except Exception as e:
        logger.warning("Redis write failed for warnings[%s]: %s", member_id, e)


async def _mod_redis_append_action(record: dict) -> None:
    """Append a moderation action to the Redis list (capped at 1000)."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            await r.rpush(_REDIS_KEY_MOD_ACTIONS, json.dumps(record))
            # Trim to last 1000 entries
            await r.ltrim(_REDIS_KEY_MOD_ACTIONS, -1000, -1)
        else:
            logger.warning("Redis unavailable — mod action will not persist")
    except Exception as e:
        logger.warning("Redis write failed for mod action: %s", e)


async def _mod_redis_get_actions(count: int = 25) -> list[dict]:
    """Load recent moderation actions from Redis."""
    try:
        from apps.backend.core.redis_client import get_redis

        r = await get_redis()
        if r:
            raw_list = await r.lrange(_REDIS_KEY_MOD_ACTIONS, -count, -1)
            return [json.loads(item if isinstance(item, str) else item.decode()) for item in raw_list]
    except Exception as e:
        logger.debug("Redis read failed for mod actions: %s", e)
    return []


async def _ensure_warnings_loaded(member_id: int) -> None:
    """Ensure warnings for a member are in the in-memory cache."""
    if member_id not in _warnings:
        redis_warns = await _mod_redis_get_warnings(member_id)
        if redis_warns:
            _warnings[member_id] = redis_warns


async def _record_action(
    action: str,
    moderator: discord.Member,
    target: discord.Member,
    reason: str,
    guild_id: int,
    duration: str | None = None,
) -> dict:
    """Record a moderation action to Redis (with in-memory cache)."""
    record = {
        "action": action,
        "moderator_id": moderator.id,
        "moderator_name": str(moderator),
        "target_id": target.id,
        "target_name": str(target),
        "reason": reason,
        "guild_id": guild_id,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if duration:
        record["duration"] = duration
    _mod_actions.append(record)

    # Keep last 1000 actions in memory
    if len(_mod_actions) > 1000:
        _mod_actions.pop(0)

    # Persist to Redis
    await _mod_redis_append_action(record)

    return record


async def _send_mod_log(bot: commands.Bot, guild: discord.Guild, embed: discord.Embed) -> None:
    """Send an embed to the mod-log channel if configured."""
    if MOD_LOG_CHANNEL_ID:
        channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.warning("Failed to send to mod-log channel: %s", e)
            return

    # Fallback: look for a channel named mod-log
    channel = discord.utils.get(guild.text_channels, name="mod-log")
    if not channel:
        channel = discord.utils.get(guild.text_channels, name="🔨│mod-log")
    if channel:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning("Failed to send to mod-log channel: %s", e)


# ============================================================================
# WARN
# ============================================================================


@commands.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_user(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
    """
    ⚠️ Issue a warning to a user.

    Warnings are tracked and can trigger auto-moderation at thresholds.
    - 3 warnings → auto-timeout (10 min)
    - 5 warnings → auto-kick

    Usage: !warn @user Spamming in general
    """
    if member.bot:
        await ctx.send("❌ Cannot warn bots.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot warn someone with equal or higher role.")
        return

    # Record warning
    await _ensure_warnings_loaded(member.id)
    warning = {
        "reason": reason,
        "moderator": str(ctx.author),
        "moderator_id": ctx.author.id,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    _warnings[member.id].append(warning)
    warn_count = len(_warnings[member.id])

    # Persist to Redis
    await _mod_redis_set_warnings(member.id, _warnings[member.id])

    await _record_action("warn", ctx.author, member, reason, ctx.guild.id)

    # Build response
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        color=discord.Color.yellow(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
    embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
    embed.set_footer(text="Helix Moderation • Tat Tvam Asi 🌀")

    await ctx.send(embed=embed)
    await _send_mod_log(ctx.bot, ctx.guild, embed)

    # Auto-moderation thresholds
    if warn_count >= WARN_THRESHOLD_KICK:
        try:
            await member.kick(reason=f"Auto-kick: {warn_count} warnings")
            await ctx.send(f"🚪 **{member.name}** auto-kicked after {warn_count} warnings.")
        except discord.Forbidden:
            await ctx.send("⚠️ Auto-kick failed — insufficient permissions.")
    elif warn_count >= WARN_THRESHOLD_MUTE:
        try:
            duration = datetime.timedelta(minutes=10)
            await member.timeout(duration, reason=f"Auto-timeout: {warn_count} warnings")
            await ctx.send(f"🔇 **{member.name}** auto-timed out for 10 minutes ({warn_count} warnings).")
        except discord.Forbidden:
            await ctx.send("⚠️ Auto-timeout failed — insufficient permissions.")


@commands.command(name="warnings")
@commands.has_permissions(manage_messages=True)
async def check_warnings(ctx: commands.Context, member: discord.Member) -> None:
    """
    📋 View warnings for a user.

    Usage: !warnings @user
    """
    await _ensure_warnings_loaded(member.id)
    user_warnings = _warnings.get(member.id, [])

    if not user_warnings:
        await ctx.send(f"✅ **{member.display_name}** has no warnings.")
        return

    embed = discord.Embed(
        title=f"📋 Warnings for {member.display_name}",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    for i, w in enumerate(user_warnings[-10:], 1):  # Show last 10
        embed.add_field(
            name=f"Warning #{i}",
            value="**Reason:** {}\n**By:** {}\n**Date:** {}".format(
                w["reason"],
                w["moderator"],
                w["timestamp"][:10],
            ),
            inline=False,
        )

    embed.set_footer(text=f"Total warnings: {len(user_warnings)} • Helix Moderation")
    await ctx.send(embed=embed)


@commands.command(name="clearwarnings", aliases=["clear-warnings"])
@commands.has_permissions(administrator=True)
async def clear_warnings(ctx: commands.Context, member: discord.Member) -> None:
    """
    🧹 Clear all warnings for a user.

    Usage: !clearwarnings @user
    """
    await _ensure_warnings_loaded(member.id)
    count = len(_warnings.get(member.id, []))
    _warnings[member.id] = []
    await _mod_redis_set_warnings(member.id, [])
    await _record_action("clearwarnings", ctx.author, member, f"Cleared {count} warnings", ctx.guild.id)
    await ctx.send(f"✅ Cleared **{count}** warnings for **{member.display_name}**.")


# ============================================================================
# TIMEOUT / MUTE
# ============================================================================


@commands.command(name="timeout", aliases=["mute"])
@commands.has_permissions(moderate_members=True)
async def timeout_user(
    ctx: commands.Context,
    member: discord.Member,
    duration: str = "10m",
    *,
    reason: str = "No reason provided",
) -> None:
    """
    🔇 Timeout (mute) a user for a specified duration.

    Duration format: 1m, 5m, 10m, 30m, 1h, 6h, 12h, 1d, 7d, 28d
    Maximum: 28 days (Discord limit)

    Usage:
        !timeout @user 10m Spamming
        !mute @user 1h Being disruptive
    """
    if member.bot:
        await ctx.send("❌ Cannot timeout bots.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot timeout someone with equal or higher role.")
        return

    # Parse duration
    duration_map = {
        "1m": datetime.timedelta(minutes=1),
        "5m": datetime.timedelta(minutes=5),
        "10m": datetime.timedelta(minutes=10),
        "30m": datetime.timedelta(minutes=30),
        "1h": datetime.timedelta(hours=1),
        "6h": datetime.timedelta(hours=6),
        "12h": datetime.timedelta(hours=12),
        "1d": datetime.timedelta(days=1),
        "7d": datetime.timedelta(days=7),
        "28d": datetime.timedelta(days=28),
    }

    td = duration_map.get(duration.lower())
    if not td:
        await ctx.send("❌ Invalid duration. Use: {}".format(", ".join(duration_map.keys())))
        return

    try:
        await member.timeout(td, reason=f"{reason} (by {ctx.author})")
        await _record_action("timeout", ctx.author, member, reason, ctx.guild.id, duration=duration)

        embed = discord.Embed(
            title="🔇 User Timed Out",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Helix Moderation • Tat Tvam Asi 🌀")

        await ctx.send(embed=embed)
        await _send_mod_log(ctx.bot, ctx.guild, embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout this user.")


@commands.command(name="untimeout", aliases=["unmute"])
@commands.has_permissions(moderate_members=True)
async def untimeout_user(ctx: commands.Context, member: discord.Member) -> None:
    """
    🔊 Remove timeout from a user.

    Usage: !untimeout @user
    """
    try:
        await member.timeout(None, reason=f"Timeout removed by {ctx.author}")
        await _record_action("untimeout", ctx.author, member, "Timeout removed", ctx.guild.id)
        await ctx.send(f"✅ Timeout removed for **{member.display_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to remove this timeout.")


# ============================================================================
# KICK / BAN
# ============================================================================


@commands.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_user(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
    """
    🚪 Kick a user from the server.

    Usage: !kick @user Being disruptive
    """
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot kick someone with equal or higher role.")
        return

    try:
        # DM the user before kicking
        try:
            dm_embed = discord.Embed(
                title=f"🚪 You've been kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.red(),
            )
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # Can't DM, proceed anyway

        await member.kick(reason=f"{reason} (by {ctx.author})")
        await _record_action("kick", ctx.author, member, reason, ctx.guild.id)

        embed = discord.Embed(
            title="🚪 User Kicked",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
        embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Helix Moderation • Tat Tvam Asi 🌀")

        await ctx.send(embed=embed)
        await _send_mod_log(ctx.bot, ctx.guild, embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user.")


@commands.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_user(
    ctx: commands.Context,
    member: discord.Member,
    delete_days: int = 1,
    *,
    reason: str = "No reason provided",
) -> None:
    """
    🔨 Ban a user from the server.

    Args:
        member: User to ban
        delete_days: Days of messages to delete (0-7, default 1)
        reason: Ban reason

    Usage: !ban @user 1 Repeated violations
    """
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot ban someone with equal or higher role.")
        return

    delete_days = max(0, min(7, delete_days))

    try:
        # DM the user before banning
        try:
            dm_embed = discord.Embed(
                title=f"🔨 You've been banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.dark_red(),
            )
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.debug("Could not DM ban notice to %s: %s", member, exc)

        await member.ban(
            reason=f"{reason} (by {ctx.author})",
            delete_message_days=delete_days,
        )
        await _record_action("ban", ctx.author, member, reason, ctx.guild.id)

        embed = discord.Embed(
            title="🔨 User Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="User", value=str(member), inline=True)
        embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
        embed.add_field(name="Messages Deleted", value=f"{delete_days} days", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Helix Moderation • Tat Tvam Asi 🌀")

        await ctx.send(embed=embed)
        await _send_mod_log(ctx.bot, ctx.guild, embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user.")


@commands.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_user(ctx: commands.Context, *, user_input: str) -> None:
    """
    ✅ Unban a user by name#discriminator or user ID.

    Usage:
        !unban username#1234
        !unban 123456789012345678
    """
    banned_users = [entry async for entry in ctx.guild.bans()]

    target = None
    # Try by ID
    if user_input.isdigit():
        user_id = int(user_input)
        for entry in banned_users:
            if entry.user.id == user_id:
                target = entry.user
                break
    else:
        # Try by name
        for entry in banned_users:
            if str(entry.user).lower() == user_input.lower() or entry.user.name.lower() == user_input.lower():
                target = entry.user
                break

    if not target:
        await ctx.send("❌ User not found in ban list.")
        return

    try:
        await ctx.guild.unban(target, reason=f"Unbanned by {ctx.author}")
        await ctx.send(f"✅ **{target}** has been unbanned.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban users.")


# ============================================================================
# PURGE / CLEAN
# ============================================================================


@commands.command(name="purge", aliases=["clear-messages"])
@commands.has_permissions(manage_messages=True)
async def purge_messages(
    ctx: commands.Context,
    count: int = 10,
    member: discord.Member | None = None,
) -> None:
    """
    🧹 Bulk delete messages from the current channel.

    Args:
        count: Number of messages to delete (1-100, default 10)
        member: Optional - only delete messages from this user

    Usage:
        !purge 20
        !purge 50 @user
    """
    count = max(1, min(100, count))

    def check(msg):
        if member:
            return msg.author == member
        return True

    try:
        deleted = await ctx.channel.purge(limit=count + 1, check=check)  # +1 for the command message
        confirm = await ctx.send(
            "🧹 Deleted **{}** messages.{}".format(
                len(deleted) - 1,
                f" (from {member.display_name})" if member else "",
            )
        )

        # Auto-delete confirmation after 5 seconds
        import asyncio

        await asyncio.sleep(5)
        try:
            await confirm.delete()
        except discord.NotFound:
            pass

        await _record_action(
            "purge",
            ctx.author,
            member or ctx.author,
            f"Purged {len(deleted) - 1} messages",
            ctx.guild.id,
        )

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete messages.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Failed to purge messages: {str(e)[:100]}")


# ============================================================================
# SLOWMODE
# ============================================================================


@commands.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def set_slowmode(ctx: commands.Context, seconds: int = 0) -> None:
    """
    🐌 Set slowmode delay for the current channel.

    Args:
        seconds: Slowmode delay in seconds (0 to disable, max 21600 = 6 hours)

    Usage:
        !slowmode 10
        !slowmode 0   (disable)
    """
    seconds = max(0, min(21600, seconds))

    try:
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("✅ Slowmode **disabled** for this channel.")
        else:
            await ctx.send(f"✅ Slowmode set to **{seconds} seconds** for this channel.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change slowmode.")


# ============================================================================
# SERVER INFO / USER INFO
# ============================================================================


@commands.command(name="serverinfo", aliases=["server-info", "guild-info"])
async def server_info(ctx: commands.Context) -> None:
    """
    📊 Display comprehensive server statistics.

    Usage: !serverinfo
    """
    guild = ctx.guild

    # Count members by status
    online = sum(1 for m in guild.members if m.status == discord.Status.online)
    idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
    dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
    offline = sum(1 for m in guild.members if m.status == discord.Status.offline)

    # Channel counts
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    forums = len([c for c in guild.channels if isinstance(c, discord.ForumChannel)])

    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Owner", value=str(guild.owner), inline=True)
    embed.add_field(
        name="Created",
        value=f"<t:{int(guild.created_at.timestamp())}:R>",
        inline=True,
    )
    embed.add_field(name="Server ID", value=str(guild.id), inline=True)

    embed.add_field(
        name=f"Members ({guild.member_count})",
        value=(f"🟢 Online: {online}\n" f"🟡 Idle: {idle}\n" f"🔴 DND: {dnd}\n" f"⚫ Offline: {offline}\n" f"🤖 Bots: {sum(1 for m in guild.members if m.bot)}"),
        inline=True,
    )

    embed.add_field(
        name=f"Channels ({text_channels + voice_channels})",
        value=(f"💬 Text: {text_channels}\n" f"🔊 Voice: {voice_channels}\n" f"📁 Categories: {categories}\n" f"💭 Forums: {forums}"),
        inline=True,
    )

    embed.add_field(
        name="Boost",
        value=f"Level {guild.premium_tier} ({guild.premium_subscription_count or 0} boosts)",
        inline=True,
    )

    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Emojis", value=str(len(guild.emojis)), inline=True)
    embed.add_field(
        name="Verification Level",
        value=str(guild.verification_level).capitalize(),
        inline=True,
    )

    if guild.features:
        feature_list = ", ".join(f.replace("_", " ").title() for f in guild.features[:8])
        embed.add_field(name="Features", value=feature_list, inline=False)

    embed.set_footer(text="Helix Server Info • Tat Tvam Asi 🌀")
    await ctx.send(embed=embed)


@commands.command(name="userinfo", aliases=["user-info", "whois"])
async def user_info(ctx: commands.Context, member: discord.Member | None = None) -> None:
    """
    👤 Display detailed information about a user.

    Usage:
        !userinfo
        !userinfo @user
    """
    member = member or ctx.author

    roles = [r.mention for r in member.roles[1:]]  # Skip @everyone
    roles.reverse()

    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)

    embed.add_field(name="Username", value=str(member), inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Bot", value="✅ Yes" if member.bot else "❌ No", inline=True)

    embed.add_field(
        name="Account Created",
        value=f"<t:{int(member.created_at.timestamp())}:R>",
        inline=True,
    )
    embed.add_field(
        name="Joined Server",
        value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown",
        inline=True,
    )

    if member.premium_since:
        embed.add_field(
            name="Boosting Since",
            value=f"<t:{int(member.premium_since.timestamp())}:R>",
            inline=True,
        )

    if roles:
        role_text = " ".join(roles[:15])
        if len(roles) > 15:
            role_text += f" (+{len(roles) - 15} more)"
        embed.add_field(name=f"Roles ({len(roles)})", value=role_text, inline=False)

    # Moderation info
    await _ensure_warnings_loaded(member.id)
    user_warns = _warnings.get(member.id, [])
    if user_warns:
        embed.add_field(name="⚠️ Warnings", value=str(len(user_warns)), inline=True)

    if member.is_timed_out():
        embed.add_field(
            name="🔇 Timed Out Until",
            value=f"<t:{int(member.timed_out_until.timestamp())}:R>",
            inline=True,
        )

    embed.set_footer(text="Helix User Info • Tat Tvam Asi 🌀")
    await ctx.send(embed=embed)


# ============================================================================
# MOD LOG
# ============================================================================


@commands.command(name="modlog", aliases=["mod-log", "audit"])
@commands.has_permissions(manage_messages=True)
async def mod_log(ctx: commands.Context, count: int = 10) -> None:
    """
    📋 View recent moderation actions.

    Usage:
        !modlog
        !modlog 20
    """
    count = max(1, min(25, count))

    # Load from Redis if in-memory cache is empty
    if not _mod_actions:
        redis_actions = await _mod_redis_get_actions(count)
        if redis_actions:
            _mod_actions.extend(redis_actions)

    if not _mod_actions:
        await ctx.send("📋 No moderation actions recorded this session.")
        return

    embed = discord.Embed(
        title="📋 Moderation Log",
        color=discord.Color.dark_blue(),
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    recent = _mod_actions[-count:]
    recent.reverse()

    for action in recent:
        action_emojis = {
            "warn": "⚠️",
            "timeout": "🔇",
            "untimeout": "🔊",
            "kick": "🚪",
            "ban": "🔨",
            "unban": "✅",
            "purge": "🧹",
            "clearwarnings": "🧹",
        }
        emoji = action_emojis.get(action["action"], "📝")

        embed.add_field(
            name="{} {} → {}".format(emoji, action["action"].upper(), action["target_name"]),
            value="By: {}\nReason: {}\nTime: {}".format(
                action["moderator_name"],
                action["reason"][:80],
                action["timestamp"][:16],
            ),
            inline=False,
        )

    embed.set_footer(text=f"Showing last {len(recent)} actions • Helix Moderation")
    await ctx.send(embed=embed)


# ============================================================================
# MESSAGE LOGGING (on_message_edit, on_message_delete)
# ============================================================================

_message_log_cog = None


class MessageLogCog(commands.Cog):
    """Logs message edits and deletes to mod-log channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log deleted messages."""
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)

        content = message.content[:1000] if message.content else "*No text content*"
        embed.add_field(name="Content", value=content, inline=False)

        if message.attachments:
            att_text = "\n".join(a.filename for a in message.attachments[:5])
            embed.add_field(name="Attachments", value=att_text, inline=False)

        embed.set_footer(text=f"Message ID: {message.id}")

        await _send_mod_log(self.bot, message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edits (only if content changed)."""
        if before.author.bot or not before.guild:
            return

        if before.content == after.content:
            return  # Embed-only update, skip

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author})", inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(
            name="Jump to Message",
            value=f"[Click here]({after.jump_url})",
            inline=True,
        )

        embed.add_field(name="Before", value=before.content[:500] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:500] or "*Empty*", inline=False)

        embed.set_footer(text=f"Message ID: {before.id}")

        await _send_mod_log(self.bot, before.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log when a member leaves the server."""
        embed = discord.Embed(
            title="👋 Member Left",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
        embed.add_field(
            name="Joined",
            value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown",
            inline=True,
        )
        embed.add_field(name="Roles", value=str(len(member.roles) - 1), inline=True)

        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.set_footer(text=f"User ID: {member.id}")

        await _send_mod_log(member.bot if hasattr(member, "bot") else None, member.guild, embed)


# ============================================================================
# SETUP
# ============================================================================


async def setup(bot: commands.Bot) -> None:
    """Register all moderation commands."""
    bot.add_command(warn_user)
    bot.add_command(check_warnings)
    bot.add_command(clear_warnings)
    bot.add_command(timeout_user)
    bot.add_command(untimeout_user)
    bot.add_command(kick_user)
    bot.add_command(ban_user)
    bot.add_command(unban_user)
    bot.add_command(purge_messages)
    bot.add_command(set_slowmode)
    bot.add_command(server_info)
    bot.add_command(user_info)
    bot.add_command(mod_log)

    # Register message log cog for edit/delete tracking
    await bot.add_cog(MessageLogCog(bot))

    logger.info(
        "✅ Moderation commands loaded (warn, timeout, kick, ban, purge, "
        "slowmode, serverinfo, userinfo, modlog + message logging)"
    )
