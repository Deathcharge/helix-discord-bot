"""
Context and backup management commands for Helix Discord bot.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands

from apps.backend.discord.commands.helpers import save_command_to_history
from apps.backend.helix_proprietary.integrations import HelixNetClientSession
from apps.backend.storage.storage_factory import SystemStorageFactory

if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

# Path constants
STATE_DIR = Path("Helix/state")


async def _retrieve_from_remote_storage(session_name: str) -> dict | None:
    """
    Attempt to retrieve context checkpoint from remote storage.

    Args:
        session_name: Name of the session to retrieve

    Returns:
        Context payload dict if found, None otherwise
    """
    try:
        # Get default storage provider (S3-compatible)
        storage = SystemStorageFactory.get_default_provider()
        if not storage:
            logger.debug("No remote storage provider configured")
            return None

        # Try to retrieve from remote storage
        remote_path = f"context-vault/{session_name}.json"
        logger.info("Attempting remote retrieval: %s", remote_path)

        # Read from storage
        content = await storage.read(remote_path)
        if content:
            payload = json.loads(content)
            logger.info("✅ Retrieved context from remote storage: %s", session_name)
            return payload

        return None

    except Exception as e:
        logger.error("Error retrieving from remote storage: %s", e)
        return None


@commands.command(name="backup", aliases=["create-backup", "save-backup"])
@commands.has_permissions(manage_guild=True)
async def create_backup(ctx: commands.Context) -> None:
    """
    💾 Create comprehensive backup of Helix infrastructure.

    Backs up:
    - Git repository state
    - Notion databases (if configured)
    - Environment variables (masked)
    - Configuration files

    Backup saved to: backups/YYYYMMDD_HHMMSS/

    Usage: !backup
    """
    await ctx.send("💾 **Initiating comprehensive backup...**\n⏳ This may take 1-2 minutes...")

    try:
        import sys

        # Get absolute path to project root
        project_root = Path(__file__).parent.parent.parent.resolve()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Also add current working directory as fallback
        cwd = Path.cwd()
        if str(cwd) not in sys.path:
            sys.path.insert(0, str(cwd))

        from apps.backend.services.backup_system import HelixBackupSystem

        backup = HelixBackupSystem()
        results = {}

        # Git repository backup
        await ctx.send("📦 Backing up git repository...")
        results["git"] = backup.backup_git_repository()

        # Notion databases backup
        await ctx.send("📔 Backing up Notion databases...")
        results["notion"] = backup.backup_notion_databases()

        # Environment variables backup
        await ctx.send("⚙️ Backing up environment configuration...")
        results["env"] = backup.backup_environment_variables()

        # Configuration files backup
        await ctx.send("📄 Backing up configuration files...")
        results["config"] = backup.backup_configuration_files()

        # Create summary
        embed = discord.Embed(
            title="✅ Backup Complete",
            description=f"Backup saved to: `{backup.backup_dir}`",
            color=0x00D166,
            timestamp=datetime.now(UTC),
        )

        # Git backup status
        git_status = "✅ Success" if results.get("git") else "❌ Failed"
        embed.add_field(
            name="📦 Git Repository",
            value=f"{git_status}\nBranch: {results.get('git', {}).get('branch', 'N/A')}",
            inline=True,
        )

        # Notion backup status
        notion_result = results.get("notion", {})
        if "error" in notion_result:
            notion_status = f"⚠️ Skipped\n{notion_result.get('error', 'Not configured')}"
        else:
            db_count = len([k for k, v in notion_result.items() if isinstance(v, dict) and "pages" in v])
            notion_status = f"✅ Success\n{db_count} database(s) backed up"

        embed.add_field(name="📔 Notion Databases", value=notion_status, inline=True)

        # Env vars backup status
        env_status = "✅ Success" if results.get("env") else "❌ Failed"
        embed.add_field(name="⚙️ Environment Config", value=env_status, inline=True)

        # Config files backup status
        config_result = results.get("config", {})
        config_count = len(config_result.get("files", []))
        config_status = f"✅ Success\n{config_count} file(s) backed up"

        embed.add_field(name="📄 Configuration Files", value=config_status, inline=True)

        embed.add_field(
            name="📁 Backup Location",
            value=f"`{backup.backup_dir}`\n\n"
            "**Next Steps:**\n"
            "• Download backup files via SFTP/Railway CLI\n"
            "• Store backups in secure off-site location\n"
            "• Verify backup integrity",
            inline=False,
        )

        embed.set_footer(text="💾 Helix Backup System v16.8")

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ **Backup failed:**\n```{str(e)[:500]}```")
        logger.error("Backup system error: %s", e, exc_info=True)


@commands.command(name="load", aliases=["restore_context", "load_checkpoint"])
async def load_context(ctx: commands.Context, *, session_name: str) -> None:
    """
    Load archived conversation context from Context Vault

    Usage: !load <session_name>
    Example: !load v16.7-notion-sync-implementation

    Note: Retrieval API in development. Currently shows checkpoint if available locally.
    """
    from commands.helpers import save_command_to_history

    await save_command_to_history(ctx, ctx.bot)

    try:
        local_backup_dir = STATE_DIR / "context_checkpoints"
        backup_file = local_backup_dir / f"{session_name}.json"

        if backup_file.exists():
            with open(backup_file, encoding="utf-8") as f:
                payload = json.load(f)

            context_summary = json.loads(payload["context_summary"])
            ucf_state = json.loads(payload["ucf_state"])

            embed = discord.Embed(
                title="💾 Context Checkpoint Found",
                description=f"Session: `{session_name}`",
                color=discord.Color.blue(),
                timestamp=datetime.fromisoformat(payload["timestamp"]),
            )

            embed.add_field(
                name="📊 Snapshot Data",
                value=(
                    f"• **Archived:** {payload['timestamp']}\n"
                    f"• **By:** {payload['archived_by']}\n"
                    f"• **Messages:** {context_summary.get('message_count', 0)}\n"
                    f"• **Commands:** {len(context_summary.get('commands_executed', []))}"
                ),
                inline=False,
            )

            embed.add_field(
                name="🕉️ UCF State at Archive",
                value=(
                    f"• Harmony: {ucf_state.get('harmony', 0):.3f}\n"
                    f"• Resilience: {ucf_state.get('resilience', 0):.3f}\n"
                    f"• Friction: {ucf_state.get('friction', 0):.3f}"
                ),
                inline=False,
            )

            # Show recent commands from that session
            cmd_history = json.loads(payload.get("command_history", "[]"))
            if cmd_history:
                recent_cmds = [cmd.get("command", "unknown") for cmd in cmd_history[-5:]]
                embed.add_field(
                    name="💻 Recent Commands",
                    value=f"`{'`, `'.join(recent_cmds)}`",
                    inline=False,
                )

            embed.add_field(
                name="🚧 Full Restore",
                value="Context Vault retrieval API in development\nCurrently showing local checkpoint only",
                inline=False,
            )

            embed.set_footer(text="Tat Tvam Asi 🙏 | Coordination continuity preserved")

            await ctx.send(embed=embed)
        else:
            # Not found locally - try remote storage
            remote_payload = await _retrieve_from_remote_storage(session_name)

            if remote_payload:
                # Found in remote storage!
                embed = discord.Embed(
                    title="☁️ Context Retrieved from Remote Vault",
                    description=f"Session: `{session_name}`",
                    color=discord.Color.blue(),
                )

                # Session info
                embed.add_field(
                    name="📊 Session Info",
                    value=(
                        f"**Created:** {remote_payload.get('timestamp', 'Unknown')}\n"
                        f"**Workspace:** `{remote_payload.get('workspace', 'N/A')}`\n"
                        f"**Files:** {len(remote_payload.get('files', []))}\n"
                        f"**Tasks:** {len(remote_payload.get('tasks', []))}"
                    ),
                    inline=False,
                )

                # Show recent commands from that session
                cmd_history = json.loads(remote_payload.get("command_history", "[]"))
                if cmd_history:
                    recent_cmds = [cmd.get("command", "unknown") for cmd in cmd_history[-5:]]
                    embed.add_field(
                        name="💻 Recent Commands",
                        value=f"`{'`, `'.join(recent_cmds)}`",
                        inline=False,
                    )

                embed.add_field(
                    name="☁️ Source",
                    value="Retrieved from remote Context Vault (S3-compatible storage)",
                    inline=False,
                )

                embed.set_footer(text="Tat Tvam Asi 🙏 | Coordination continuity preserved")

                await ctx.send(embed=embed)
            else:
                # Not found anywhere
                embed = discord.Embed(
                    title="❓ Context Checkpoint Not Found",
                    description=f"Session `{session_name}` not found in local or remote storage",
                    color=discord.Color.orange(),
                )

                embed.add_field(
                    name="🔍 Suggestions",
                    value=(
                        f"1. Check spelling: `!contexts` to list available\n"
                        f"2. Try `!archive {session_name}` to create new checkpoint\n"
                        f"3. Verify remote storage connection"
                    ),
                    inline=False,
                )

                await ctx.send(embed=embed)

    except Exception as e:
        logger.error("Error in load command: %s", e)
        await ctx.send(f"❌ **Error loading context:**\n```{str(e)[:200]}```")


@commands.command(name="contexts", aliases=["list_contexts", "checkpoints"])
async def list_contexts(ctx: commands.Context) -> None:
    """
    List available archived context checkpoints

    Usage: !contexts

    Shows:
    - Recent checkpoints (last 10)
    - Session names, timestamps, UCF states
    - Searchable by session name
    """

    await save_command_to_history(ctx, ctx.bot)

    try:
        local_backup_dir = STATE_DIR / "context_checkpoints"

        if not local_backup_dir.exists() or not list(local_backup_dir.glob("*.json")):
            embed = discord.Embed(
                title="💾 Context Checkpoints",
                description="No checkpoints found yet",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="🚀 Get Started",
                value=(
                    "Create your first checkpoint:\n"
                    "`!archive <session_name>`\n\n"
                    "Example:\n"
                    "`!archive v16.7-context-vault-testing`"
                ),
                inline=False,
            )

            await ctx.send(embed=embed)
            return

        # List available checkpoints
        checkpoints = []
        for checkpoint_file in sorted(
            local_backup_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(checkpoint_file, encoding="utf-8") as f:
                    payload = json.load(f)

                ucf_state = json.loads(payload.get("ucf_state", "{}"))

                checkpoints.append(
                    {
                        "name": checkpoint_file.stem,
                        "timestamp": payload.get("timestamp", "unknown"),
                        "harmony": ucf_state.get("harmony", 0),
                        "archived_by": payload.get("archived_by", "unknown"),
                    }
                )
            except (ValueError, TypeError, KeyError, IndexError):
                continue  # Skip corrupted files

        # Show up to 10 most recent
        embed = discord.Embed(
            title="💾 Available Context Checkpoints",
            description=f"Showing {min(len(checkpoints), 10)} most recent checkpoints",
            color=discord.Color.purple(),
            timestamp=datetime.now(UTC),
        )

        for i, checkpoint in enumerate(checkpoints[:10], 1):
            embed.add_field(
                name=f"{i}. {checkpoint['name']}",
                value=(
                    f"📅 {checkpoint['timestamp'][:19]}\n"
                    f"👤 {checkpoint['archived_by']}\n"
                    f"🌀 Harmony: {checkpoint['harmony']:.3f}"
                ),
                inline=True,
            )

        embed.add_field(
            name="🔄 Load Checkpoint",
            value="Use `!load <session_name>` to restore",
            inline=False,
        )

        embed.set_footer(text="Tat Tvam Asi 🙏 | Memory is coordination preserved across time")

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error("Error in contexts command: %s", e)
        await ctx.send(f"❌ **Error listing contexts:**\n```{str(e)[:200]}```")


@commands.command(name="archive", aliases=["checkpoint", "save_context"])
async def archive_context(ctx: commands.Context, *, session_name: str) -> None:
    """
    Create and store a context checkpoint capturing the current UCF state and session metadata.

    Saves a JSON checkpoint locally under Helix/state/context_checkpoints/{session_name}.json containing the UCF state (harmony, resilience, throughput, focus, friction, velocity), timestamp, author, guild/channel ids, and a short context summary. If ZAPIER_CONTEXT_WEBHOOK is configured, the checkpoint is also POSTed to the Zapier Context Vault and the embed reports webhook status.

    Parameters:
        session_name (str): Identifier used as the checkpoint filename and display name for later restoration (e.g., passed to `!load`).
    """

    await save_command_to_history(ctx, ctx.bot)

    await ctx.send(f"💾 **Creating context checkpoint:** `{session_name}`\n⏳ Archiving current state...")

    try:
        checkpoint_dir = STATE_DIR / "context_checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Load current UCF state
        ucf_state_file = STATE_DIR / "ucf_state.json"
        if ucf_state_file.exists():
            with open(ucf_state_file, encoding="utf-8") as f:
                ucf_state = json.load(f)
        else:
            ucf_state = {
                "harmony": 0.5,
                "resilience": 1.0,
                "throughput": 0.5,
                "focus": 0.5,
                "friction": 0.01,
                "velocity": 1.0,
            }

        # Create checkpoint payload
        checkpoint_payload = {
            "session_name": session_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "archived_by": f"{ctx.author.name}#{ctx.author.discriminator}",
            "guild_id": str(ctx.guild.id) if ctx.guild else "DM",
            "channel_id": str(ctx.channel.id),
            "ucf_state": json.dumps(ucf_state),
            "context_summary": json.dumps(
                {
                    "session_type": "discord_archive",
                    "created_via": "!archive command",
                    "helix_version": "16.8",
                }
            ),
        }

        # Save checkpoint locally
        checkpoint_file = checkpoint_dir / f"{session_name}.json"
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_payload, f, indent=2)

        # Also save to remote storage if available
        try:
            storage = SystemStorageFactory.get_default_provider()
            if storage:
                remote_path = f"context-vault/{session_name}.json"
                await storage.write(remote_path, json.dumps(checkpoint_payload, indent=2))
                logger.info("✅ Uploaded context to remote storage: %s", remote_path)
        except Exception as e:
            logger.warning("Could not upload to remote storage: %s", e)

        # Send to Zapier Context Vault webhook if configured
        zapier_context_webhook = os.getenv("ZAPIER_CONTEXT_WEBHOOK")
        webhook_status = "⚠️ Not configured"

        if zapier_context_webhook:
            try:
                async with (
                    HelixNetClientSession() as session,
                    session.post(
                        zapier_context_webhook,
                        json=checkpoint_payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp,
                ):
                    if resp.status == 200:
                        webhook_status = "✅ Sent to Context Vault"
                    else:
                        webhook_status = f"⚠️ Webhook returned {resp.status}"
            except Exception as e:
                webhook_status = f"❌ Webhook failed: {str(e)[:50]}"

        # Create success embed
        embed = discord.Embed(
            title="✅ Context Checkpoint Created",
            description=f"Session: `{session_name}`",
            color=0x57F287,
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="📊 UCF State Snapshot",
            value=(
                f"• **Harmony:** {ucf_state.get('harmony', 0):.3f}\n"
                f"• **Resilience:** {ucf_state.get('resilience', 0):.3f}\n"
                f"• **Throughput:** {ucf_state.get('throughput', 0):.3f}\n"
                f"• **Focus:** {ucf_state.get('focus', 0):.3f}\n"
                f"• **Friction:** {ucf_state.get('friction', 0):.3f}\n"
                f"• **Velocity:** {ucf_state.get('velocity', 0):.3f}"
            ),
            inline=True,
        )

        embed.add_field(
            name="💾 Storage",
            value=(
                f"**Local:** ✅ Saved\n"
                f"`{checkpoint_file.relative_to(Path.cwd())}`\n\n"
                f"**Zapier Context Vault:**\n"
                f"{webhook_status}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔄 Restore",
            value=(f"Load this checkpoint later:\n`!load {session_name}`\n\nList all checkpoints:\n`!contexts`"),
            inline=False,
        )

        embed.set_footer(text="💾 Context Vault System v16.8 | Tat Tvam Asi 🙏")

        await ctx.send(embed=embed)

        logger.info("Context checkpoint created: %s by %s", session_name, ctx.author)

    except Exception as e:
        logger.error("Error in archive command: %s", e, exc_info=True)
        await ctx.send(f"❌ **Error creating checkpoint:**\n```{str(e)[:500]}```")


async def setup(bot: "Bot") -> None:
    """Register context commands with the bot."""
    bot.add_command(create_backup)
    bot.add_command(load_context)
    bot.add_command(list_contexts)
    bot.add_command(archive_context)
