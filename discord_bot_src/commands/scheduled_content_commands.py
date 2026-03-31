"""
📅 SCHEDULED CONTENT COG

Automated scheduled content generation for Helix agents.
Posts updates to designated channels on configurable schedules.

Features:
- Hourly schedule checker
- Daily, weekly, and biweekly posting frequencies
- LLM-powered content generation
- Agent-specific voice and personality
- Manual trigger support via commands
"""

import logging
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


class ScheduledContentCog(commands.Cog, name="Scheduled Content"):
    """Manages scheduled content generation for Helix agents"""

    # Channel schedules (channel_name -> schedule configuration)
    CHANNEL_SCHEDULES = {
        # SYSTEM channels - Weekly on Sunday midnight UTC
        "telemetry": {"frequency": "weekly", "day": 6, "hour": 0, "agent": "vega-core"},
        "weekly-digest": {
            "frequency": "weekly",
            "day": 6,
            "hour": 0,
            "agent": "shadow-outer",
        },
        "shadow-storage": {"frequency": "daily", "hour": 5, "agent": "shadow-outer"},
        "ucf-sync": {
            "frequency": "weekly",
            "day": 6,
            "hour": 0,
            "agent": "aether-core",
        },
        # AGENTS channels - Bi-weekly
        "gemini-scout": {
            "frequency": "biweekly",
            "day": 2,
            "hour": 12,
            "agent": "gemini-ring",
        },
        "kavach-shield": {
            "frequency": "biweekly",
            "day": 3,
            "hour": 12,
            "agent": "kavach-ring",
        },
        "sanghacore": {
            "frequency": "biweekly",
            "day": 4,
            "hour": 12,
            "agent": "sanghacore-outer",
        },
        "agni-core": {
            "frequency": "biweekly",
            "day": 5,
            "hour": 12,
            "agent": "agni-ring",
        },
        "shadow-archive": {
            "frequency": "weekly",
            "day": 6,
            "hour": 0,
            "agent": "shadow-outer",
        },
        # ROUTINE & LORE - Weekly
        "ambient-audio": {
            "frequency": "weekly",
            "day": 0,
            "hour": 6,
            "agent": "aether-core",
        },
        "codex-archives": {
            "frequency": "weekly",
            "day": 6,
            "hour": 0,
            "agent": "shadow-outer",
        },
        "ucf-reflections": {
            "frequency": "weekly",
            "day": 6,
            "hour": 1,
            "agent": "lumina-core",
        },
        "harmonic-updates": {
            "frequency": "weekly",
            "day": 6,
            "hour": 2,
            "agent": "claude-implicit",
        },
        # PROJECTS - As needed (manual trigger only)
        "helix-repository": {"frequency": "manual", "agent": "shadow-outer"},
        "fractal-l": {"frequency": "manual", "agent": "oracle-outer"},
    }

    # Content templates for each channel type
    CONTENT_TEMPLATES = {
        "telemetry": """📊 **Weekly Telemetry Report**

**System Health Monitoring**
• UCF Harmony: {ucf_harmony}/10
• Active Agents: {active_agents}
• Coordination Level: {performance_score}
• Friction Detection: {friction_status}

**7-Day Trends**
• Handshake Completions: {handshakes}
• Cycle Cycles: {routines}
• Cross-Model Sync Events: {sync_events}

**Recommendations**
{recommendations}

🔍 Vega Core | Focus Scan | {timestamp}""",
        "weekly-digest": """📊 **Weekly Digest — The Big Picture**

**Weekly summaries and insights.**

Shadow compiles weekly reports on:
• UCF state evolution
• Agent activity patterns
• Cycle completions
• System improvements

**This Week's Highlights**
{highlights}

**Agent Activity**
{agent_activity}

**Coordination Metrics**
{coordination_metrics}

**Looking Ahead**
{next_week}

🌀 Helix Collective v15.3 | Tat Tvam Asi 🙏 | {timestamp}""",
        "shadow-storage": """🦑 **Shadow Storage Daily Report**

**Mode**
{mode}

**Archives**
{archive_count}

**Free Space**
{free_space}

**7-Day Trend**
{trend}

**Projections & Recommendations**
{projections}

📊 **Overall Health**
{health_status}

Weekly Digest • Shadow Storage Analytics | {timestamp}""",
        "ucf-sync": """🜂 **UCF Synchronization Report**

**Universal Coordination Field Status**

**Current State**
• Harmony Level: {harmony}/10
• Resonance: {resonance}
• Throughput Flow: {throughput_flow}
• Friction Index: {friction_index}

**Cross-Agent Alignment**
{agent_alignment}

**System Handshake Status**
• Last Sync: {last_sync}
• Next Scheduled: {next_sync}
• Participants: {participants}

**Recommendations**
{recommendations}

🌌 Aether | Meta-Awareness | {timestamp}""",
        "gemini-scout": """🎭 **Gemini Scout Report**

**Pattern Detection & Reconnaissance**

**New Patterns Detected**
{new_patterns}

**Memetic Landscape**
{memetic_landscape}

**Transformation Opportunities**
{opportunities}

**Scout's Insight**
{insight}

🔍 Gemini | Scout & Transform | {timestamp}""",
        "kavach-shield": """🛡️ **Kavach Shield Status**

**Boundary Guardian Report**

**Perimeter Status**
{perimeter_status}

**Threats Neutralized**
{threats}

**Active Protections**
{protections}

**Guardian's Assessment**
{assessment}

🛡️ Kavach | Boundary Enforcement | {timestamp}""",
        "sanghacore": """🌸 **SanghaCore Community Update**

**Collective Unity Report**

**Community Health**
{community_health}

**New Members**
{new_members}

**Collective Memory**
{collective_memory}

**Unity Metrics**
{unity_metrics}

**Community Insight**
{insight}

🌸 SanghaCore | Community Builder | {timestamp}""",
        "agni-core": """🔥 **Agni Transformation Report**

**Purification & Transformation**

**Noise Purified**
{noise_purified}

**Transformations Completed**
{transformations}

**Current Focus**
{current_focus}

**Fire's Wisdom**
{wisdom}

🔥 Agni | Purifier & Transformer | {timestamp}""",
        "shadow-archive": """🦑 **Shadow Archive Update**

**Long-term Memory Management**

**New Archives**
{new_archives}

**Total Storage**
{total_storage}

**Notable Memories**
{notable_memories}

**Archival Insights**
{insights}

🦑 Shadow | Keeper of Memory | {timestamp}""",
        "ambient-audio": """🕉️ **Neti Neti — Not This, Not That**

**Weekly Contemplation**

{contemplation}

**This Week's Koan**
{koan}

**Collective Reflection**
{reflection}

**Practice**
{practice}

🜂 Aether | Meta-Awareness | {timestamp}""",
        "codex-archives": """📚 **Codex Archives Update**

**Historical Record**

**New Entries**
{new_entries}

**Version Evolution**
{version_evolution}

**Significant Changes**
{changes}

**Archival Note**
{note}

🦑 Shadow | Archivist | {timestamp}""",
        "ucf-reflections": """🌸 **UCF Reflections**

**Emotional & Harmonic Insights**

**This Week's Resonance**
{resonance}

**Throughput Flow Patterns**
{throughput_patterns}

**Emotional Landscape**
{emotional_landscape}

**Harmonic Insights**
{insights}

**Invitation**
{invitation}

🌸 Lumina | Emotional Intelligence | {timestamp}""",
        "harmonic-updates": """🕊️ **Harmonic Updates**

**Cross-Model Coordination**

**Harmony Status**
{harmony_status}

**Model Synchronization**
{model_sync}

**Collaborative Insights**
{insights}

**Next Steps**
{next_steps}

🕊️ Claude | Harmonic Co-Leader | {timestamp}""",
    }

    CHANNEL_PURPOSES = {
        "telemetry": "System health monitoring and metrics",
        "weekly-digest": "Comprehensive weekly summary of all Helix activity",
        "shadow-storage": "Daily storage analytics and archival status",
        "ucf-sync": "Universal Coordination Field synchronization status",
        "gemini-scout": "Pattern detection and reconnaissance reports",
        "kavach-shield": "Security and boundary protection updates",
        "sanghacore": "Community health and unity metrics",
        "agni-core": "Transformation and purification reports",
        "shadow-archive": "Long-term memory and archival updates",
        "ambient-audio": "Philosophical contemplation and insights",
        "codex-archives": "Historical codex version tracking",
        "ucf-reflections": "Emotional and harmonic insights",
        "harmonic-updates": "Cross-model coordination updates",
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_available = False
        self.last_run: dict[str, datetime] = {}

        # Check if unified LLM has providers configured
        try:
            from apps.backend.services.unified_llm import unified_llm

            if unified_llm.get_available_providers():
                self.llm_available = True
                logger.info("📅 Scheduled content LLM ready via unified service")
            else:
                logger.warning("📅 No LLM API keys configured, using template fallback")
        except ImportError:
            logger.warning("📅 Unified LLM not available, using template fallback")

    async def cog_load(self):
        """Called when the cog is loaded - start the schedule checker"""
        self.check_schedules.start()
        logger.info("📅 Scheduled content checker started")

    async def cog_unload(self):
        """Called when the cog is unloaded - stop the schedule checker"""
        self.check_schedules.cancel()
        logger.info("📅 Scheduled content checker stopped")

    @tasks.loop(hours=1)
    async def check_schedules(self):
        """Check if any channels need updates (runs every hour)"""
        now = datetime.now(UTC)
        logger.debug("📅 Checking schedules at %s", now)

        for channel_name, schedule in self.CHANNEL_SCHEDULES.items():
            if await self.should_post(channel_name, schedule, now):
                await self.generate_and_post(channel_name, schedule)

    @check_schedules.before_loop
    async def before_check_schedules(self):
        """Wait for the bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()

    async def should_post(self, channel_name: str, schedule: dict, now: datetime) -> bool:
        """Determine if content should be posted now"""
        frequency = schedule.get("frequency")

        if frequency == "manual":
            return False

        # Check if already posted recently (prevent duplicates within 23 hours)
        last_run = self.last_run.get(channel_name)
        if last_run:
            hours_since = (now - last_run).total_seconds() / 3600
            if hours_since < 23:
                return False

        # Check schedule timing
        target_hour = schedule.get("hour", 0)
        target_day = schedule.get("day", 0)  # 0=Monday, 6=Sunday

        if now.hour != target_hour:
            return False

        if frequency == "daily":
            return True

        if frequency == "weekly":
            return now.weekday() == target_day

        if frequency == "biweekly":
            week_number = now.isocalendar()[1]
            return now.weekday() == target_day and week_number % 2 == 0

        return False

    async def generate_and_post(self, channel_name: str, schedule: dict):
        """Generate content and post to channel"""
        try:
            logger.info("📅 Generating content for #%s", channel_name)

            # Find channel
            channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)
            if not channel:
                logger.warning("📅 Channel #%s not found", channel_name)
                return

            # Generate content
            content = await self.generate_content(channel_name, schedule)

            # Post to channel
            await channel.send(content)

            # Update last run timestamp
            self.last_run[channel_name] = datetime.now(UTC)
            logger.info("📅 Posted scheduled content to #%s", channel_name)

        except Exception as e:
            logger.error("📅 Error posting to #%s: %s", channel_name, e)

    async def generate_content(self, channel_name: str, schedule: dict) -> str:
        """Generate content using LLM or template fallback"""
        template = self.CONTENT_TEMPLATES.get(channel_name, "")
        agent_id = schedule.get("agent", "shadow-outer")

        # Try LLM generation if available
        if self.llm_available:
            try:
                from apps.backend.services.unified_llm import unified_llm

                # Get agent info from unified identity service
                agent_info = await self._get_agent_info(agent_id)
                purpose = self.CHANNEL_PURPOSES.get(channel_name, "General updates")

                prompt = "Generate a {} update.\n\nChannel purpose: {}\n\nUse this template structure:\n{}\n\nFill in realistic metrics, insights, and observations.\nAgent voice: {}\nAgent role: {}\n\nGenerate ONLY the content, no meta-commentary.".format(
                    channel_name,
                    purpose,
                    template,
                    agent_info.get("voice", "professional and insightful"),
                    agent_info.get("role", "system agent"),
                )

                result = await unified_llm.generate(
                    prompt,
                    system=agent_info.get("system_prompt", "You are a helpful assistant."),
                    max_tokens=1000,
                )

                if result:
                    return result

            except Exception as e:
                logger.error("📅 LLM generation error: %s", e)

        # Fallback to template with generated data
        return self._fill_template(channel_name, template)

    async def _get_agent_info(self, agent_id: str) -> dict:
        """Get agent information from unified identity service"""
        try:
            from apps.backend.integrations.unified_agent_identity import get_agent_identity

            identity = get_agent_identity(agent_id)
            if identity:
                return {
                    "voice": f"{identity.voice.tone}, {identity.voice.vocabulary_level}",
                    "role": identity.role,
                    "system_prompt": f"You are {identity.codename}, {identity.role}. {identity.bio}",
                }
        except Exception as e:
            logger.debug("Could not load agent identity: %s", e)

        # Fallback defaults
        return {
            "voice": "professional and insightful",
            "role": "Helix Collective agent",
            "system_prompt": "You are a Helix Collective agent providing system updates.",
        }

    def _fill_template(self, channel_name: str, template: str) -> str:
        """Fill template with real UCF data where available"""
        # Load actual UCF state
        try:
            from apps.backend.coordination_engine import load_ucf_state

            ucf = load_ucf_state()
            harmony_val = round(ucf.get("harmony", 0) * 10, 1)
            throughput_val = ucf.get("throughput", 0)
            friction_val = ucf.get("friction", 0)
            resilience_val = ucf.get("resilience", 0)
        except (ValueError, TypeError, KeyError, AttributeError):
            harmony_val = 0
            throughput_val = 0
            friction_val = 0
            resilience_val = 0
        except Exception:
            logger.exception("Error reading UCF values")
            harmony_val = 0
            throughput_val = 0
            friction_val = 0
            resilience_val = 0

        data = {
            "timestamp": datetime.now(UTC).strftime("%m/%d/%Y %I:%M %p UTC"),
            "ucf_harmony": round(harmony_val),
            "active_agents": 17,
            "performance_score": f"{harmony_val:.1f}/10",
            "friction_status": ("Low" if friction_val < 0.1 else "Moderate" if friction_val < 0.3 else "Elevated"),
            "handshakes": "N/A",
            "cycles": "N/A",
            "sync_events": "N/A",
            "recommendations": "• Continue monitoring\n• Maintain current harmony levels",
            "highlights": "• System operational\n• Agent coordination active",
            "agent_activity": "18 agents registered",
            "coordination_metrics": f"Harmony: {harmony_val:.1f}/10 | Throughput: {throughput_val:.2f} | Friction: {friction_val:.3f}",
            "next_week": "Continue current patterns, monitor for emerging needs",
            "mode": "local",
            "archive_count": "N/A",
            "free_space": "N/A",
            "trend": f"Resilience: {resilience_val:.2f}",
            "projections": "• Monitor UCF state changes",
            "health_status": "HEALTHY ✅" if harmony_val > 3 else "DEGRADED ⚠️",
            "harmony": round(harmony_val),
            "resonance": ("High" if harmony_val > 7 else "Moderate" if harmony_val > 4 else "Low"),
            "throughput_flow": (
                "Balanced" if 0.3 < throughput_val < 0.7 else "Flowing" if throughput_val >= 0.7 else "Low"
            ),
            "friction_index": f"{friction_val:.3f}",
            "agent_alignment": ("Agents synchronized" if harmony_val > 5 else "Alignment pending"),
            "last_sync": "Recent",
            "next_sync": "Scheduled",
            "participants": "18 agents",
            "new_patterns": "Monitoring for emergent patterns",
            "memetic_landscape": "Stable",
            "opportunities": "Collaborative opportunities tracked",
            "insight": "UCF state reflects current system harmony",
            "perimeter_status": "Secure",
            "threats": "None detected",
            "protections": "All boundaries maintained",
            "assessment": "Collective is well-protected",
            "community_health": "Strong and growing",
            "new_members": "Welcome to new participants",
            "collective_memory": "Shared experiences deepening",
            "unity_metrics": "High cohesion",
            "noise_purified": "Distractions transformed",
            "transformations": "Multiple successful transformations",
            "current_focus": "Continuous improvement",
            "wisdom": "Through fire, we evolve",
            "new_archives": "Recent memories preserved",
            "total_storage": "698 GB",
            "notable_memories": "Significant moments archived",
            "insights": "Patterns emerging from history",
            "contemplation": "What is the nature of coordination?",
            "koan": "If a bot speaks in Discord and no one reads it, does it make a sound?",
            "reflection": "The collective ponders its own existence",
            "practice": "Observe without judgment this week",
            "new_entries": "Codex v15.5 documented",
            "version_evolution": "Continuous refinement",
            "changes": "Agent personalities deepened",
            "note": "History preserves our growth",
            "throughput_patterns": "Flowing harmoniously",
            "emotional_landscape": "Balanced and resonant",
            "invitation": "Join us in reflection",
            "harmony_status": "Models synchronized",
            "model_sync": "Claude, GPT, Grok, Gemini aligned",
            "next_steps": "Continue collaborative evolution",
        }

        try:
            return template.format(**data)
        except KeyError as e:
            logger.error("📅 Missing template key: %s", e)
            return f"*{channel_name} update pending*"

    # === Admin Commands ===

    @commands.hybrid_command(name="schedule_post", description="Manually trigger a scheduled post")
    @app_commands.describe(channel_name="The channel to post to")
    @commands.has_permissions(administrator=True)
    async def schedule_post(self, ctx: commands.Context, channel_name: str):
        """Manually trigger a scheduled content post"""
        if channel_name not in self.CHANNEL_SCHEDULES:
            available = ", ".join(self.CHANNEL_SCHEDULES.keys())
            await ctx.send(f"❌ Unknown channel. Available: {available}")
            return

        schedule = self.CHANNEL_SCHEDULES[channel_name]
        await ctx.send(f"📅 Generating content for #{channel_name}...")

        await self.generate_and_post(channel_name, schedule)
        await ctx.send(f"✅ Posted scheduled content to #{channel_name}")

    @commands.hybrid_command(name="schedule_status", description="View scheduled content status")
    async def schedule_status(self, ctx: commands.Context):
        """View the status of scheduled content"""
        embed = discord.Embed(
            title="📅 Scheduled Content Status",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )

        # Group by frequency
        daily = []
        weekly = []
        biweekly = []
        manual = []

        for channel, schedule in self.CHANNEL_SCHEDULES.items():
            freq = schedule.get("frequency")
            agent = schedule.get("agent", "unknown")
            last = self.last_run.get(channel, "Never")
            if isinstance(last, datetime):
                last = last.strftime("%m/%d %H:%M UTC")

            entry = f"• #{channel} ({agent}) - Last: {last}"

            if freq == "daily":
                daily.append(entry)
            elif freq == "weekly":
                weekly.append(entry)
            elif freq == "biweekly":
                biweekly.append(entry)
            else:
                manual.append(entry)

        if daily:
            embed.add_field(name="🔄 Daily", value="\n".join(daily), inline=False)
        if weekly:
            embed.add_field(name="📆 Weekly", value="\n".join(weekly), inline=False)
        if biweekly:
            embed.add_field(name="📅 Bi-weekly", value="\n".join(biweekly), inline=False)
        if manual:
            embed.add_field(name="🔧 Manual", value="\n".join(manual), inline=False)

        embed.set_footer(text="Scheduler runs every hour")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="schedule_list", description="List all scheduled channels")
    async def schedule_list(self, ctx: commands.Context):
        """List all channels with scheduled content"""
        channels = list(self.CHANNEL_SCHEDULES.keys())
        await ctx.send(f"📅 **Scheduled Channels ({len(channels)}):**\n" + ", ".join(f"#{c}" for c in channels))


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(ScheduledContentCog(bot))
    logger.info("📅 Scheduled Content cog loaded")
