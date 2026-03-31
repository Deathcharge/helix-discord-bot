"""
🌀 Helix Collective — Discord Account Linking & Privacy Commands
apps/backend/discord/discord_account_commands.py

Provides Discord bot commands for:
- !link <token>       — Link Discord account to Helix platform account
- !unlink             — Unlink Discord from Helix
- !subscription       — Show linked account's subscription tier
- !privacy            — View/manage privacy & consent settings
- !opt-out            — Opt out of all data collection
- !opt-in             — Opt back in to data collection
- !delete-my-data     — Request deletion of all stored data

Version: 17.2.0
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE HELPER — get an async session for account lookups
# ============================================================================


async def _get_db_session():
    """Get an async database session for Discord bot operations."""
    try:
        from apps.backend.database import get_async_session

        async with get_async_session() as session:
            yield session
    except Exception as e:
        logger.error("Failed to get database session: %s", e)
        yield None


async def _get_session():
    """Convenience wrapper that returns a usable session (not a generator)."""
    try:
        from apps.backend.database import get_async_session

        return get_async_session()
    except Exception as e:
        logger.error("Failed to create database session: %s", e)
        return None


# ============================================================================
# ACCOUNT LINKING COG
# ============================================================================


class AccountLinkingCog(commands.Cog, name="Account Linking"):
    """Commands for linking Discord accounts to Helix platform and managing privacy."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========================================================================
    # !link <token>
    # ========================================================================

    @commands.command(name="link")
    async def link_account(self, ctx: commands.Context, token: str | None = None):
        """
        Link your Discord account to your Helix platform account.

        Usage:
          1. Go to your Helix dashboard → Settings → Discord
          2. Click "Link Discord" to get a one-time token
          3. Come back here and type: !link <token>

        Example: !link abc123def456...
        """
        if not token:
            embed = discord.Embed(
                title="🔗 Link Your Discord Account",
                description=(
                    "To link your Discord to Helix, follow these steps:\n\n"
                    "1️⃣ Log in to your [Helix Dashboard](https://helix.app/dashboard)\n"
                    "2️⃣ Go to **Settings → Discord Integration**\n"
                    "3️⃣ Click **Link Discord** to get a one-time token\n"
                    "4️⃣ Come back here and type:\n"
                    "```\n!link <your-token>\n```\n\n"
                    "Your token expires after 15 minutes."
                ),
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Tat Tvam Asi 🌀")
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                from apps.backend.database import get_async_session
                from apps.backend.discord.discord_account_link import consume_link_token, link_discord_account

                # Validate token
                user_id = await consume_link_token(token)
                if not user_id:
                    await ctx.send("❌ Invalid or expired token. Please generate a new one from your Helix dashboard.")
                    return

                # Link the account
                discord_id = str(ctx.author.id)
                async with get_async_session() as db:
                    success, message = await link_discord_account(db, user_id, discord_id)

                if success:
                    embed = discord.Embed(
                        title="✅ Account Linked!",
                        description=(
                            "Your Discord account is now connected to your Helix platform account.\n\n"
                            "**What this means:**\n"
                            "• Bot commands now respect your subscription tier\n"
                            "• You can manage privacy settings with `!privacy`\n"
                            "• Your subscription benefits apply to Discord features\n\n"
                            "Use `!subscription` to see your current tier."
                        ),
                        color=discord.Color.green(),
                    )
                    embed.set_footer(text="Tat Tvam Asi 🌀")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ " + message)

            except Exception as e:
                logger.error("Link command failed: %s", e)
                await ctx.send("❌ Failed to link account. Please try again later.")

    # ========================================================================
    # !unlink
    # ========================================================================

    @commands.command(name="unlink")
    async def unlink_account(self, ctx: commands.Context):
        """
        Unlink your Discord account from your Helix platform account.

        Usage: !unlink
        """
        async with ctx.typing():
            try:
                from apps.backend.database import get_async_session
                from apps.backend.discord.discord_account_link import get_user_by_discord_id, unlink_discord_account

                discord_id = str(ctx.author.id)
                async with get_async_session() as db:
                    user = await get_user_by_discord_id(db, discord_id)

                    if not user:
                        await ctx.send("ℹ️ Your Discord account is not linked to any Helix account.")
                        return

                    success, message = await unlink_discord_account(db, user.id)

                if success:
                    embed = discord.Embed(
                        title="🔓 Account Unlinked",
                        description=(
                            "Your Discord account has been disconnected from Helix.\n\n"
                            "• Bot commands will use Discord-role-based permissions only\n"
                            "• Subscription benefits no longer apply to Discord\n"
                            "• You can re-link anytime with `!link`"
                        ),
                        color=discord.Color.orange(),
                    )
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ " + message)

            except Exception as e:
                logger.error("Unlink command failed: %s", e)
                await ctx.send("❌ Failed to unlink account. Please try again later.")

    # ========================================================================
    # !subscription
    # ========================================================================

    @commands.command(name="subscription", aliases=["sub", "tier", "plan"])
    async def show_subscription(self, ctx: commands.Context):
        """
        Show your linked Helix subscription tier and its Discord benefits.

        Usage: !subscription
        """
        async with ctx.typing():
            try:
                from apps.backend.database import get_async_session
                from apps.backend.discord.discord_account_link import get_user_by_discord_id

                discord_id = str(ctx.author.id)
                async with get_async_session() as db:
                    user = await get_user_by_discord_id(db, discord_id)

                if not user:
                    embed = discord.Embed(
                        title="📋 Subscription Status",
                        description=(
                            "Your Discord account is **not linked** to a Helix account.\n\n"
                            "Link your account with `!link` to access subscription features."
                        ),
                        color=discord.Color.greyple(),
                    )
                    await ctx.send(embed=embed)
                    return

                tier = user.subscription_tier or "free"
                tier_display = tier.capitalize()

                # Tier info with Discord-specific benefits
                tier_info = {
                    "free": {
                        "color": discord.Color.light_grey(),
                        "emoji": "🆓",
                        "benefits": ["Basic bot commands", "Public channels"],
                    },
                    "hobby": {
                        "color": discord.Color.blue(),
                        "emoji": "🎨",
                        "benefits": [
                            "All Free features",
                            "Cycle commands (!harmony, !neti-neti)",
                            "Voice channel access (!join, !leave)",
                        ],
                    },
                    "starter": {
                        "color": discord.Color.green(),
                        "emoji": "🚀",
                        "benefits": [
                            "All Hobby features",
                            "Collaboration commands (!collaborate)",
                            "Agent interaction commands",
                        ],
                    },
                    "pro": {
                        "color": discord.Color.gold(),
                        "emoji": "⭐",
                        "benefits": [
                            "All Starter features",
                            "Coordination commands (!coordination)",
                            "Transcription (!transcribe)",
                            "Priority bot responses",
                        ],
                    },
                    "enterprise": {
                        "color": discord.Color.purple(),
                        "emoji": "👑",
                        "benefits": [
                            "All Pro features",
                            "Custom agent deployment",
                            "Dedicated support channel",
                        ],
                    },
                }

                info = tier_info.get(tier, tier_info["free"])
                embed = discord.Embed(
                    title="{} {} Plan".format(info["emoji"], tier_display),
                    description="Your Helix subscription tier and Discord benefits:",
                    color=info["color"],
                )
                embed.add_field(
                    name="Discord Benefits",
                    value="\n".join("• " + b for b in info["benefits"]),
                    inline=False,
                )
                embed.add_field(
                    name="Account",
                    value="Linked to: {}".format(user.email[:3] + "***"),
                    inline=True,
                )
                embed.set_footer(text="Upgrade at helix.app/billing • Tat Tvam Asi 🌀")

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error("Subscription command failed: %s", e)
                await ctx.send("❌ Failed to fetch subscription info.")

    # ========================================================================
    # !privacy
    # ========================================================================

    @commands.command(name="privacy")
    async def privacy_settings(self, ctx: commands.Context):
        """
        View your current privacy and data collection settings.

        Usage: !privacy
        """
        async with ctx.typing():
            try:
                from apps.backend.learning.consent_system import ConsentType, get_consent_system

                consent = get_consent_system()
                user_key = "discord:" + str(ctx.author.id)
                await consent.get_user_consent_summary(user_key)
                prefs = await consent.get_privacy_preferences(user_key)

                embed = discord.Embed(
                    title="🔒 Your Privacy Settings",
                    description="Here are your current data collection preferences for Discord:",
                    color=discord.Color.dark_teal(),
                )

                # Consent status
                consent_lines = []
                for ct in ConsentType:
                    has = await consent.check_consent(user_key, ct)
                    status_emoji = "✅" if has else "❌"
                    consent_lines.append(
                        "{} **{}**: {}".format(
                            status_emoji,
                            ct.value.replace("_", " ").title(),
                            "Enabled" if has else "Disabled",
                        )
                    )

                embed.add_field(
                    name="Consent Status",
                    value="\n".join(consent_lines),
                    inline=False,
                )

                embed.add_field(
                    name="Privacy Preferences",
                    value=(
                        "• Learning from interactions: {}\n"
                        "• Analytics: {}\n"
                        "• Cross-platform sharing: {}\n"
                        "• Data retention: {} days"
                    ).format(
                        "✅" if prefs.allow_learning else "❌",
                        "✅" if prefs.allow_analytics else "❌",
                        "✅" if prefs.allow_cross_platform else "❌",
                        prefs.data_retention_days,
                    ),
                    inline=False,
                )

                embed.add_field(
                    name="Commands",
                    value=(
                        "`!opt-out` — Disable all data collection\n"
                        "`!opt-in` — Re-enable data collection\n"
                        "`!delete-my-data` — Request full data deletion"
                    ),
                    inline=False,
                )

                embed.set_footer(text="Your privacy matters • Tat Tvam Asi 🌀")
                await ctx.send(embed=embed)

            except Exception as e:
                logger.error("Privacy command failed: %s", e)
                await ctx.send("❌ Failed to load privacy settings.")

    # ========================================================================
    # !opt-out
    # ========================================================================

    @commands.command(name="opt-out", aliases=["optout"])
    async def opt_out(self, ctx: commands.Context):
        """
        Opt out of all data collection from Discord interactions.

        This disables:
        - Learning from your messages
        - Analytics tracking
        - Cross-platform data sharing

        The bot will still function, but will not store or learn from your interactions.

        Usage: !opt-out
        """
        async with ctx.typing():
            try:
                from apps.backend.learning.consent_system import ConsentType, PrivacyPreferences, get_consent_system

                consent = get_consent_system()
                user_key = "discord:" + str(ctx.author.id)

                # Deny all consent types
                for ct in ConsentType:
                    await consent.deny_consent(user_key, ct, metadata={"source": "discord_opt_out"})

                # Set privacy preferences to all-off
                prefs = PrivacyPreferences(
                    user_id=user_key,
                    allow_learning=False,
                    allow_analytics=False,
                    allow_cross_platform=False,
                    allow_public_showcase=False,
                    retain_identifiers=False,
                    data_retention_days=0,
                )
                await consent.set_privacy_preferences(user_key, prefs)

                embed = discord.Embed(
                    title="🛡️ Opted Out of Data Collection",
                    description=(
                        "All data collection from your Discord interactions has been **disabled**.\n\n"
                        "**What this means:**\n"
                        "• The bot will not learn from your messages\n"
                        "• No analytics data will be collected\n"
                        "• Your interactions won't be shared across platforms\n"
                        "• The bot still works — it just won't remember anything\n\n"
                        "You can re-enable data collection anytime with `!opt-in`."
                    ),
                    color=discord.Color.dark_red(),
                )
                embed.set_footer(text="Your privacy is respected • Tat Tvam Asi 🌀")
                await ctx.send(embed=embed)

            except Exception as e:
                logger.error("Opt-out command failed: %s", e)
                await ctx.send("❌ Failed to update privacy settings.")

    # ========================================================================
    # !opt-in
    # ========================================================================

    @commands.command(name="opt-in", aliases=["optin"])
    async def opt_in(self, ctx: commands.Context):
        """
        Opt back in to data collection from Discord interactions.

        This enables:
        - Learning from your messages (agent memory improvement)
        - Basic analytics

        Cross-platform sharing and public showcase remain OFF by default.

        Usage: !opt-in
        """
        async with ctx.typing():
            try:
                from apps.backend.learning.consent_system import ConsentType, PrivacyPreferences, get_consent_system

                consent = get_consent_system()
                user_key = "discord:" + str(ctx.author.id)

                # Grant learning and analytics consent
                await consent.grant_consent(
                    user_key,
                    ConsentType.LEARNING,
                    metadata={"source": "discord_opt_in"},
                )
                await consent.grant_consent(
                    user_key,
                    ConsentType.ANALYTICS,
                    metadata={"source": "discord_opt_in"},
                )

                # Cross-platform and public showcase stay off — user must enable explicitly
                await consent.deny_consent(user_key, ConsentType.CROSS_PLATFORM)
                await consent.deny_consent(user_key, ConsentType.PUBLIC_SHOWCASE)

                # Update preferences
                prefs = PrivacyPreferences(
                    user_id=user_key,
                    allow_learning=True,
                    allow_analytics=True,
                    allow_cross_platform=False,
                    allow_public_showcase=False,
                    retain_identifiers=False,
                    data_retention_days=90,
                )
                await consent.set_privacy_preferences(user_key, prefs)

                embed = discord.Embed(
                    title="✅ Data Collection Re-enabled",
                    description=(
                        "Learning and analytics are now **enabled** for your Discord interactions.\n\n"
                        "**Active:**\n"
                        "• ✅ Learning from interactions\n"
                        "• ✅ Basic analytics\n\n"
                        "**Still disabled (privacy-first defaults):**\n"
                        "• ❌ Cross-platform data sharing\n"
                        "• ❌ Public showcase\n\n"
                        "Use `!privacy` to see all settings."
                    ),
                    color=discord.Color.green(),
                )
                embed.set_footer(text="Thank you for helping improve Helix • Tat Tvam Asi 🌀")
                await ctx.send(embed=embed)

            except Exception as e:
                logger.error("Opt-in command failed: %s", e)
                await ctx.send("❌ Failed to update privacy settings.")

    # ========================================================================
    # !delete-my-data
    # ========================================================================

    @commands.command(name="delete-my-data", aliases=["deletedata", "gdpr-delete"])
    async def delete_my_data(self, ctx: commands.Context):
        """
        Request deletion of all your data from the Helix system.

        This will:
        - Remove all consent records
        - Clear privacy preferences
        - Request deletion from the GDPR service (if linked)
        - Unlink your Discord account

        This action cannot be undone. Type !delete-my-data confirm to proceed.

        Usage: !delete-my-data confirm
        """
        # Require explicit confirmation
        # The command itself is "delete-my-data" and we check for "confirm" in the message
        if "confirm" not in ctx.message.content.lower():
            embed = discord.Embed(
                title="⚠️ Data Deletion Request",
                description=(
                    "This will **permanently delete** all your data from the Helix system.\n\n"
                    "**What will be deleted:**\n"
                    "• All consent records\n"
                    "• Privacy preferences\n"
                    "• Agent memories associated with your Discord ID\n"
                    "• Discord account link\n\n"
                    "**This cannot be undone.**\n\n"
                    "To confirm, type:\n```\n!delete-my-data confirm\n```"
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                from apps.backend.learning.consent_system import ConsentType, get_consent_system

                consent = get_consent_system()
                user_key = "discord:" + str(ctx.author.id)

                # Revoke/deny all consent
                for ct in ConsentType:
                    try:
                        has = await consent.check_consent(user_key, ct)
                        if has:
                            await consent.revoke_consent(user_key, ct, reason="GDPR deletion request")
                        else:
                            await consent.deny_consent(user_key, ct)
                    except (ValueError, KeyError) as exc:
                        logger.warning("Failed to revoke consent for %s type %s: %s", user_key, ct, exc)

                # Clear privacy preferences
                if user_key in consent.privacy_preferences:
                    del consent.privacy_preferences[user_key]

                # Remove consent records for this user
                keys_to_del = [k for k in consent.consent_records if k.startswith(user_key + ":")]
                for k in keys_to_del:
                    del consent.consent_records[k]

                # If account is linked, trigger backend GDPR deletion + unlink
                unlinked = False
                try:
                    from apps.backend.database import get_async_session
                    from apps.backend.discord.discord_account_link import get_user_by_discord_id, unlink_discord_account

                    discord_id = str(ctx.author.id)
                    async with get_async_session() as db:
                        user = await get_user_by_discord_id(db, discord_id)
                        if user:
                            await unlink_discord_account(db, user.id)
                            unlinked = True
                except Exception as e:
                    logger.warning("Could not unlink during deletion: %s", e)

                embed = discord.Embed(
                    title="🗑️ Data Deleted",
                    description=(
                        "All your data has been removed from the Helix Discord system.\n\n"
                        "• ✅ Consent records cleared\n"
                        "• ✅ Privacy preferences removed\n"
                        + ("• ✅ Discord account unlinked\n" if unlinked else "")
                        + "\nYou can re-join and start fresh anytime."
                    ),
                    color=discord.Color.dark_grey(),
                )
                embed.set_footer(text="Tat Tvam Asi 🌀")
                await ctx.send(embed=embed)

            except Exception as e:
                logger.error("Delete-my-data command failed: %s", e)
                await ctx.send("❌ Failed to delete data. Please contact support.")


# ============================================================================
# COG SETUP
# ============================================================================


async def setup(bot: commands.Bot):
    """Register the AccountLinkingCog with the bot."""
    await bot.add_cog(AccountLinkingCog(bot))
