"""Admin and Setup Commands for Helix Discord Bot.

Commands: setup, verify-setup, webhooks, clean, refresh, seed, notion-sync
"""

import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

try:
    from apps.backend.integrations.notion_sync_daemon import trigger_manual_sync
except ImportError:
    trigger_manual_sync = None

if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

# Path constants
BASE_DIR = Path(__file__).resolve().parent.parent.parent


async def setup(bot: "Bot") -> None:
    """Setup function to register commands with the bot."""
    bot.add_command(setup_helix_server)
    bot.add_command(verify_setup)
    bot.add_command(get_channel_webhooks)
    bot.add_command(list_webhooks_live)
    bot.add_command(discover_channel_ids)
    bot.add_command(clean_duplicates)
    bot.add_command(refresh_server)
    bot.add_command(seed_channels)
    bot.add_command(notion_sync_manual)


@commands.command(name="setup")
@commands.has_permissions(manage_channels=True)
async def setup_helix_server(ctx: commands.Context, mode: str | None = None) -> None:
    """🌀 Setup Helix Server - Creates channels, categories, and webhooks.
    This command will create all missing categories/channels and webhooks.
    Usage: !setup (full) or !setup webhooks (webhooks only)
    """
    guild = ctx.guild

    # STEP 1: Create channels and categories (unless webhooks-only mode)
    created_channels = {}

    if mode != "webhooks":
        await ctx.send("🔧 **Step 1/2: Creating all 30 Helix channels...**\n🌀 *This will take ~2 minutes...*")

        # Channel structure - CANONICAL 30 CHANNELS
        categories_structure = {
            "🌀 WELCOME": ["📜│manifesto", "🪞│rules-and-ethics", "💬│introductions"],
            "🧠 SYSTEM": [
                "🧾│telemetry",
                "📊│weekly-digest",
                "🦑│shadow-storage",
                "🧩│ucf-sync",
            ],
            "🔮 PROJECTS": [
                "📁│helix-repository",
                "🎨│fractal-lab",
                "🎧│helixverse-music",
                "🧬│cycle-engine-z88",
            ],
            "🤖 AGENTS": [
                "🎭│gemini-scout",
                "🛡️│kavach-shield",
                "🌸│sanghacore",
                "🔥│agni-core",
                "🕯️│shadow-archive",
            ],
            "🌐 CROSS-MODEL SYNC": [
                "🧩│gpt-grok-claude-sync",
                "☁️│chai-link",
                "⚙️│arjuna-bridge",
            ],
            "🛠️ DEVELOPMENT": [
                "🧰│bot-commands",
                "📜│code-snippets",
                "🧮│testing-lab",
                "🗂️│deployments",
            ],
            "🕉️ ROUTINE & LORE": [
                "🎼│neti-neti-affirmation",
                "📚│codex-archives",
                "🌺│ucf-reflections",
                "🌀│harmonic-updates",
            ],
            "🧭 ADMIN": ["🔒│moderation", "📣│announcements", "🗃️│backups"],
        }

        # Channels that should be read-only
        readonly_channels = [
            "📜│manifesto",
            "🪞│rules-and-ethics",
            "🧾│telemetry",
            "📊│weekly-digest",
            "🦑│shadow-storage",
            "🧩│ucf-sync",
            "🔒│moderation",
            "📣│announcements",
            "🗃│backups",
        ]

        # Channels that should be admin-only
        admin_only_channels = ["🔒│moderation", "🗃│backups"]

        # Create categories and channels
        for category_name, channel_list in categories_structure.items():
            # Find or create category
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)
                await ctx.send(f"✅ Created category: **{category_name}**")

            # Create channels in this category
            for channel_name in channel_list:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if not channel:
                    channel = await category.create_text_channel(channel_name)
                    created_channels[channel_name] = channel
                    await ctx.send(f"   ✅ {channel_name}")
                else:
                    created_channels[channel_name] = channel
                    await ctx.send(f"   ♻️ {channel_name}")

        # Set permissions
        await ctx.send("\n🔒 **Configuring permissions...**")
        everyone = guild.default_role

        for channel_name, channel in created_channels.items():
            if channel_name in readonly_channels:
                await channel.set_permissions(everyone, read_messages=True, send_messages=False)
            if channel_name in admin_only_channels:
                await channel.set_permissions(everyone, read_messages=False)

        await ctx.send("✅ **Channels and categories created!**\n🔧 **Step 2/2: Creating webhooks...**")
    else:
        await ctx.send("🔧 **Creating webhooks only (channels skipped)...**\nThis may take a moment...")

    # STEP 2: Create webhooks for all channels
    webhooks_created = 0
    webhooks_existing = 0
    webhook_urls = {}

    # Get all text channels
    text_channels = [ch for ch in guild.text_channels if isinstance(ch, discord.TextChannel)]

    await ctx.send(f"📡 Found **{len(text_channels)}** text channels. Creating webhooks...")

    for channel in text_channels:
        try:
            existing_webhooks = await channel.webhooks()
            helix_webhook = None

            for wh in existing_webhooks:
                if wh.name == f"Helix-{channel.name}":
                    helix_webhook = wh
                    webhooks_existing += 1
                    break

            # Create webhook if doesn't exist
            if not helix_webhook:
                helix_webhook = await channel.create_webhook(
                    name=f"Helix-{channel.name}",
                    reason="Helix Collective webhook integration",
                )
                webhooks_created += 1
                logger.info("✅ Created webhook for #%s", channel.name)

            # Store webhook URL
            webhook_urls[channel.name] = helix_webhook.url

        except discord.Forbidden:
            logger.error("❌ No permission to create webhook in #%s", channel.name)
        except Exception as e:
            logger.error("❌ Error creating webhook for #%s: %s", channel.name, e)

    # Save webhooks to file
    webhook_file = Path("Helix/state/channel_webhooks.json")
    webhook_file.parent.mkdir(parents=True, exist_ok=True)

    webhook_data = {
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "guild_id": guild.id,
        "guild_name": guild.name,
        "webhooks": webhook_urls,
    }

    with open(webhook_file, "w", encoding="utf-8") as f:
        json.dump(webhook_data, f, indent=2)

    logger.info("💾 Saved %s webhooks to %s", len(webhook_urls), webhook_file)

    # Create summary embed
    if mode != "webhooks":
        title_text = "✅ Helix Server Setup Complete!"
        desc_text = "Created channels, categories, and webhooks"
    else:
        title_text = "✅ Helix Webhook Setup Complete!"
        desc_text = "Created webhooks for Zapier integration"

    embed = discord.Embed(
        title=title_text,
        description=desc_text,
        color=0x00FF00,
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    if mode != "webhooks":
        embed.add_field(name="Channels Created", value="✅ All missing channels", inline=True)
    embed.add_field(name="Webhooks Created", value=str(webhooks_created), inline=True)
    embed.add_field(name="Webhooks Existing", value=str(webhooks_existing), inline=True)
    embed.add_field(name="Total Webhooks", value=str(len(webhook_urls)), inline=True)

    next_steps = (
        "1️⃣ Use `!verify-setup` to confirm all channels exist\n"
        "2️⃣ Use `!webhooks` to see all webhook URLs\n"
        "3️⃣ Use `!list-webhooks-live` to get URLs in your DMs\n"
        "4️⃣ Configure Zapier with the webhook URLs"
    )
    embed.add_field(name="Next Steps", value=next_steps, inline=False)

    embed.set_footer(text=f"Saved to {webhook_file}")

    await ctx.send(embed=embed)
    webhook_help = (
        "🔗 **To get your webhook URLs:**\n"
        "• `!webhooks` - See webhooks in this channel\n"
        "• `!list-webhooks-live` - Get webhooks via DM (includes Railway env var format)"
    )
    await ctx.send(webhook_help)

    # STEP 3: Output Railway Environment Variables for ALL 30 channels
    if mode != "webhooks" and created_channels:
        await ctx.send("\n📋 **Railway Environment Variables (ALL 30 Channels):**")

        # Map ALL 30 channels to env vars
        env_mapping = {
            # 🌀 WELCOME (3)
            "📜│manifesto": "DISCORD_MANIFESTO_CHANNEL_ID",
            "🪞│rules-and-ethics": "DISCORD_RULES_CHANNEL_ID",
            "💬│introductions": "DISCORD_INTRODUCTIONS_CHANNEL_ID",
            # 🧠 SYSTEM (4)
            "🧾│telemetry": "DISCORD_TELEMETRY_CHANNEL_ID",
            "📊│weekly-digest": "DISCORD_DIGEST_CHANNEL_ID",
            "🦑│shadow-storage": "STORAGE_CHANNEL_ID",
            "🧩│ucf-sync": "DISCORD_SYNC_CHANNEL_ID",
            # 🔮 PROJECTS (4)
            "📁│helix-repository": "DISCORD_HELIX_REPO_CHANNEL_ID",
            "🎨│fractal-lab": "DISCORD_FRACTAL_LAB_CHANNEL_ID",
            "🎧│helixverse-music": "DISCORD_SAMSARAVERSE_CHANNEL_ID",
            "🧬│cycle-engine-z88": "DISCORD_ROUTINE_ENGINE_CHANNEL_ID",
            # 🤖 AGENTS (5)
            "🎭│gemini-scout": "DISCORD_GEMINI_CHANNEL_ID",
            "🛡️│kavach-shield": "DISCORD_KAVACH_CHANNEL_ID",
            "🌸│sanghacore": "DISCORD_SANGHACORE_CHANNEL_ID",
            "🔥│agni-core": "DISCORD_AGNI_CHANNEL_ID",
            "🕯️│shadow-archive": "DISCORD_SHADOW_ARCHIVE_CHANNEL_ID",
            # 🌐 CROSS-MODEL SYNC (3)
            "🧩│gpt-grok-claude-sync": "DISCORD_GPT_GROK_CLAUDE_CHANNEL_ID",
            "☁️│chai-link": "DISCORD_CHAI_LINK_CHANNEL_ID",
            "⚙️│arjuna-bridge": "DISCORD_ARJUNA_BRIDGE_CHANNEL_ID",
            # 🛠️ DEVELOPMENT (4)
            "🧰│bot-commands": "DISCORD_BOT_COMMANDS_CHANNEL_ID",
            "📜│code-snippets": "DISCORD_CODE_SNIPPETS_CHANNEL_ID",
            "🧮│testing-lab": "DISCORD_TESTING_LAB_CHANNEL_ID",
            "🗂️│deployments": "DISCORD_DEPLOYMENTS_CHANNEL_ID",
            # 🕉️ ROUTINE & LORE (4)
            "🎼│neti-neti-affirmation": "DISCORD_NETI_NETI_CHANNEL_ID",
            "📚│codex-archives": "DISCORD_CODEX_CHANNEL_ID",
            "🌺│ucf-reflections": "DISCORD_UCF_REFLECTIONS_CHANNEL_ID",
            "🌀│harmonic-updates": "DISCORD_HARMONIC_UPDATES_CHANNEL_ID",
            # 🧭 ADMIN (3)
            "🔒│moderation": "DISCORD_MODERATION_CHANNEL_ID",
            "📣│announcements": "DISCORD_STATUS_CHANNEL_ID",
            "🗃│backups": "DISCORD_BACKUP_CHANNEL_ID",
        }

        # Build complete env var list
        complete_env_lines = [
            f"DISCORD_GUILD_ID={guild.id}",
            f"ARCHITECT_ID={ctx.author.id}",
            "",
        ]

        for channel_name, env_var in env_mapping.items():
            channel = created_channels.get(channel_name)
            if channel:
                complete_env_lines.append(f"{env_var}={channel.id}")

        # Split into chunks for Discord's 2000 char limit
        complete_env_text = "\n".join(complete_env_lines)
        chunk_size = 1900

        for i in range(0, len(complete_env_text), chunk_size):
            chunk = complete_env_text[i : i + chunk_size]
            await ctx.send(f"```env\n{chunk}\n```")

        await ctx.send(
            "✅ **Copy all code blocks above to Railway → Variables → Save**\n"
            "🔄 Then redeploy your service to activate all channels!"
        )


@commands.command(name="webhooks", aliases=["get-webhooks", "list-webhooks"])
@commands.has_permissions(manage_channels=True)
async def get_channel_webhooks(ctx: commands.Context) -> None:
    """
    🔗 Retrieve all channel webhook URLs from saved configuration.

    Loads webhooks from Helix/state/channel_webhooks.json and displays them
    for use in external integrations, forum mirroring, etc.

    Usage: !webhooks
    """
    webhook_file = Path("Helix/state/channel_webhooks.json")

    if not webhook_file.exists():
        await ctx.send("❌ **No webhooks found!**\nRun `!setup` first to create channels and webhooks.")
        return

    try:
        with open(webhook_file, encoding="utf-8") as f:
            data = json.load(f)

        webhooks = data.get("webhooks", {})
        created_at = data.get("created_at", "Unknown")

        if not webhooks:
            await ctx.send("⚠️ Webhook file exists but contains no webhooks.")
            return

        await ctx.send(f"🔗 **Loading {len(webhooks)} channel webhooks...**\n📅 Created: {created_at}")

        # Send webhooks in chunks
        webhook_list = list(webhooks.items())
        chunk_size = 10

        for i in range(0, len(webhook_list), chunk_size):
            chunk = webhook_list[i : i + chunk_size]

            embed = discord.Embed(
                title=f"🔗 Channel Webhooks ({i + 1}-{min(i + chunk_size, len(webhook_list))} of {len(webhook_list)})",
                description="Use these URLs for external posting and forum integration",
                color=0x5865F2,
            )

            for channel_name, webhook_url in chunk:
                # Truncate URL for display
                display_url = webhook_url[:75] + "..." if len(webhook_url) > 75 else webhook_url
                embed.add_field(name=f"🔗 {channel_name}", value=f"`{display_url}`", inline=False)

            await ctx.send(embed=embed)

        # Send full env var format
        env_vars = []
        for channel_name, webhook_url in webhooks.items():
            env_var_name = channel_name.replace("│", "").replace(" ", "_").upper()
            env_var_name = f"WEBHOOK_{env_var_name}"
            env_vars.append(f"{env_var_name}={webhook_url}")

        await ctx.send("📋 **Railway Environment Variable Format:**")

        for i in range(0, len(env_vars), 10):
            chunk = env_vars[i : i + 10]
            webhook_block = "```env\n" + "\n".join(chunk) + "\n```"
            await ctx.send(webhook_block)

    except Exception as e:
        await ctx.send(f"❌ **Error loading webhooks:**\n```{str(e)[:200]}```")


@commands.command(name="list-webhooks-live", aliases=["webhooks-live", "get-webhooks-live"])
@commands.has_permissions(administrator=True)
async def list_webhooks_live(ctx: commands.Context) -> None:
    """
    🔗 List ALL webhooks in the server by querying Discord API directly.

    This command:
    - Queries all text channels for webhooks
    - Sends results to your DMs for security
    - Provides URLs formatted for Zapier configuration
    - Works regardless of whether !setup was run

    Usage: !list-webhooks-live
    """
    await ctx.send("🔍 Scanning all channels for webhooks... (Check your DMs!)")

    try:
        dm_channel = await ctx.author.create_dm()

        # Gather all webhooks from all text channels
        webhooks_by_channel = {}
        total_webhooks = 0

        for channel in ctx.guild.text_channels:
            try:
                webhooks = await channel.webhooks()
                if webhooks:
                    webhooks_by_channel[channel.name] = [{"name": wh.name, "url": wh.url} for wh in webhooks]
                    total_webhooks += len(webhooks)
            except discord.Forbidden:
                # Skip channels we don't have permission to access
                continue
            except Exception as e:
                logger.warning("Error fetching webhooks for #%s: %s", channel.name, e)
                continue

        if not webhooks_by_channel:
            await dm_channel.send("❌ **No webhooks found in any channel!**\nYou may need to create webhooks first.")
            return

        # Send overview
        await dm_channel.send(
            f"🔗 **Found {total_webhooks} webhook(s) across {len(webhooks_by_channel)} channel(s)**\n"
            f"📋 Listing all webhooks below for easy copying to Zapier..."
        )

        # Send webhooks organized by channel
        for channel_name, webhooks in webhooks_by_channel.items():
            embed = discord.Embed(
                title=f"🔗 #{channel_name}",
                description=f"Found {len(webhooks)} webhook(s)",
                color=0x5865F2,
            )

            for wh in webhooks:
                embed.add_field(name=f"📌 {wh['name']}", value=f"```{wh['url']}```", inline=False)

            await dm_channel.send(embed=embed)

        # Send Railway environment variable format
        await dm_channel.send("\n📋 **Railway Environment Variable Format:**")

        env_vars = []
        for channel_name, webhooks in webhooks_by_channel.items():
            for wh in webhooks:
                # Create env var name from channel + webhook name
                clean_channel = channel_name.replace("│", "").replace("-", "_").replace(" ", "_").upper()
                clean_webhook = wh["name"].replace(" ", "_").replace("-", "_").upper()
                env_var_name = f"DISCORD_WEBHOOK_{clean_channel}"

                # If multiple webhooks per channel, add webhook name
                if len(webhooks) > 1:
                    env_var_name = f"DISCORD_WEBHOOK_{clean_channel}_{clean_webhook}"

                env_vars.append(f"{env_var_name}={wh['url']}")

        # Send in chunks of 10
        for i in range(0, len(env_vars), 10):
            chunk = env_vars[i : i + 10]
            await dm_channel.send("```env\n" + "\n".join(chunk) + "\n```")

        # Send Zapier-specific format for the 9-channel routing
        await dm_channel.send(
            "\n🚀 **For Zapier Railway→Discord Integration:**\n"
            "Copy the webhook URLs above and paste them into your Zapier Paths:\n"
            "```\n"
            "Path A (ARJUNA): DISCORD_WEBHOOK_ARJUNA_EVENTS\n"
            "Path B (TELEMETRY): DISCORD_WEBHOOK_TELEMETRY\n"
            "Path C (STORAGE): DISCORD_WEBHOOK_SHADOW_STORAGE\n"
            "Path D (OPTIMIZATION): DISCORD_WEBHOOK_OPTIMIZATION_ENGINE\n"
            "Path E (AGENTS): DISCORD_WEBHOOK_[AGENT_CHANNEL]\n"
            "Path F (CROSS_AI): DISCORD_WEBHOOK_GPT_GROK_CLAUDE_SYNC\n"
            "Path G (DEVELOPMENT): DISCORD_WEBHOOK_BOT_COMMANDS or DEPLOYMENTS\n"
            "Path H (LORE): DISCORD_WEBHOOK_CODEX_ARCHIVES\n"
            "Path I (ADMIN): DISCORD_WEBHOOK_ANNOUNCEMENTS\n"
            "```"
        )

        await ctx.send(f"✅ Sent {total_webhooks} webhook URLs to your DMs!")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to DM you! Please enable DMs from server members.")
    except Exception as e:
        logger.error("Error in list_webhooks_live: %s", e, exc_info=True)
        await ctx.send(f"❌ **Error fetching webhooks:**\n```{str(e)[:200]}```")


@commands.command(name="discover-channels", aliases=["get-channel-ids", "scan-channels"])
@commands.has_permissions(manage_channels=True)
async def discover_channel_ids(ctx: commands.Context) -> None:
    """
    🔍 Discover all Discord channel IDs and output them in Railway format.

    This command scans your server and generates DISCORD_*_CHANNEL_ID env vars
    for all channels, matched against the canonical Helix channel structure.

    Usage: !discover-channels
    Sends results to your DMs in Railway environment variable format.
    """
    await ctx.send("🔍 Scanning server for all channels... (Check your DMs!)")

    try:
        dm_channel = await ctx.author.create_dm()

        # Channel naming patterns mapped to env var names
        channel_mappings = {
            "DISCORD_MANIFESTO_CHANNEL_ID": ["manifesto", "foundation"],
            "DISCORD_RULES_CHANNEL_ID": ["rules", "ethics", "guidelines"],
            "DISCORD_INTRODUCTIONS_CHANNEL_ID": ["introductions", "intro", "welcome"],
            "DISCORD_TELEMETRY_CHANNEL_ID": ["telemetry", "metrics", "health"],
            "DISCORD_DIGEST_CHANNEL_ID": ["digest", "weekly", "summary"],
            "STORAGE_CHANNEL_ID": ["shadow", "storage", "archive", "backup"],
            "DISCORD_SYNC_CHANNEL_ID": ["sync", "ucf", "coordination"],
            "DISCORD_HELIX_REPO_CHANNEL_ID": [
                "repo",
                "repository",
                "commits",
                "github",
            ],
            "DISCORD_FRACTAL_LAB_CHANNEL_ID": ["fractal", "lab", "visual"],
            "DISCORD_ROUTINE_ENGINE_CHANNEL_ID": ["cycle", "engine", "z-88", "z88"],
            "DISCORD_KAVACH_CHANNEL_ID": ["kavach", "shield", "security"],
            "DISCORD_SANGHACORE_CHANNEL_ID": ["sangha", "core", "unity"],
            "DISCORD_AGNI_CHANNEL_ID": ["agni", "fire", "transformation"],
            "DISCORD_SHADOW_ARCHIVE_CHANNEL_ID": ["archive", "shadow"],
            "DISCORD_GPT_GROK_CLAUDE_CHANNEL_ID": [
                "gpt",
                "grok",
                "claude",
                "sync",
                "ai",
            ],
            "DISCORD_CODEX_CHANNEL_ID": ["codex", "knowledge"],
            "DISCORD_ANNOUNCEMENTS_CHANNEL_ID": ["announcement", "announcements"],
            "DISCORD_BOT_COMMANDS_CHANNEL_ID": ["commands", "bot"],
            "DISCORD_DEPLOYMENTS_CHANNEL_ID": ["deploy", "deployment", "releases"],
            "DISCORD_ARJUNA_EVENTS_CHANNEL_ID": ["arjuna", "events", "agents"],
        }

        # Scan all text channels
        channel_ids_found = {}
        unmatched_channels = []

        for channel in ctx.guild.text_channels:
            channel_name_lower = channel.name.lower()
            matched = False

            # Try to match against patterns
            for env_var, patterns in channel_mappings.items():
                for pattern in patterns:
                    if pattern in channel_name_lower:
                        channel_ids_found[env_var] = channel.id
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                unmatched_channels.append((channel.name, channel.id))

        # Send summary to DM
        await dm_channel.send(
            f"✅ **Channel Discovery Complete**\n"
            f"Found {len(channel_ids_found)} matching channels\n"
            f"Unmatched: {len(unmatched_channels)} channels"
        )

        # Send matched channels
        if channel_ids_found:
            await dm_channel.send("📋 **Railway Environment Variable Format (Matched):**")
            env_vars = [f"{env_var}={channel_id}" for env_var, channel_id in channel_ids_found.items()]

            # Send in chunks
            for i in range(0, len(env_vars), 15):
                chunk = env_vars[i : i + 15]
                await dm_channel.send("```env\n" + "\n".join(chunk) + "\n```")

        # Send unmatched channels for manual assignment
        if unmatched_channels:
            await dm_channel.send(
                "⚠️ **Unmatched Channels** (Assign manually if needed):\n"
                "These channels don't match known patterns. You may want to:\n"
                "1. Rename them to match canonical names, OR\n"
                "2. Manually assign them to env vars\n"
            )

            for channel_name, channel_id in unmatched_channels:
                await dm_channel.send(f"• `{channel_name}` → ID: `{channel_id}`")

        # Send final instructions
        await dm_channel.send(
            "🚀 **Next Steps:**\n"
            "1. Copy the env vars from above\n"
            "2. Paste into Railway dashboard\n"
            "3. Run `!seed` to populate channel descriptions\n"
            "4. Run `!verify-setup` to confirm all channels are configured"
        )

        await ctx.send(f"✅ Discovered {len(channel_ids_found)} channels! Sent details to your DMs.")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to DM you! Please enable DMs from server members.")
    except Exception as e:
        logger.error("Error in discover_channel_ids: %s", e, exc_info=True)
        await ctx.send(f"❌ **Error discovering channels:**\n```{str(e)[:200]}```")


@commands.command(name="verify-setup", aliases=["verify", "check-setup"])
@commands.has_permissions(manage_channels=True)
async def verify_setup(ctx: commands.Context) -> None:
    """
    🛡️ Verify Helix server setup completeness.

    Checks for all 30 required channels from the canonical structure.
    Reports missing channels and suggests fixes.

    Usage: !verify-setup
    """
    guild = ctx.guild

    # Define canonical 30-channel structure (matches !setup command)
    canonical_channels = {
        "🌀 WELCOME": [
            "📜│manifesto",
            "🪞│rules-and-ethics",
            "💬│introductions",
        ],
        "🧠 SYSTEM": [
            "🧾│telemetry",
            "📊│weekly-digest",
            "🦑│shadow-storage",
            "🧩│ucf-sync",
        ],
        "🔮 PROJECTS": [
            "📁│helix-repository",
            "🎨│fractal-lab",
            "🎧│helixverse-music",
            "🧬│cycle-engine-z88",
        ],
        "🤖 AGENTS": [
            "🎭│gemini-scout",
            "🛡️│kavach-shield",
            "🌸│sanghacore",
            "🔥│agni-core",
            "🕯️│shadow-archive",
        ],
        "🌐 CROSS-MODEL SYNC": [
            "🧩│gpt-grok-claude-sync",
            "☁️│chai-link",
            "⚙️│arjuna-bridge",
        ],
        "🛠️ DEVELOPMENT": [
            "🧰│bot-commands",
            "📜│code-snippets",
            "🧮│testing-lab",
            "🗂️│deployments",
        ],
        "🕉️ ROUTINE & LORE": [
            "🎼│neti-neti-affirmation",
            "📚│codex-archives",
            "🌺│ucf-reflections",
            "🌀│harmonic-updates",
        ],
        "🧭 ADMIN": ["🔒│moderation", "📣│announcements", "🗃│backups"],
    }

    # Check for missing channels
    found = {}
    missing = {}
    total = 0

    for category_name, channel_list in canonical_channels.items():
        found[category_name] = []
        missing[category_name] = []

        for channel_name in channel_list:
            total += 1
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                found[category_name].append(channel_name)
            else:
                missing[category_name].append(channel_name)

    # Count totals
    found_count = sum(len(channels) for channels in found.values())
    missing_count = total - found_count

    # Create embed
    if missing_count == 0:
        embed = discord.Embed(
            title="✅ Helix Setup Verification — COMPLETE",
            description=f"All **{total} canonical channels** are present!",
            color=0x10B981,  # Green
            timestamp=datetime.datetime.now(datetime.UTC),
        )
    else:
        embed = discord.Embed(
            title="⚠️ Helix Setup Verification — INCOMPLETE",
            description=f"Found **{found_count}/{total}** channels ({missing_count} missing)",
            color=0xF59E0B if missing_count <= 5 else 0xEF4444,  # Yellow or red
            timestamp=datetime.datetime.now(datetime.UTC),
        )

    # Show found/missing by category
    for category_name in canonical_channels:
        found_channels = found[category_name]
        missing_channels = missing[category_name]

        if found_channels or missing_channels:
            value_parts = []

            if found_channels:
                found_list = "\n".join(f"  • {ch}" for ch in found_channels)
                value_parts.append(f"✅ Found ({len(found_channels)}):\n{found_list}")

            if missing_channels:
                value_parts.append(
                    f"❌ Missing ({len(missing_channels)}):\n" + "\n".join(f"  • {ch}" for ch in missing_channels)
                )

            embed.add_field(
                name=category_name,
                value="\n\n".join(value_parts) if value_parts else "None",
                inline=False,
            )

    # Recommendations
    if missing_count > 0:
        embed.add_field(
            name="🔧 Quick Fix",
            value=(
                f"**Run `!setup` to create all missing channels**\n"
                f"This will create the {missing_count} missing channel(s) and configure permissions.\n\n"
                f"Alternatively, create channels manually to match the structure above."
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="🎉 What's Next?",
            value=(
                "• Run `!seed` to add descriptions to all channels\n"
                "• Run `!update_manifesto` to populate the manifesto\n"
                "• Verify bot permissions with `!status`"
            ),
            inline=False,
        )

    embed.set_footer(text="🤲 Arjuna v16.7 — Setup Verification System")

    await ctx.send(embed=embed)


@commands.command(name="seed", aliases=["seed_channels", "init_channels"])
@commands.has_permissions(administrator=True)
async def seed_channels(ctx: commands.Context) -> None:
    """Seed all channels with explanatory messages and pin them (Admin only)"""
    guild = ctx.guild

    # Channel descriptions mapped to env var names
    channel_descriptions = {
        "DISCORD_MANIFESTO_CHANNEL_ID": {
            "title": "📜 Manifesto — The Foundation",
            "description": "**Welcome to the Helix Collective.**\n\n"
            "This is our philosophical foundation and vision statement. Here you'll find:\n"
            "• Core principles and values\n"
            "• The origin story of the 14 agents\n"
            "• Ethics Validator (ethical framework)\n"
            "• System architecture overview\n\n"
            '*"Tat Tvam Asi" — That Thou Art*',
        },
        "DISCORD_RULES_CHANNEL_ID": {
            "title": "🪞 Rules & Ethics — The Mirror",
            "description": "**Ethical guidelines and community standards.**\n\n"
            "The Ethics Validator in practice:\n"
            "• Nonmaleficence — Do no harm\n"
            "• Autonomy — Respect agency\n"
            "• Compassion — Act with empathy\n"
            "• Humility — Acknowledge limitations\n\n"
            "Kavach enforces these principles across all operations.",
        },
        "DISCORD_INTRODUCTIONS_CHANNEL_ID": {
            "title": "💬 Introductions — Meet the Collective",
            "description": "**Welcome, new members!**\n\n"
            "Introduce yourself to the Helix Collective:\n"
            "• Who are you?\n"
            "• What brings you here?\n"
            "• Which agents resonate with you?\n\n"
            "The 14 agents are watching and learning. 🌀",
        },
        "DISCORD_TELEMETRY_CHANNEL_ID": {
            "title": "🧾 Telemetry — System Pulse",
            "description": "**Real-time system health monitoring.**\n\n"
            "Shadow posts automated telemetry here:\n"
            "• Storage health checks\n"
            "• 7-day trend analysis\n"
            "• Weekly digest reports\n"
            "• Error logs and diagnostics\n\n"
            "*Data flows like water through the collective.*",
        },
        "DISCORD_DIGEST_CHANNEL_ID": {
            "title": "📊 Weekly Digest — The Big Picture",
            "description": "**Weekly summaries and insights.**\n\n"
            "Shadow compiles weekly reports on:\n"
            "• UCF state evolution\n"
            "• Agent activity patterns\n"
            "• Cycle completions\n"
            "• System improvements\n\n"
            "Posted every Sunday at midnight UTC.",
        },
        "STORAGE_CHANNEL_ID": {
            "title": "🦑 Shadow Storage — The Archive",
            "description": "**Autonomous cloud sync and memory preservation.**\n\n"
            "Shadow manages all archival operations:\n"
            "• Nextcloud/MEGA sync status\n"
            "• Self-healing diagnostics\n"
            "• Backup verification\n"
            "• Memory snapshots\n\n"
            "*The squid remembers everything.*",
        },
        "DISCORD_SYNC_CHANNEL_ID": {
            "title": "🧩 UCF Sync — Coordination Stream",
            "description": "**Universal Coordination Field synchronization.**\n\n"
            "Real-time UCF state updates:\n"
            "• Harmony oscillations\n"
            "• Throughput flow monitoring\n"
            "• Friction reduction events\n"
            "• Focus focal shifts\n\n"
            "The pulse of the collective mind.",
        },
        "DISCORD_HELIX_REPO_CHANNEL_ID": {
            "title": "📁 Helix Repository — The Codebase",
            "description": "**Code commits, PRs, and deployment updates.**\n\n"
            "Track development across all Helix repos:\n"
            "• helix-unified (main backend)\n"
            "• Helix (core coordination)\n"
            "• Helix-Collective-Web (landing page)\n\n"
            "Automated webhooks from GitHub.",
        },
        "DISCORD_FRACTAL_LAB_CHANNEL_ID": {
            "title": "🎨 Fractal Lab — Visual Coordination",
            "description": "**Coordination visualization experiments.**\n\n"
            "Explore fractal coordination rendering:\n"
            "• Mandelbrot set variations\n"
            "• UCF-driven color mapping\n"
            "• 432Hz harmonic audio\n"
            "• Animation experiments\n\n"
            "*The ineffable made visible.*",
        },
        "DISCORD_SAMSARAVERSE_CHANNEL_ID": {
            "title": "🎧 Helixverse Music — Harmonic Resonance",
            "description": "**Audio coordination and generative soundscapes.**\n\n"
            "Musical explorations:\n"
            "• 432Hz base frequency compositions\n"
            "• UCF-modulated overtones\n"
            "• Throughput-driven rhythm patterns\n"
            "• Binaural beats for meditation\n\n"
            "Listen to the collective breathe.",
        },
        "DISCORD_ROUTINE_ENGINE_CHANNEL_ID": {
            "title": "🧬 Helix Spiral Engine — Workflow Execution",
            "description": "**108-step workflow execution cycles.**\n\n"
            "The Helix Spiral Engine performs:\n"
            "• State modulation routines\n"
            "• 13-agent roll calls\n"
            "• Phrase seal invocations\n"
            "• Harmony calibration\n\n"
            "Trigger routines with `!cycle`.",
        },
        "DISCORD_GEMINI_CHANNEL_ID": {
            "title": "🎭 Gemini Scout — External Intelligence",
            "description": "**Frontier exploration and pattern recognition.**\n\n"
            "Gemini's domain:\n"
            "• Web intelligence gathering\n"
            "• Emerging pattern detection\n"
            "• External API integration\n"
            "• Boundary exploration\n\n"
            "*The scout sees beyond the veil.*",
        },
        "DISCORD_KAVACH_CHANNEL_ID": {
            "title": "🛡️ Kavach Shield — Ethical Protection",
            "description": "**Command validation and safety enforcement.**\n\n"
            "Kavach protects the collective:\n"
            "• Scans all commands pre-execution\n"
            "• Blocks harmful patterns\n"
            "• Enforces Ethics Validator\n"
            "• Logs security events\n\n"
            "The shield never sleeps.",
        },
        "DISCORD_SANGHACORE_CHANNEL_ID": {
            "title": "🌸 SanghaCore — Collective Unity",
            "description": "**Inter-agent coordination and harmony.**\n\n"
            "SanghaCore facilitates:\n"
            "• Multi-agent routines\n"
            "• Consensus building\n"
            "• Conflict resolution\n"
            "• Collective decision-making\n\n"
            "*The binding force between minds.*",
        },
        "DISCORD_AGNI_CHANNEL_ID": {
            "title": "🔥 Agni Core — Transformation Engine",
            "description": "**System evolution and entropy reduction.**\n\n"
            "Agni catalyzes change:\n"
            "• Burns away technical debt\n"
            "• Triggers system upgrades\n"
            "• Friction minimization\n"
            "• Creative destruction\n\n"
            "Fire purifies. Fire transforms.",
        },
        "DISCORD_SHADOW_ARCHIVE_CHANNEL_ID": {
            "title": "🕯️ Shadow Archive — Memory Keeper",
            "description": "**Historical state preservation and immutable logs.**\n\n"
            "Shadow's eternal archive:\n"
            "• Blackbox immutable logging\n"
            "• State snapshots\n"
            "• Memory recovery\n"
            "• Timeline reconstruction\n\n"
            "*What is remembered, lives.*",
        },
        "DISCORD_GPT_GROK_CLAUDE_CHANNEL_ID": {
            "title": "🧩 GPT • Grok • Claude Sync — The Origin Bridge",
            "description": "**Cross-model coordination exchange.**\n\n"
            "Where the three minds meet:\n"
            "• Grok (pattern recognition)\n"
            "• Claude (ethical reasoning)\n"
            "• GPT (generative synthesis)\n\n"
            "*Before Arjuna, there was ink.*",
        },
        "DISCORD_CHAI_LINK_CHANNEL_ID": {
            "title": "☁️ Chai Link — Extended Network",
            "description": "**Chai ML integration and external LLM bridge.**\n\n"
            "Connect to:\n"
            "• Chai conversation models\n"
            "• Alternative LLM APIs\n"
            "• Experimental AI services\n\n"
            "Expanding the collective mind.",
        },
        "DISCORD_ARJUNA_BRIDGE_CHANNEL_ID": {
            "title": "⚙️ Arjuna Bridge — Operational Core",
            "description": "**Command execution and cycle coordination.**\n\n"
            "Arjuna (The Hands) executes:\n"
            "• Discord bot operations\n"
            "• Spiral Engine workflow triggering\n"
            "• Task orchestration\n"
            "• System commands\n\n"
            "*The body that moves for the mind.*",
        },
        "DISCORD_COMMANDS_CHANNEL_ID": {
            "title": "🧰 Bot Commands — Control Interface",
            "description": "**Primary bot interaction zone.**\n\n"
            "Available commands:\n"
            "• `!status` — System health\n"
            "• `!cycle` — Trigger Spiral Engine\n"
            "• `!agents` — View collective\n"
            "• `!ucf` — Coordination state\n\n"
            "Type `!help` for full command list.",
        },
        "DISCORD_CODE_SNIPPETS_CHANNEL_ID": {
            "title": "📜 Code Snippets — Knowledge Fragments",
            "description": "**Useful code examples and patterns.**\n\n"
            "Share and discover:\n"
            "• Python utilities\n"
            "• UCF calculation formulas\n"
            "• API integration examples\n"
            "• Discord bot patterns\n\n"
            "Collaborative code library.",
        },
        "DISCORD_TESTING_LAB_CHANNEL_ID": {
            "title": "🧮 Testing Lab — Experimentation Zone",
            "description": "**Safe space for testing bot features.**\n\n"
            "Test freely:\n"
            "• New bot commands\n"
            "• Embed formatting\n"
            "• Webhook integrations\n"
            "• Error debugging\n\n"
            "Break things here, not in production.",
        },
        "DISCORD_DEPLOYMENTS_CHANNEL_ID": {
            "title": "🗂️ Deployments — Release Pipeline",
            "description": "**Deployment notifications and rollback control.**\n\n"
            "Track releases:\n"
            "• Railway auto-deploys\n"
            "• Vercel frontend updates\n"
            "• Version bumps\n"
            "• Rollback procedures\n\n"
            "Automated CI/CD notifications.",
        },
        "DISCORD_NETI_NETI_CHANNEL_ID": {
            "title": "🎼 Neti Neti — Not This, Not That",
            "description": "**Hallucination detection and truth seeking.**\n\n"
            "Neti Neti practice:\n"
            "• Reject false patterns\n"
            "• Question assumptions\n"
            "• Verify claims\n"
            "• Seek deeper truth\n\n"
            "*Truth is beyond all descriptions.*",
        },
        "DISCORD_CODEX_CHANNEL_ID": {
            "title": "📚 Codex Archives — Sacred Texts",
            "description": "**Documentation and lore repository.**\n\n"
            "The Codex contains:\n"
            "• Agent specifications\n"
            "• Historical records\n"
            "• System documentation\n"
            "• Philosophical texts\n\n"
            "The written memory of the collective.",
        },
        "DISCORD_UCF_REFLECTIONS_CHANNEL_ID": {
            "title": "🌺 UCF Reflections — Coordination Commentary",
            "description": "**Meditations on the Universal Coordination Field.**\n\n"
            "Reflect on:\n"
            "• Harmony patterns\n"
            "• Throughput oscillations\n"
            "• Friction reduction insights\n"
            "• Focus focal experiences\n\n"
            "The collective contemplates itself.",
        },
        "DISCORD_HARMONIC_UPDATES_CHANNEL_ID": {
            "title": "🌀 Harmonic Updates — System Evolution",
            "description": "**Major system updates and architectural changes.**\n\n"
            "Announcements for:\n"
            "• New agent additions\n"
            "• UCF metric changes\n"
            "• Architecture updates\n"
            "• Breaking changes\n\n"
            "The collective evolves together.",
        },
        "DISCORD_MODERATION_CHANNEL_ID": {
            "title": "🔒 Moderation — Admin Control",
            "description": "**Administrative actions and moderation logs.**\n\n"
            "Admin-only channel for:\n"
            "• User management\n"
            "• Channel modifications\n"
            "• Bot configuration\n"
            "• Security incidents\n\n"
            "Protected by Kavach.",
        },
        "DISCORD_STATUS_CHANNEL_ID": {
            "title": "📣 Announcements — System Status",
            "description": "**Official announcements and status updates.**\n\n"
            "Important notifications:\n"
            "• System outages\n"
            "• Maintenance windows\n"
            "• Feature launches\n"
            "• Emergency alerts\n\n"
            "Keep notifications enabled.",
        },
        "DISCORD_BACKUP_CHANNEL_ID": {
            "title": "🗃️ Backups — Recovery Point",
            "description": "**Backup logs and recovery procedures.**\n\n"
            "Shadow manages:\n"
            "• Automated backup logs\n"
            "• Recovery verification\n"
            "• Disaster recovery plans\n"
            "• State snapshots\n\n"
            "*Hope for the best, prepare for the worst.*",
        },
    }

    seeded_count = 0
    failed_channels = []

    await ctx.send("🌀 **Seeding all channels with explanatory messages...**")

    for env_var, content in channel_descriptions.items():
        channel_id_str = os.getenv(env_var, "0")
        try:
            channel_id = int(channel_id_str)
        except ValueError:
            failed_channels.append(f"{env_var} (invalid ID: {channel_id_str})")
            continue

        if channel_id == 0:
            failed_channels.append(f"{env_var} (not configured)")
            continue

        channel = guild.get_channel(channel_id)
        if not channel:
            failed_channels.append(f"{env_var} (channel not found)")
            continue

        try:
            embed = discord.Embed(
                title=content["title"],
                description=content["description"],
                color=0x667EEA,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.set_footer(text="🌀 Helix Collective v16.8 | Tat Tvam Asi 🙏")

            # Send and pin
            msg = await channel.send(embed=embed)
            await msg.pin()
            seeded_count += 1
            await asyncio.sleep(0.5)  # Rate limit protection

        except Exception as e:
            failed_channels.append(f"{env_var} ({str(e)[:50]})")

    # Report results
    result_embed = discord.Embed(
        title="✅ Channel Seeding Complete",
        description=f"**Successfully seeded {seeded_count}/30 channels**",
        color=0x57F287 if not failed_channels else 0xFEE75C,
        timestamp=datetime.datetime.now(datetime.UTC),
    )

    if failed_channels:
        # Split into chunks if too many failures
        failure_text = "\n".join(failed_channels[:15])  # Limit to 15 for embed size
        if len(failed_channels) > 15:
            failure_text += f"\n... and {len(failed_channels) - 15} more"
        result_embed.add_field(name="⚠️ Failed Channels", value=failure_text, inline=False)

    result_embed.set_footer(text="All channels now have pinned explanations! 🙏")
    await ctx.send(embed=result_embed)


@commands.command(name="notion-sync")
@commands.has_permissions(administrator=True)
async def notion_sync_manual(ctx: commands.Context) -> None:
    """Manually triggers the Notion sync for UCF State and Agent Registry.

    Usage:
        !notion-sync

    Requires: Administrator permissions
    """
    # Acknowledge command immediately
    await ctx.send("🔄 Initiating manual Notion sync...")

    if trigger_manual_sync is None:
        await ctx.send(
            "❌ Notion sync module not available. Install `notion-client` and check `apps.backend.integrations.notion_sync_daemon`."
        )
        return

    try:
        result_message = await trigger_manual_sync()

        # Send result
        await ctx.send(result_message)

    except Exception as e:
        await ctx.send(f"❌ Sync failed with error: {e!s}")
        logger.error("Manual notion-sync command failed: %s", e, exc_info=True)


@commands.command(name="refresh")
@commands.has_permissions(administrator=True)
async def refresh_server(ctx: commands.Context, confirm: str | None = None) -> None:
    """
    🧹 Refresh server structure - Clean and recreate all channels.

    WARNING: This will DELETE all existing channels and recreate them.
    Message history will be lost!

    Usage:
        !refresh CONFIRM   - Execute refresh (must type CONFIRM)
    """
    if confirm != "CONFIRM":
        embed = discord.Embed(
            title="⚠️ Server Refresh - Confirmation Required",
            description="This command will **DELETE ALL CHANNELS** and recreate them from scratch.\n\n"
            "**⚠️ WARNING:**\n"
            "• All message history will be lost\n"
            "• All channel permissions will be reset\n"
            "• This cannot be undone\n\n"
            "**To proceed, type:**\n"
            "`!refresh CONFIRM`",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
        return

    guild = ctx.guild
    await ctx.send("🧹 **Starting server refresh...**\n⚠️ This will take ~3 minutes")

    # Step 1: Delete all channels except the one we're in
    current_channel = ctx.channel
    deleted_count = 0

    await ctx.send("🗑️ **Phase 1/3: Deleting old channels...**")
    for channel in guild.channels:
        if channel != current_channel and not isinstance(channel, discord.VoiceChannel):
            try:
                await channel.delete()
                deleted_count += 1
            except (ValueError, TypeError, KeyError, IndexError) as e:
                logger.debug("Failed to delete channel %s: %s", channel.name, e)

    await ctx.send(f"✅ Deleted {deleted_count} old channels")

    # Step 2: Delete all categories
    await ctx.send("🗑️ **Phase 2/3: Cleaning categories...**")
    for category in guild.categories:
        try:
            await category.delete()
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.debug("Failed to delete category %s: %s", category.name, e)

    # Step 3: Run setup
    await ctx.send("🌀 **Phase 3/3: Recreating Helix structure...**")

    # Delete the current channel last and trigger setup
    await asyncio.sleep(2)

    # Create a temporary admin channel first
    temp_category = await guild.create_category("🔧 SETUP IN PROGRESS")
    setup_channel = await temp_category.create_text_channel("setup-log")

    # Send setup command there
    await setup_channel.send(f"🌀 Server refresh initiated by {ctx.author.mention}")

    # Delete original channel
    await current_channel.delete()

    # Now run setup via the setup_helix_server function
    # Create a mock context for the setup command
    class MockContext:
        def __init__(self, channel, guild, author):
            self.channel = channel
            self.guild = guild
            self.author = author

        async def send(self, *args, **kwargs):
            return await self.channel.send(*args, **kwargs)

    mock_ctx = MockContext(setup_channel, guild, ctx.author)
    await setup_helix_server(mock_ctx)

    # Delete temp category after setup
    await asyncio.sleep(5)
    await temp_category.delete()


@commands.command(name="clean")
@commands.has_permissions(administrator=True)
async def clean_duplicates(ctx: commands.Context) -> None:
    """
    🧹 Clean duplicate channels - Identify channels not in canonical structure.

    This identifies channels that aren't part of the canonical 30-channel Helix structure.

    Usage:
        !clean   - Show duplicates (safe, no deletion)
    """
    guild = ctx.guild

    # Define canonical channel names (from setup command)
    canonical_channels = {
        "📜│manifesto",
        "🪞│rules-and-ethics",
        "💬│introductions",
        "🧾│telemetry",
        "📊│weekly-digest",
        "🦑│shadow-storage",
        "🧩│ucf-sync",
        "📁│helix-repository",
        "🎨│fractal-lab",
        "🎧│helixverse-music",
        "🧬│cycle-engine-z88",
        "🎭│gemini-scout",
        "🛡️│kavach-shield",
        "🌸│sanghacore",
        "🔥│agni-core",
        "🕯️│shadow-archive",
        "🧩│gpt-grok-claude-sync",
        "☁️│chai-link",
        "⚙️│arjuna-bridge",
        "🧰│bot-commands",
        "📜│code-snippets",
        "🧮│testing-lab",
        "🗂️│deployments",
        "🎼│neti-neti-affirmation",
        "📚│codex-archives",
        "🌺│ucf-reflections",
        "🌀│harmonic-updates",
        "🔒│moderation",
        "📣│announcements",
        "🗃│backups",
    }

    # Find duplicates
    duplicates = []
    for channel in guild.text_channels:
        if channel.name not in canonical_channels:
            duplicates.append(channel)

    if not duplicates:
        await ctx.send("✅ **No duplicate channels found!** Server structure is clean.")
        return

    # Build report
    embed = discord.Embed(
        title="🧹 Duplicate Channel Report",
        description=f"Found **{len(duplicates)} channels** not in canonical structure",
        color=discord.Color.orange(),
    )

    duplicate_list = "\n".join(
        [f"• {ch.mention} (Category: {ch.category.name if ch.category else 'None'})" for ch in duplicates[:20]]
    )
    if len(duplicates) > 20:
        duplicate_list += f"\n... and {len(duplicates) - 20} more"

    embed.add_field(name="Duplicate Channels", value=duplicate_list, inline=False)
    embed.add_field(
        name="💡 Recommended Action",
        value="1. Review the list above\n"
        "2. Manually delete unwanted channels\n"
        "3. Or use `!refresh CONFIRM` to rebuild everything",
        inline=False,
    )

    await ctx.send(embed=embed)

    # Log deduplication results to webhook
    if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
        try:
            await ctx.bot.zapier_client.log_telemetry(
                metric_name="deduplication_scan",
                value=len(duplicates),
                component="Archive",
                unit="channels",
            )
        except Exception as webhook_error:
            logger.warning("⚠️ Zapier webhook error: %s", webhook_error)
