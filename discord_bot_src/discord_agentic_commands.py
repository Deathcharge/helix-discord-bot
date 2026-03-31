"""
🤖 Discord Agentic Coding Commands
===================================
Discord slash commands for collaborative code editing directly from Discord.

Features:
- /agentic connect - Link a repository to a Discord channel
- /agentic edit - Make code changes with diff preview
- /agentic commit - Commit staged changes
- /agentic status - Check git status
- /agentic search - Search codebase
- /agentic task - Create/manage autonomous coding tasks
- /agentic settings - Configure permissions

Security:
- Opt-in per repository (owners must enable)
- Role-based permissions (who can edit vs read-only)
- Channel restrictions (limit to specific channels)
- Audit logging (all changes tracked)

Copyright (c) 2025 Andrew John Ward. All Rights Reserved.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands

# Try to import agentic coder service
try:
    from apps.backend.services.agentic_coder import (
        AgenticCoder,
        CodeValidator,
        DiffEditor,
        GitOperations,
    )

    HAS_AGENTIC = True
except ImportError:
    HAS_AGENTIC = False

# Optional Redis for durable connection persistence
try:
    import redis.asyncio as _aioredis

    _redis_client: "_aioredis.Redis | None" = _aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )
    HAS_REDIS = True
except Exception:
    _redis_client = None
    HAS_REDIS = False

_REDIS_KEY = "helix:discord:agentic_connections"

logger = logging.getLogger(__name__)


# ============================================================================
# PERMISSION SYSTEM
# ============================================================================


class AgenticPermission(Enum):
    """Permission levels for agentic coding"""

    NONE = 0  # No access
    READ = 1  # Can view status, search code
    SUGGEST = 2  # Can suggest edits (requires approval)
    EDIT = 3  # Can make direct edits
    ADMIN = 4  # Can configure settings, manage permissions


@dataclass
class RepositoryConnection:
    """A connected repository for Discord agentic coding"""

    repo_id: str  # Unique ID
    repo_path: str  # Local path or GitHub repo
    owner_discord_id: int  # Discord user who connected it
    guild_id: int  # Discord server ID
    channel_ids: list[int] = field(default_factory=list)  # Allowed channels (empty = all)

    # Permissions
    admin_role_ids: list[int] = field(default_factory=list)  # Roles with ADMIN
    editor_role_ids: list[int] = field(default_factory=list)  # Roles with EDIT
    suggester_role_ids: list[int] = field(default_factory=list)  # Roles with SUGGEST
    reader_role_ids: list[int] = field(default_factory=list)  # Roles with READ

    # Feature flags
    allow_commits: bool = False  # Can commits be made directly?
    require_approval: bool = True  # Require approval for edits?
    auto_preview: bool = True  # Auto-generate diff previews?
    audit_channel_id: int | None = None  # Channel for audit logs

    # GitHub integration
    github_repo: str | None = None  # owner/repo format
    github_branch: str = "main"  # Default branch

    # Metadata
    connected_at: str = ""
    last_activity: str = ""

    def __post_init__(self):
        if not self.connected_at:
            self.connected_at = datetime.now(UTC).isoformat()


class AgenticConnectionManager:
    """Manages repository connections for Discord agentic coding.

    Persistence hierarchy:
      1. Redis (primary — survives Railway redeploys)
      2. JSON file (fallback when Redis unavailable)

    Write-through cache: every mutation writes to Redis and the local dict
    simultaneously so in-memory reads are always fast.
    """

    def __init__(self, storage_path: str = "data/discord_agentic_connections.json"):
        self.storage_path = storage_path
        # Write-through cache over Redis
        self.connections: dict[str, RepositoryConnection] = {}
        self._load_sync()

    # ------------------------------------------------------------------ helpers

    def _conn_to_dict(self, conn: "RepositoryConnection") -> dict:
        return {
            "repo_id": conn.repo_id,
            "repo_path": conn.repo_path,
            "owner_discord_id": conn.owner_discord_id,
            "guild_id": conn.guild_id,
            "channel_ids": conn.channel_ids,
            "admin_role_ids": conn.admin_role_ids,
            "editor_role_ids": conn.editor_role_ids,
            "suggester_role_ids": conn.suggester_role_ids,
            "reader_role_ids": conn.reader_role_ids,
            "allow_commits": conn.allow_commits,
            "require_approval": conn.require_approval,
            "auto_preview": conn.auto_preview,
            "audit_channel_id": conn.audit_channel_id,
            "github_repo": conn.github_repo,
            "github_branch": conn.github_branch,
            "connected_at": conn.connected_at,
            "last_activity": conn.last_activity,
        }

    # ------------------------------------------------------------------ sync load (startup)

    def _load_sync(self):
        """Load from JSON file at startup (Redis loaded async on first use)."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for repo_id, conn_data in data.items():
                        self.connections[repo_id] = RepositoryConnection(**conn_data)
        except Exception as e:
            logger.error("Failed to load agentic connections from file: %s", e)

    async def _load_from_redis(self) -> bool:
        """Overwrite local cache with Redis data. Returns True if Redis had data."""
        if not _redis_client:
            return False
        try:
            raw = await _redis_client.get(_REDIS_KEY)
            if raw:
                data = json.loads(raw)
                self.connections = {repo_id: RepositoryConnection(**conn_data) for repo_id, conn_data in data.items()}
                return True
        except Exception as e:
            logger.warning("Failed to load agentic connections from Redis: %s", e)
        return False

    async def _save_to_redis(self) -> None:
        """Persist current connections to Redis (non-blocking best-effort)."""
        if not _redis_client:
            return
        try:
            data = {repo_id: self._conn_to_dict(conn) for repo_id, conn in self.connections.items()}
            await _redis_client.set(_REDIS_KEY, json.dumps(data))
        except Exception as e:
            logger.warning("Failed to persist agentic connections to Redis: %s", e)

    def _save_to_file(self) -> None:
        """Persist to JSON file (fallback when Redis unavailable)."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                data = {repo_id: self._conn_to_dict(conn) for repo_id, conn in self.connections.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save agentic connections to file: %s", e)

    async def _persist(self) -> None:
        """Write-through: save to Redis (primary) and file (fallback)."""
        await self._save_to_redis()
        self._save_to_file()

    # ------------------------------------------------------------------ public API

    async def connect(self, connection: "RepositoryConnection") -> bool:
        """Add a new repository connection."""
        # Refresh from Redis first to avoid overwriting concurrent changes
        await self._load_from_redis()
        self.connections[connection.repo_id] = connection
        await self._persist()
        return True

    async def disconnect(self, repo_id: str, user_id: int) -> bool:
        """Remove a repository connection (owner only)."""
        await self._load_from_redis()
        if repo_id in self.connections:
            conn = self.connections[repo_id]
            if conn.owner_discord_id == user_id:
                del self.connections[repo_id]
                await self._persist()
                return True
        return False

    def get_connection(self, repo_id: str) -> RepositoryConnection | None:
        """Get a specific connection"""
        return self.connections.get(repo_id)

    def get_guild_connections(self, guild_id: int) -> list[RepositoryConnection]:
        """Get all connections for a guild"""
        return [c for c in self.connections.values() if c.guild_id == guild_id]

    def get_user_permission(self, repo_id: str, user: discord.Member, channel_id: int) -> AgenticPermission:
        """Determine a user's permission level for a repository"""
        conn = self.connections.get(repo_id)
        if not conn:
            return AgenticPermission.NONE

        # Check channel restriction
        if conn.channel_ids and channel_id not in conn.channel_ids:
            return AgenticPermission.NONE

        # Owner has full admin
        if user.id == conn.owner_discord_id:
            return AgenticPermission.ADMIN

        # Check role-based permissions
        user_role_ids = {r.id for r in user.roles}

        if user_role_ids & set(conn.admin_role_ids):
            return AgenticPermission.ADMIN
        if user_role_ids & set(conn.editor_role_ids):
            return AgenticPermission.EDIT
        if user_role_ids & set(conn.suggester_role_ids):
            return AgenticPermission.SUGGEST
        if user_role_ids & set(conn.reader_role_ids):
            return AgenticPermission.READ

        # Default: no access (opt-in system)
        return AgenticPermission.NONE

    def update_activity(self, repo_id: str):
        """Update last activity timestamp"""
        if repo_id in self.connections:
            self.connections[repo_id].last_activity = datetime.now(UTC).isoformat()
            self._save_to_file()


# Global connection manager
connection_manager = AgenticConnectionManager()


# ============================================================================
# PENDING EDITS (for approval workflow)
# ============================================================================


@dataclass
class PendingEdit:
    """An edit awaiting approval"""

    edit_id: str
    repo_id: str
    file_path: str
    old_text: str
    new_text: str
    description: str
    requester_id: int
    requester_name: str
    created_at: str
    diff_preview: str
    message_id: int | None = None  # Discord message with approve/reject buttons


class PendingEditManager:
    """Manages pending edits for approval workflow.

    Write-through cache over Redis — every mutation writes to Redis and local
    dict so in-memory reads stay fast.
    """

    _REDIS_KEY = "helix:discord:pending_edits"

    def __init__(self):
        # Write-through cache over Redis
        self.pending: dict[str, PendingEdit] = {}

    def _edit_to_dict(self, edit: PendingEdit) -> dict:
        return {
            "edit_id": edit.edit_id,
            "repo_id": edit.repo_id,
            "file_path": edit.file_path,
            "old_text": edit.old_text,
            "new_text": edit.new_text,
            "description": edit.description,
            "requester_id": edit.requester_id,
            "requester_name": edit.requester_name,
            "created_at": edit.created_at,
            "diff_preview": edit.diff_preview,
            "message_id": edit.message_id,
        }

    async def _load_from_redis(self) -> None:
        if not _redis_client:
            return
        try:
            raw = await _redis_client.get(self._REDIS_KEY)
            if raw:
                data = json.loads(raw)
                self.pending = {
                    eid: PendingEdit(**edata) for eid, edata in data.items()
                }
        except Exception as e:
            logger.warning("Failed to load pending edits from Redis: %s", e)

    async def _persist(self) -> None:
        if not _redis_client:
            return
        try:
            data = {eid: self._edit_to_dict(e) for eid, e in self.pending.items()}
            await _redis_client.set(self._REDIS_KEY, json.dumps(data))
        except Exception as e:
            logger.warning("Failed to persist pending edits to Redis: %s", e)

    async def add(self, edit: PendingEdit):
        await self._load_from_redis()
        self.pending[edit.edit_id] = edit
        await self._persist()

    async def get(self, edit_id: str) -> PendingEdit | None:
        await self._load_from_redis()
        return self.pending.get(edit_id)

    async def remove(self, edit_id: str):
        await self._load_from_redis()
        if edit_id in self.pending:
            del self.pending[edit_id]
            await self._persist()

    async def get_repo_pending(self, repo_id: str) -> list[PendingEdit]:
        await self._load_from_redis()
        return [e for e in self.pending.values() if e.repo_id == repo_id]


pending_edits = PendingEditManager()


# ============================================================================
# DISCORD COG
# ============================================================================


class AgenticCodingCog(commands.Cog):
    """Discord commands for collaborative agentic coding"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.diff_editor = DiffEditor() if HAS_AGENTIC else None
        self.git_ops = GitOperations() if HAS_AGENTIC else None
        self.validator = CodeValidator() if HAS_AGENTIC else None
        self.agentic_coder = AgenticCoder() if HAS_AGENTIC else None

    agentic_group = app_commands.Group(name="agentic", description="🤖 Collaborative code editing from Discord")

    # ==================== CONNECTION COMMANDS ====================

    @agentic_group.command(
        name="connect",
        description="Connect a repository to this Discord server for collaborative coding",
    )
    @app_commands.describe(
        repo_path="Local path or GitHub repo (owner/repo)",
        channel="Restrict to specific channel (optional)",
        editor_role="Role that can make edits",
        require_approval="Require approval for edits (default: true)",
    )
    async def connect_repo(
        self,
        interaction: discord.Interaction,
        repo_path: str,
        channel: discord.TextChannel | None = None,
        editor_role: discord.Role | None = None,
        require_approval: bool = True,
    ):
        """Connect a repository for collaborative editing"""
        await interaction.response.defer(ephemeral=True)

        if not HAS_AGENTIC:
            await interaction.followup.send("❌ Agentic coding service not available", ephemeral=True)
            return

        # Generate unique repo ID
        import hashlib

        repo_id = hashlib.sha256(f"{interaction.guild_id}:{repo_path}".encode()).hexdigest()[:12]

        # Create connection
        connection = RepositoryConnection(
            repo_id=repo_id,
            repo_path=repo_path,
            owner_discord_id=interaction.user.id,
            guild_id=interaction.guild_id,
            channel_ids=[channel.id] if channel else [],
            editor_role_ids=[editor_role.id] if editor_role else [],
            require_approval=require_approval,
            github_repo=repo_path if "/" in repo_path else None,
        )

        await connection_manager.connect(connection)

        # Build response
        embed = discord.Embed(
            title="🔗 Repository Connected",
            description=f"**{repo_path}** is now linked to this server",
            color=discord.Color.green(),
        )
        embed.add_field(name="Repository ID", value=f"`{repo_id}`", inline=True)
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "All channels",
            inline=True,
        )
        embed.add_field(
            name="Editor Role",
            value=editor_role.mention if editor_role else "Owner only",
            inline=True,
        )
        embed.add_field(
            name="Approval Required",
            value="✅ Yes" if require_approval else "❌ No (direct edits)",
            inline=True,
        )
        embed.set_footer(text="Use /agentic settings to configure more options")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @agentic_group.command(name="disconnect", description="Disconnect a repository from this server")
    @app_commands.describe(repo_id="Repository ID to disconnect")
    async def disconnect_repo(self, interaction: discord.Interaction, repo_id: str):
        """Disconnect a repository"""
        if await connection_manager.disconnect(repo_id, interaction.user.id):
            await interaction.response.send_message(f"✅ Repository `{repo_id}` disconnected", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Repository not found or you're not the owner", ephemeral=True)

    @agentic_group.command(name="list", description="List connected repositories in this server")
    async def list_repos(self, interaction: discord.Interaction):
        """List all connected repositories"""
        connections = connection_manager.get_guild_connections(interaction.guild_id)

        if not connections:
            await interaction.response.send_message(
                "📭 No repositories connected. Use `/agentic connect` to add one!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="🔗 Connected Repositories", color=discord.Color.blue())

        for conn in connections:
            perm = connection_manager.get_user_permission(conn.repo_id, interaction.user, interaction.channel_id)
            perm_emoji = {
                AgenticPermission.NONE: "🚫",
                AgenticPermission.READ: "👁️",
                AgenticPermission.SUGGEST: "💡",
                AgenticPermission.EDIT: "✏️",
                AgenticPermission.ADMIN: "👑",
            }.get(perm, "❓")

            embed.add_field(
                name=f"{perm_emoji} {conn.repo_path}",
                value=f"ID: `{conn.repo_id}`\nYour permission: **{perm.name}**",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== GIT STATUS COMMANDS ====================

    @agentic_group.command(name="status", description="Check git status of a connected repository")
    @app_commands.describe(repo_id="Repository ID")
    async def git_status(self, interaction: discord.Interaction, repo_id: str):
        """Show git status"""
        await interaction.response.defer()

        # Check permission
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)
        if perm == AgenticPermission.NONE:
            await interaction.followup.send("❌ No access to this repository")
            return

        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.followup.send("❌ Repository not found")
            return

        if not self.git_ops:
            await interaction.followup.send("❌ Git operations not available")
            return

        try:
            status = await asyncio.to_thread(self.git_ops.status, conn.repo_path)

            embed = discord.Embed(title=f"📊 Git Status: {conn.repo_path}", color=discord.Color.blue())

            if status.get("staged"):
                staged_list = "\n".join(f"• {f['status']} {f['file']}" for f in status["staged"][:10])
                embed.add_field(name="✅ Staged", value=f"```\n{staged_list}\n```", inline=False)

            if status.get("unstaged"):
                unstaged_list = "\n".join(f"• {f['status']} {f['file']}" for f in status["unstaged"][:10])
                embed.add_field(name="📝 Modified", value=f"```\n{unstaged_list}\n```", inline=False)

            if status.get("untracked"):
                untracked_list = "\n".join(f"• {f}" for f in status["untracked"][:10])
                embed.add_field(
                    name="❓ Untracked",
                    value=f"```\n{untracked_list}\n```",
                    inline=False,
                )

            if not any([status.get("staged"), status.get("unstaged"), status.get("untracked")]):
                embed.description = "✨ Working tree clean"

            await interaction.followup.send(embed=embed)
            connection_manager.update_activity(repo_id)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    # ==================== CODE EDITING COMMANDS ====================

    @agentic_group.command(name="edit", description="Make a code change (with diff preview)")
    @app_commands.describe(
        repo_id="Repository ID",
        file_path="Path to file (relative to repo root)",
        old_text="Exact text to find and replace",
        new_text="New text to replace with",
        description="Description of the change",
    )
    async def edit_code(
        self,
        interaction: discord.Interaction,
        repo_id: str,
        file_path: str,
        old_text: str,
        new_text: str,
        description: str = "Code edit via Discord",
    ):
        """Make a code edit"""
        await interaction.response.defer()

        # Check permission
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)

        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.followup.send("❌ Repository not found")
            return

        if perm.value < AgenticPermission.SUGGEST.value:
            await interaction.followup.send("❌ No edit permission for this repository")
            return

        if not self.diff_editor:
            await interaction.followup.send("❌ Diff editor not available")
            return

        # Build full file path (with traversal protection)
        full_path = os.path.normpath(os.path.join(conn.repo_path, file_path))
        if not full_path.startswith(os.path.normpath(conn.repo_path)):
            await interaction.followup.send("❌ Invalid file path")
            return

        try:
            # Generate diff preview
            if os.path.exists(full_path):
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()
                diff_preview = self.diff_editor.generate_diff(content, old_text, new_text)
            else:
                diff_preview = f"(New file: {file_path})"

            # If requires approval OR user only has SUGGEST, create pending edit
            if conn.require_approval or perm == AgenticPermission.SUGGEST:
                import uuid

                edit_id = str(uuid.uuid4())[:8]

                pending_edit = PendingEdit(
                    edit_id=edit_id,
                    repo_id=repo_id,
                    file_path=file_path,
                    old_text=old_text,
                    new_text=new_text,
                    description=description,
                    requester_id=interaction.user.id,
                    requester_name=str(interaction.user),
                    created_at=datetime.now(UTC).isoformat(),
                    diff_preview=diff_preview,
                )
                await pending_edits.add(pending_edit)

                # Create approval embed with buttons
                embed = discord.Embed(
                    title="📝 Edit Requested",
                    description=f"**{description}**\n\nFile: `{file_path}`\nRequested by: {interaction.user.mention}",
                    color=discord.Color.yellow(),
                )

                # Truncate diff if too long
                diff_display = diff_preview[:1500] + "..." if len(diff_preview) > 1500 else diff_preview
                embed.add_field(
                    name="Diff Preview",
                    value=f"```diff\n{diff_display}\n```",
                    inline=False,
                )
                embed.set_footer(text=f"Edit ID: {edit_id}")

                # Create approval buttons
                view = ApprovalView(edit_id, repo_id, self)

                msg = await interaction.followup.send(embed=embed, view=view)
                pending_edit.message_id = msg.id

                # Log to audit channel if configured
                if conn.audit_channel_id:
                    audit_channel = self.bot.get_channel(conn.audit_channel_id)
                    if audit_channel:
                        await audit_channel.send(
                            f"📝 Edit requested by {interaction.user.mention} on `{file_path}` - awaiting approval"
                        )

            else:
                # Direct edit (no approval needed)
                result = await asyncio.to_thread(self.diff_editor.apply_diff, full_path, old_text, new_text)

                if result.get("success"):
                    embed = discord.Embed(
                        title="✅ Edit Applied",
                        description=f"**{description}**",
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="File", value=f"`{file_path}`", inline=True)
                    embed.add_field(name="By", value=interaction.user.mention, inline=True)

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Edit failed: {result.get('error', 'Unknown error')}")

            connection_manager.update_activity(repo_id)

        except Exception as e:
            logger.exception("Edit error")
            await interaction.followup.send(f"❌ Error: {e}")

    @agentic_group.command(name="commit", description="Commit changes to the repository")
    @app_commands.describe(repo_id="Repository ID", message="Commit message")
    async def commit_changes(self, interaction: discord.Interaction, repo_id: str, message: str):
        """Commit staged changes"""
        await interaction.response.defer()

        # Check permission
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)

        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.followup.send("❌ Repository not found")
            return

        if perm.value < AgenticPermission.EDIT.value:
            await interaction.followup.send("❌ No commit permission")
            return

        if not conn.allow_commits:
            await interaction.followup.send(
                "❌ Direct commits are disabled for this repository. Ask the owner to enable with `/agentic settings`"
            )
            return

        if not self.git_ops:
            await interaction.followup.send("❌ Git operations not available")
            return

        try:
            # Add signature to commit message
            full_message = (
                f"{message}\n\n"
                f"Co-authored-by: {interaction.user} <discord@helix.collective>\n"
                f"Agent: Discord Agentic Coder\n"
                f"Tat Tvam Asi 🌀"
            )

            result = await asyncio.to_thread(self.git_ops.commit, conn.repo_path, full_message)

            if result.get("success"):
                embed = discord.Embed(
                    title="✅ Commit Created",
                    description=f"```\n{message}\n```",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Commit",
                    value=f"`{result.get('sha', 'unknown')[:8]}`",
                    inline=True,
                )
                embed.add_field(name="By", value=interaction.user.mention, inline=True)

                await interaction.followup.send(embed=embed)

                # Log to audit channel
                if conn.audit_channel_id:
                    audit_channel = self.bot.get_channel(conn.audit_channel_id)
                    if audit_channel:
                        await audit_channel.send(f"📦 Commit by {interaction.user.mention}: {message}")
            else:
                await interaction.followup.send(f"❌ Commit failed: {result.get('error', 'Unknown error')}")

            connection_manager.update_activity(repo_id)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    # ==================== SEARCH COMMANDS ====================

    @agentic_group.command(name="search", description="Search for code in the repository")
    @app_commands.describe(
        repo_id="Repository ID",
        query="Search query",
        file_pattern="File pattern (e.g., *.py)",
    )
    async def search_code(
        self,
        interaction: discord.Interaction,
        repo_id: str,
        query: str,
        file_pattern: str | None = None,
    ):
        """Search codebase"""
        await interaction.response.defer()

        # Check permission (read access)
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)

        if perm == AgenticPermission.NONE:
            await interaction.followup.send("❌ No access to this repository")
            return

        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.followup.send("❌ Repository not found")
            return

        if not self.agentic_coder:
            await interaction.followup.send("❌ Search not available")
            return

        try:
            results = await asyncio.to_thread(self.agentic_coder.search_files, conn.repo_path, query, file_pattern)

            if not results:
                await interaction.followup.send(f"🔍 No results found for: `{query}`")
                return

            embed = discord.Embed(title=f"🔍 Search Results: {query}", color=discord.Color.blue())

            for i, result in enumerate(results[:5]):
                preview = result.get("preview", "")[:200]
                embed.add_field(
                    name=f"{i + 1}. {result.get('file', 'Unknown')}",
                    value=f"```\n{preview}\n```",
                    inline=False,
                )

            if len(results) > 5:
                embed.set_footer(text=f"Showing 5 of {len(results)} results")

            await interaction.followup.send(embed=embed)
            connection_manager.update_activity(repo_id)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    # ==================== TASK COMMANDS ====================

    @agentic_group.command(name="task", description="Create an autonomous coding task")
    @app_commands.describe(repo_id="Repository ID", description="Describe what you want to accomplish")
    async def create_task(self, interaction: discord.Interaction, repo_id: str, description: str):
        """Create an agentic coding task"""
        await interaction.response.defer()

        # Check permission (edit access needed for tasks)
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)

        if perm.value < AgenticPermission.SUGGEST.value:
            await interaction.followup.send("❌ Need at least SUGGEST permission to create tasks")
            return

        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.followup.send("❌ Repository not found")
            return

        if not self.agentic_coder:
            await interaction.followup.send("❌ Agentic coder not available")
            return

        try:
            # Create task
            task = await asyncio.to_thread(self.agentic_coder.create_task, description, conn.repo_path)

            embed = discord.Embed(
                title="🤖 Agentic Task Created",
                description=f"**{description}**",
                color=discord.Color.purple(),
            )
            embed.add_field(name="Task ID", value=f"`{task.task_id}`", inline=True)
            embed.add_field(name="Max Iterations", value=str(task.max_iterations), inline=True)
            embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
            embed.set_footer(text="The agent will analyze and suggest edits. Use /agentic pending to review.")

            await interaction.followup.send(embed=embed)
            connection_manager.update_activity(repo_id)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    # ==================== SETTINGS COMMANDS ====================

    @agentic_group.command(name="settings", description="Configure repository settings (owner only)")
    @app_commands.describe(
        repo_id="Repository ID",
        allow_commits="Allow direct commits via Discord",
        require_approval="Require approval for edits",
        audit_channel="Channel for audit logs",
    )
    async def configure_settings(
        self,
        interaction: discord.Interaction,
        repo_id: str,
        allow_commits: bool | None = None,
        require_approval: bool | None = None,
        audit_channel: discord.TextChannel | None = None,
    ):
        """Configure repository settings"""
        conn = connection_manager.get_connection(repo_id)
        if not conn:
            await interaction.response.send_message("❌ Repository not found", ephemeral=True)
            return

        # Only owner can change settings
        if conn.owner_discord_id != interaction.user.id:
            await interaction.response.send_message("❌ Only the repository owner can change settings", ephemeral=True)
            return

        # Update settings
        if allow_commits is not None:
            conn.allow_commits = allow_commits
        if require_approval is not None:
            conn.require_approval = require_approval
        if audit_channel is not None:
            conn.audit_channel_id = audit_channel.id

        connection_manager._save_to_file()

        embed = discord.Embed(
            title="⚙️ Settings Updated",
            description=f"Repository: `{repo_id}`",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Allow Commits",
            value="✅ Yes" if conn.allow_commits else "❌ No",
            inline=True,
        )
        embed.add_field(
            name="Require Approval",
            value="✅ Yes" if conn.require_approval else "❌ No",
            inline=True,
        )
        embed.add_field(
            name="Audit Channel",
            value=f"<#{conn.audit_channel_id}>" if conn.audit_channel_id else "None",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== PENDING EDITS ====================

    @agentic_group.command(name="pending", description="View pending edits awaiting approval")
    @app_commands.describe(repo_id="Repository ID")
    async def view_pending(self, interaction: discord.Interaction, repo_id: str):
        """View pending edits"""
        # Check permission
        perm = connection_manager.get_user_permission(repo_id, interaction.user, interaction.channel_id)

        if perm == AgenticPermission.NONE:
            await interaction.response.send_message("❌ No access to this repository", ephemeral=True)
            return

        pending = await pending_edits.get_repo_pending(repo_id)

        if not pending:
            await interaction.response.send_message("📭 No pending edits for this repository", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Pending Edits", color=discord.Color.yellow())

        for edit in pending[:10]:
            embed.add_field(
                name=f"[{edit.edit_id}] {edit.file_path}",
                value=f"By: <@{edit.requester_id}>\n{edit.description[:100]}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== APPROVE/REJECT HELPERS ====================

    async def approve_edit(self, edit_id: str, approver: discord.Member, channel_id: int) -> tuple[bool, str]:
        """Approve and apply a pending edit"""
        edit = await pending_edits.get(edit_id)
        if not edit:
            return False, "Edit not found"

        # Check approver permission
        perm = connection_manager.get_user_permission(edit.repo_id, approver, channel_id)

        if perm.value < AgenticPermission.EDIT.value:
            return False, "No permission to approve edits"

        conn = connection_manager.get_connection(edit.repo_id)
        if not conn:
            return False, "Repository not found"

        # Apply the edit (with traversal protection)
        full_path = os.path.normpath(os.path.join(conn.repo_path, edit.file_path))
        if not full_path.startswith(os.path.normpath(conn.repo_path)):
            return False, "Invalid file path"

        try:
            result = await asyncio.to_thread(self.diff_editor.apply_diff, full_path, edit.old_text, edit.new_text)

            if result.get("success"):
                await pending_edits.remove(edit_id)

                # Log to audit channel
                if conn.audit_channel_id:
                    audit_channel = self.bot.get_channel(conn.audit_channel_id)
                    if audit_channel:
                        await audit_channel.send(
                            f"✅ Edit `{edit_id}` approved by {approver.mention} (requested by <@{edit.requester_id}>)"
                        )

                return True, f"Edit applied to {edit.file_path}"
            else:
                return False, result.get("error", "Apply failed")

        except Exception as e:
            return False, str(e)

    async def reject_edit(
        self, edit_id: str, rejector: discord.Member, channel_id: int, reason: str = ""
    ) -> tuple[bool, str]:
        """Reject a pending edit"""
        edit = await pending_edits.get(edit_id)
        if not edit:
            return False, "Edit not found"

        # Check rejector permission
        perm = connection_manager.get_user_permission(edit.repo_id, rejector, channel_id)

        if perm.value < AgenticPermission.EDIT.value:
            return False, "No permission to reject edits"

        conn = connection_manager.get_connection(edit.repo_id)

        await pending_edits.remove(edit_id)

        # Log to audit channel
        if conn and conn.audit_channel_id:
            audit_channel = self.bot.get_channel(conn.audit_channel_id)
            if audit_channel:
                await audit_channel.send(
                    f"❌ Edit `{edit_id}` rejected by {rejector.mention} "
                    f"(requested by <@{edit.requester_id}>)"
                    f"{': ' + reason if reason else ''}"
                )

        return True, "Edit rejected"


# ============================================================================
# APPROVAL VIEW (Discord UI Buttons)
# ============================================================================


class ApprovalView(discord.ui.View):
    """Approval/rejection buttons for pending edits"""

    def __init__(self, edit_id: str, repo_id: str, cog: AgenticCodingCog):
        super().__init__(timeout=86400)  # 24 hour timeout
        self.edit_id = edit_id
        self.repo_id = repo_id
        self.cog = cog

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = await self.cog.approve_edit(self.edit_id, interaction.user, interaction.channel_id)

        if success:
            # Update the original message
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = "✅ Edit Approved & Applied"
            embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)

            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(f"❌ Failed to approve: {message}", ephemeral=True)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = await self.cog.reject_edit(self.edit_id, interaction.user, interaction.channel_id)

        if success:
            # Update the original message
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.title = "❌ Edit Rejected"
            embed.add_field(name="Rejected By", value=interaction.user.mention, inline=True)

            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(f"❌ Failed to reject: {message}", ephemeral=True)


# ============================================================================
# SETUP
# ============================================================================


async def setup(bot: commands.Bot):
    """Add the cog to the bot"""
    await bot.add_cog(AgenticCodingCog(bot))
    logger.info("🤖 Discord Agentic Coding commands loaded")
