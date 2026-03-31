"""
🧠 Helix Agent Persistent Memory Service
apps/backend/discord/agent_memory_service.py

Replaces the ephemeral in-memory agent memory with a DB-backed system
that persists across restarts and enables cross-platform continuity.

Features:
- Per-user conversation threads (each user gets their own context per agent)
- Forum memory integration (agents remember forum posts/discussions)
- Persistent agent memories with relevance scoring
- Automatic memory summarization for efficient context windows
- Cross-platform memory (Discord ↔ Web ↔ Forum)
- User LLM preference management

Version: 17.3.0
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from apps.backend.db_models import AgentMemoryEntry, DiscordConversation, DiscordMessage

logger = logging.getLogger(__name__)


# ============================================================================
# PERSISTENT MEMORY SERVICE
# ============================================================================


class AgentPersistentMemory:
    """
    DB-backed memory service for Helix agents.

    Manages:
    - AgentMemoryEntry: Long-term knowledge (facts, forum posts, insights)
    - DiscordConversation: Per-user conversation threads
    - DiscordMessage: Individual messages within conversations
    - UserLLMPreference: Per-user model selection
    """

    # Maximum messages in context window (recent + relevant)
    MAX_CONTEXT_MESSAGES = 20
    # Maximum long-term memories to inject into system prompt
    MAX_MEMORY_CONTEXT = 5
    # Minimum coordination score to persist as long-term memory
    MIN_PERSIST_SCORE = 3.0

    # ------------------------------------------------------------------
    # CONVERSATION MANAGEMENT (per-user, per-agent threads)
    # ------------------------------------------------------------------

    async def get_or_create_conversation(
        self,
        db: AsyncSession,
        discord_user_id: str,
        agent_name: str,
        channel_id: str | None = None,
        guild_id: str | None = None,
    ) -> "DiscordConversation":
        """Get the active conversation for a user+agent pair, or create one."""
        from apps.backend.db_models import DiscordConversation

        result = await db.execute(
            select(DiscordConversation)
            .where(
                DiscordConversation.discord_user_id == discord_user_id,
                DiscordConversation.agent_name == agent_name,
                DiscordConversation.is_active.is_(True),
            )
            .order_by(desc(DiscordConversation.last_message_at))
            .limit(1)
        )
        conv = result.scalar_one_or_none()

        if conv is None:
            conv = DiscordConversation(
                id=str(uuid.uuid4()),
                discord_user_id=discord_user_id,
                agent_name=agent_name,
                channel_id=channel_id,
                guild_id=guild_id,
                message_count=0,
                last_message_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
                is_active=True,
            )
            db.add(conv)
            await db.flush()
            logger.info(
                "📝 Created new conversation for user %s with %s",
                discord_user_id,
                agent_name,
            )

        return conv

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
        agent_name: str | None = None,
        model_used: str | None = None,
        tokens_used: int | None = None,
        ucf_metrics: dict | None = None,
    ) -> "DiscordMessage":
        """Add a message to a conversation and update conversation metadata."""
        from apps.backend.db_models import DiscordConversation, DiscordMessage

        msg = DiscordMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_name=agent_name,
            model_used=model_used,
            tokens_used=tokens_used,
            ucf_metrics=ucf_metrics,
            created_at=datetime.now(UTC),
        )
        db.add(msg)

        # Update conversation metadata
        await db.execute(
            update(DiscordConversation)
            .where(DiscordConversation.id == conversation_id)
            .values(
                message_count=DiscordConversation.message_count + 1,
                last_message_at=datetime.now(UTC),
            )
        )
        await db.flush()
        return msg

    async def get_conversation_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        """Get recent messages from a conversation formatted for LLM context."""
        from apps.backend.db_models import DiscordMessage

        result = await db.execute(
            select(DiscordMessage)
            .where(DiscordMessage.conversation_id == conversation_id)
            .order_by(desc(DiscordMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()

        # Reverse to chronological order
        return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]

    async def reset_conversation(
        self,
        db: AsyncSession,
        discord_user_id: str,
        agent_name: str,
    ) -> bool:
        """Archive the active conversation and allow a fresh start."""
        from apps.backend.db_models import DiscordConversation

        result = await db.execute(
            update(DiscordConversation)
            .where(
                DiscordConversation.discord_user_id == discord_user_id,
                DiscordConversation.agent_name == agent_name,
                DiscordConversation.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await db.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # LONG-TERM MEMORY (facts, forum knowledge, insights)
    # ------------------------------------------------------------------

    async def store_memory(
        self,
        db: AsyncSession,
        agent_name: str,
        content: str,
        memory_type: str = "conversation",
        platform: str = "discord",
        source_id: str | None = None,
        user_id: str | None = None,
        discord_user_id: str | None = None,
        coordination_score: float = 5.0,
        summary: str | None = None,
        metadata: dict | None = None,
    ) -> "AgentMemoryEntry":
        """Store a long-term memory entry for an agent."""
        from apps.backend.db_models import AgentMemoryEntry

        entry = AgentMemoryEntry(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            summary=summary,
            platform=platform,
            source_id=source_id,
            user_id=user_id,
            discord_user_id=discord_user_id,
            coordination_score=coordination_score,
            metadata_json=metadata,
            created_at=datetime.now(UTC),
        )
        db.add(entry)
        await db.flush()
        return entry

    async def store_forum_memory(
        self,
        db: AsyncSession,
        agent_name: str,
        post_title: str,
        post_content: str,
        agent_response: str,
        post_id: str,
        coordination_score: float = 5.0,
    ) -> "AgentMemoryEntry":
        """Store a forum interaction as agent memory.

        This gives agents continuity — they remember forum discussions
        and can reference them in Discord conversations.
        """
        summary = f"Forum post: '{post_title[:100]}' — I responded about {post_content[:80]}"
        content = f"Forum Discussion: {post_title}\n\nUser's Post:\n{post_content[:500]}\n\nMy Response:\n{agent_response[:500]}"

        return await self.store_memory(
            db=db,
            agent_name=agent_name,
            content=content,
            memory_type="forum",
            platform="forum",
            source_id=post_id,
            coordination_score=coordination_score,
            summary=summary,
            metadata={"post_title": post_title, "post_id": post_id},
        )

    async def get_relevant_memories(
        self,
        db: AsyncSession,
        agent_name: str,
        limit: int = 5,
        memory_types: list[str] | None = None,
        platform: str | None = None,
        discord_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant long-term memories for context injection.

        Orders by coordination_score (importance) then recency.
        Can filter by memory type, platform, and user.
        """
        from apps.backend.db_models import AgentMemoryEntry

        query = select(AgentMemoryEntry).where(AgentMemoryEntry.agent_name == agent_name)

        if memory_types:
            query = query.where(AgentMemoryEntry.memory_type.in_(memory_types))
        if platform:
            query = query.where(AgentMemoryEntry.platform == platform)
        if discord_user_id:
            query = query.where(
                (AgentMemoryEntry.discord_user_id == discord_user_id) | (AgentMemoryEntry.discord_user_id.is_(None))
            )

        # Filter expired memories
        now = datetime.now(UTC)
        query = query.where((AgentMemoryEntry.expires_at.is_(None)) | (AgentMemoryEntry.expires_at > now))

        query = query.order_by(
            desc(AgentMemoryEntry.coordination_score),
            desc(AgentMemoryEntry.created_at),
        ).limit(limit)

        result = await db.execute(query)
        entries = result.scalars().all()

        return [
            {
                "type": e.memory_type,
                "summary": e.summary or e.content[:200],
                "content": e.content,
                "platform": e.platform,
                "score": e.coordination_score,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    async def get_memory_count(
        self,
        db: AsyncSession,
        agent_name: str,
    ) -> int:
        """Count total memories for an agent."""
        from sqlalchemy import func

        from apps.backend.db_models import AgentMemoryEntry

        result = await db.execute(
            select(func.count(AgentMemoryEntry.id)).where(AgentMemoryEntry.agent_name == agent_name)
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # USER LLM PREFERENCES
    # ------------------------------------------------------------------

    async def get_user_llm_prefs(
        self,
        db: AsyncSession,
        discord_user_id: str,
    ) -> dict[str, Any] | None:
        """Get a user's LLM preferences."""
        from apps.backend.db_models import UserLLMPreference

        result = await db.execute(select(UserLLMPreference).where(UserLLMPreference.discord_user_id == discord_user_id))
        pref = result.scalar_one_or_none()
        if pref is None:
            return None

        return {
            "provider": pref.preferred_provider,
            "model": pref.preferred_model,
            "temperature": pref.temperature,
            "max_tokens": pref.max_tokens,
            "system_prompt_override": pref.system_prompt_override,
        }

    async def set_user_llm_prefs(
        self,
        db: AsyncSession,
        discord_user_id: str,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt_override: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Set or update a user's LLM preferences."""
        from apps.backend.db_models import UserLLMPreference

        result = await db.execute(select(UserLLMPreference).where(UserLLMPreference.discord_user_id == discord_user_id))
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = UserLLMPreference(
                id=str(uuid.uuid4()),
                discord_user_id=discord_user_id,
                user_id=user_id,
                preferred_provider=provider,
                preferred_model=model,
                temperature=temperature or 0.7,
                max_tokens=max_tokens or 2048,
                system_prompt_override=system_prompt_override,
                updated_at=datetime.now(UTC),
            )
            db.add(pref)
        else:
            if provider is not None:
                pref.preferred_provider = provider
            if model is not None:
                pref.preferred_model = model
            if temperature is not None:
                pref.temperature = temperature
            if max_tokens is not None:
                pref.max_tokens = max_tokens
            if system_prompt_override is not None:
                pref.system_prompt_override = system_prompt_override
            pref.updated_at = datetime.now(UTC)

        await db.commit()

        return {
            "provider": pref.preferred_provider,
            "model": pref.preferred_model,
            "temperature": pref.temperature,
            "max_tokens": pref.max_tokens,
        }

    # ------------------------------------------------------------------
    # CONTEXT BUILDER — assemble the full context for an LLM call
    # ------------------------------------------------------------------

    async def _get_linked_web_memories(
        self,
        db: AsyncSession,
        discord_user_id: str,
        agent_name: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Fetch web-platform memories for a user who has linked their Helix account.

        Queries the agent_memories table (used by web copilot) using the linked
        user_id resolved from discord_id → User.id.  Returns an empty list if the
        account is not linked or the query fails.
        """
        from sqlalchemy import text

        try:
            # Resolve discord_id → web user_id
            from apps.backend.db_models import User

            user_result = await db.execute(select(User).where(User.discord_id == discord_user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return []

            web_agent_id = f"{user.id}:{agent_name}"
            rows = await db.execute(
                text(
                    """
                    SELECT summary, content, source_platform, importance
                    FROM agent_memories
                    WHERE agent_id = :agent_id
                      AND source_platform != 'discord'
                      AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY importance DESC, created_at DESC
                    LIMIT :lim
                    """
                ),
                {"agent_id": web_agent_id, "lim": limit},
            )
            web_mems = []
            for row in rows.fetchall():
                web_mems.append(
                    {
                        "summary": row[0] or row[1][:120],
                        "platform": row[2],
                        "importance": float(row[3] or 0.5),
                    }
                )
            return web_mems
        except Exception as e:
            logger.debug("Cross-platform memory bridge failed (non-critical): %s", e)
            return []

    async def build_agent_context(
        self,
        db: AsyncSession,
        agent_name: str,
        discord_user_id: str,
        current_message: str,
        system_message: str,
        channel_id: str | None = None,
        guild_id: str | None = None,
        raw_discord_user_id: str | None = None,
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        """
        Build a rich context for an LLM call, combining:
        1. Agent system message (personality, ethics, capabilities)
        2. Long-term memories (forum posts, learned facts, past insights)
        3. Cross-platform memories from linked web account (if any)
        4. Per-user conversation history (last N messages)
        5. Current message

        Args:
            discord_user_id: Guild-scoped namespace key (e.g. "{guild_id}:{user_id}" or
                             "dm:{user_id}") used for conversation + memory isolation.
            raw_discord_user_id: The raw Discord snowflake ID used only for account-
                                 linking lookups. If None, falls back to discord_user_id.

        Returns:
            Tuple of (messages_list, metadata_dict)
            messages_list: Ready for LLM chat API
            metadata_dict: Contains conversation_id, user prefs, etc.
        """
        # raw_discord_user_id is used only for account-linking; defaults to discord_user_id
        # for DM contexts where they are the same value.
        link_user_id = raw_discord_user_id or discord_user_id

        # 1. Get or create the conversation thread
        conv = await self.get_or_create_conversation(db, discord_user_id, agent_name, channel_id, guild_id)

        # 2. Get user LLM preferences (keyed by raw discord_user_id for cross-guild consistency)
        prefs = await self.get_user_llm_prefs(db, link_user_id)

        # 3. Get long-term memories (Discord platform) — scoped by context key
        memories = await self.get_relevant_memories(
            db,
            agent_name,
            limit=self.MAX_MEMORY_CONTEXT,
            discord_user_id=discord_user_id,
        )

        # 3b. Get cross-platform web memories if account is linked (uses raw discord ID)
        web_memories = await self._get_linked_web_memories(db, link_user_id, agent_name)

        # 4. Augment system message with memories
        augmented_system = system_message
        all_memories = list(memories)
        if all_memories or web_memories:
            memory_block = "\n\n--- PERSISTENT MEMORY ---\n"
            memory_block += "You have the following relevant memories:\n"
            for i, mem in enumerate(all_memories, 1):
                memory_block += f"\n{i}. [{mem['type']}/{mem['platform']}] {mem['summary']}"
            if web_memories:
                memory_block += "\n\nFrom the user's linked web account:\n"
                for j, wmem in enumerate(web_memories, 1):
                    memory_block += f"\nW{j}. [{wmem['platform']}] {wmem['summary']}"
            memory_block += "\n\nUse these memories naturally in conversation. "
            memory_block += "Don't list them — weave them in when relevant.\n"
            memory_block += "--- END MEMORY ---\n"
            augmented_system += memory_block

        # Add user's custom system prompt if set
        if prefs and prefs.get("system_prompt_override"):
            augmented_system += f"\n\nUser's custom instructions: {prefs['system_prompt_override']}"

        # 5. Build messages list
        messages = [{"role": "system", "content": augmented_system}]

        # 6. Add conversation history
        history = await self.get_conversation_messages(db, conv.id, limit=self.MAX_CONTEXT_MESSAGES)
        messages.extend(history)

        # 7. Add current message
        messages.append({"role": "user", "content": current_message})

        # 8. Store the user's message
        await self.add_message(
            db,
            conv.id,
            "user",
            current_message,
        )
        await db.commit()

        metadata = {
            "conversation_id": conv.id,
            "user_prefs": prefs,
            "memory_count": len(memories),
            "web_memory_count": len(web_memories),
            "history_length": len(history),
        }

        return messages, metadata

    async def store_response(
        self,
        db: AsyncSession,
        conversation_id: str,
        agent_name: str,
        response: str,
        model_used: str | None = None,
        tokens_used: int | None = None,
        ucf_metrics: dict | None = None,
    ) -> None:
        """Store the agent's response and optionally create a long-term memory."""
        await self.add_message(
            db,
            conversation_id,
            "assistant",
            response,
            agent_name=agent_name,
            model_used=model_used,
            tokens_used=tokens_used,
            ucf_metrics=ucf_metrics,
        )
        await db.commit()


# Singleton
_memory_service: AgentPersistentMemory | None = None


def get_agent_memory() -> AgentPersistentMemory:
    """Get the singleton AgentPersistentMemory instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = AgentPersistentMemory()
    return _memory_service
