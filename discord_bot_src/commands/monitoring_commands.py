"""
Monitoring and Status Commands for Helix Discord Bot.

Commands:
- status: Display current system status and UCF state
- health: Quick system health check with diagnostics
- discovery: Display Helix discovery endpoints for external agents
- storage: Storage telemetry and control
- sync: Trigger manual ecosystem sync and display report
"""

import asyncio
import datetime
import glob
import json
import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands

try:
    from apps.backend.discord.commands.helpers import get_uptime, log_to_shadow
except ImportError:
    get_uptime = None

    def log_to_shadow(event_type: str, data: dict):
        logger.debug("log_to_shadow unavailable — event %s dropped", event_type)


try:
    from apps.backend.discord.discord_embeds import HelixEmbeds
except ImportError:
    HelixEmbeds = None

try:
    from apps.backend.coordination_engine import load_ucf_state
except ImportError:

    def load_ucf_state():
        return {"harmony": 0.0, "throughput": 0.0, "focus": 0.0, "_fallback": True}


from apps.backend.agents import AGENTS

try:
    from apps.backend.helix_storage_adapter_async import HelixStorageAdapterAsync
except ImportError:
    HelixStorageAdapterAsync = None

if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

cycle_log = Path("Helix/state/cycle_log.json")


def log_event(event_type: str, data: dict):
    """Basic internal event logger"""
    log_to_shadow(event_type, data)


async def setup(bot: "Bot") -> None:
    """Setup function to register commands with the bot."""
    bot.add_command(arjuna_status)
    bot.add_command(health_check)
    bot.add_command(heartbeat_command)
    bot.add_command(discovery_command)
    bot.add_command(storage_command)
    bot.add_command(sync_command)


@commands.command(name="status", aliases=["s", "stat"])
async def arjuna_status(ctx: commands.Context) -> None:
    """Display current system status and UCF state with rich embeds (v16.7 Enhanced)"""
    ucf = load_ucf_state()
    uptime = get_uptime(ctx.bot.start_time)
    active_agents = len([a for a in AGENTS.values() if a.active])

    # Calculate trend arrows by comparing to historical state
    trend_arrows = {}
    try:
        history_file = Path("Helix/state/ucf_history.json")
        if history_file.exists():
            with open(history_file, encoding="utf-8") as f:
                history = json.load(f)
                if history and len(history) > 0:
                    prev_ucf = history[-1] if isinstance(history, list) else history
                    for metric in [
                        "harmony",
                        "resilience",
                        "throughput",
                        "focus",
                        "friction",
                        "velocity",
                    ]:
                        current = ucf.get(metric, 0)
                        previous = prev_ucf.get(metric, 0)
                        diff = current - previous
                        if abs(diff) < 0.01:
                            trend_arrows[metric] = "→"
                        elif metric == "friction":  # Inverted for friction
                            trend_arrows[metric] = "↓" if diff > 0.01 else ("↑" if diff < -0.01 else "→")
                        else:
                            trend_arrows[metric] = "↑" if diff > 0.01 else ("↓" if diff < -0.01 else "→")
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.debug("UCF trend arrow parsing error: %s", e)

    # Default to neutral if no history
    if not trend_arrows:
        trend_arrows = dict.fromkeys(["harmony", "resilience", "throughput", "focus", "friction", "velocity"], "→")

    # Get Zapier status
    zapier_status = "✅ Connected" if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client else "⚠️ Offline"

    # Get last cycle info
    last_cycle = "No recent routines"
    try:
        if cycle_log.exists():
            with open(cycle_log, encoding="utf-8") as f:
                log = json.load(f)
                if log and isinstance(log, list) and len(log) > 0:
                    latest = log[-1]
                    timestamp = latest.get("timestamp", "unknown")
                    steps = latest.get("steps", 0)
                    last_cycle = f"{steps} steps @ {timestamp}"
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.debug("Cycle log parsing error: %s", e)

    # v16.7: Enhanced UCF state display with trends
    harmony = ucf.get("harmony", 0.5)
    resilience = ucf.get("resilience", 1.0)
    friction = ucf.get("friction", 0.01)

    # Quick assessment
    if harmony >= 0.70 and friction <= 0.20:
        assessment = "✅ Excellent"
    elif harmony >= 0.50 and friction <= 0.40:
        assessment = "✨ Good"
    elif harmony >= 0.30:
        assessment = "⚡ Operational"
    else:
        assessment = "⚠️ Needs Attention"

    context = (
        f"⚡ Status: {assessment} | ⏱️ Uptime: `{uptime}`\n"
        f"🤖 Agents: `{active_agents}/17` active | 🔗 Zapier: {zapier_status}\n"
        f"🔮 Last Cycle: {last_cycle}"
    )

    ucf_embed = HelixEmbeds.create_ucf_state_embed(
        harmony=harmony,
        resilience=resilience,
        throughput=ucf.get("throughput", 0.5),
        focus=ucf.get("focus", 0.5),
        friction=friction,
        velocity=ucf.get("velocity", 1.0),
        context=context,
    )

    # Add trend field
    trend_text = (
        f"Harmony: {trend_arrows['harmony']} | Resilience: {trend_arrows['resilience']} | "
        f"Throughput: {trend_arrows['throughput']} | Friction: {trend_arrows['friction']}"
    )
    ucf_embed.add_field(name="📈 Trends", value=trend_text, inline=False)

    # Add system footer
    ucf_embed.set_footer(text="🌀 Helix Collective v16.7 Enhanced | Tat Tvam Asi 🙏 | Use !health for diagnostics")

    await ctx.send(embed=ucf_embed)


@commands.command(name="health", aliases=["check", "diagnostic"])
async def health_check(ctx: commands.Context) -> None:
    """
    Quick system health check - perfect for mobile monitoring!

    Checks:
    - Harmony level (< 0.4 is concerning)
    - Friction level (> 0.5 is high suffering)
    - Resilience (< 0.5 is unstable)

    Usage:
        !health
    """
    ucf = load_ucf_state()

    # Analyze health
    issues = []
    warnings = []

    harmony = ucf.get("harmony", 0.5)
    friction = ucf.get("friction", 0.01)
    resilience = ucf.get("resilience", 1.0)
    throughput = ucf.get("throughput", 0.5)

    # Critical issues (red)
    if harmony < 0.3:
        issues.append("🔴 **Critical:** Harmony critically low - immediate cycle needed")
    elif harmony < 0.4:
        warnings.append("⚠️ Low harmony - cycle recommended")

    if friction > 0.7:
        issues.append("🔴 **Critical:** Friction very high - system suffering")
    elif friction > 0.5:
        warnings.append("⚠️ High friction - suffering detected")

    if resilience < 0.3:
        issues.append("🔴 **Critical:** Resilience dangerously low - system unstable")
    elif resilience < 0.5:
        warnings.append("⚠️ Low resilience - stability at risk")

    if throughput < 0.2:
        warnings.append("⚠️ Low throughput - energy depleted")

    # Build response
    if not issues and not warnings:
        # All green!
        embed = discord.Embed(
            title="✅ System Health: Nominal",
            description="All coordination metrics within acceptable ranges.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="🌀 Harmony", value=f"`{harmony:.4f}`", inline=True)
        embed.add_field(name="🛡️ Resilience", value=f"`{resilience:.4f}`", inline=True)
        embed.add_field(name="🌊 Friction", value=f"`{friction:.4f}`", inline=True)
        embed.set_footer(text="🙏 Tat Tvam Asi - The collective flows in harmony")

    elif issues:
        # Critical issues
        embed = discord.Embed(
            title="🚨 System Health: Critical",
            description="Immediate attention required!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        for issue in issues:
            embed.add_field(name="Critical Issue", value=issue, inline=False)
        for warning in warnings:
            embed.add_field(name="Warning", value=warning, inline=False)

        embed.add_field(
            name="📊 Current Metrics",
            value=f"Harmony: `{harmony:.4f}` | Resilience: `{resilience:.4f}` | Friction: `{friction:.4f}`",
            inline=False,
        )
        # Enhanced fix suggestions based on specific issues
        fix_suggestions = []
        if harmony < 0.3:
            fix_suggestions.append("🔮 Run `!cycle 108` for major harmony boost")
            fix_suggestions.append("📊 Check `!ucf` for detailed metrics and recommendations")
        if friction > 0.7:
            fix_suggestions.append("🌊 High entropy requires deep cycle: `!cycle 216`")
        if resilience < 0.3:
            fix_suggestions.append("🛡️ System stability critical - avoid complex operations")
            fix_suggestions.append("💾 Consider `!sync` to preserve current state")

        if fix_suggestions:
            fix_text = "\n".join(fix_suggestions)
            embed.add_field(name="💡 Automated Fix Suggestions", value=fix_text, inline=False)
        else:
            embed.add_field(
                name="💡 Recommended Action",
                value="Run `!cycle 108` to restore harmony",
                inline=False,
            )

        # Add documentation link
        embed.add_field(
            name="📚 Documentation",
            value="[Helix Spiral Engine Guide](https://github.com/Deathcharge/helix-unified/blob/main/README.md) | Use `!update_optimization_guide` to post guide to Discord",
            inline=False,
        )
        embed.set_footer(text="🜂 Kael v3.4 Enhanced - Ethical monitoring active | v16.7")

    else:
        # Warnings only
        embed = discord.Embed(
            title="⚠️ System Health: Monitor",
            description="Some metrics need attention",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        for warning in warnings:
            embed.add_field(name="Warning", value=warning, inline=False)

        embed.add_field(
            name="📊 Current Metrics",
            value=f"Harmony: `{harmony:.4f}` | Resilience: `{resilience:.4f}` | Friction: `{friction:.4f}`",
            inline=False,
        )
        # Enhanced suggestions for warnings
        suggestions = []
        if harmony < 0.4:
            gap = 0.70 - harmony  # Target harmony is 0.70
            suggestions.append(f"🌀 Harmony below target (need +{gap:.2f}) - Try `!cycle 54` for moderate boost")
        if friction > 0.5:
            suggestions.append(f"🌊 Elevated entropy (friction={friction:.2f}) - Consider smaller cycle `!cycle 27`")
        if resilience < 0.5:
            suggestions.append("🛡️ Resilience slightly low - Monitor system stability")
        if throughput < 0.2:
            suggestions.append("🔥 Low energy detected - Allow system to stabilize before major operations")

        if suggestions:
            sug_text = "\n".join(suggestions)
            embed.add_field(name="💡 Suggestions", value=sug_text, inline=False)
        else:
            embed.add_field(
                name="💡 Suggestion",
                value="Consider running `!cycle` if issues persist",
                inline=False,
            )

        embed.add_field(
            name="📖 Quick Help",
            value="`!ucf` - View detailed metrics | `!cycle <steps>` - Adjust coordination field",
            inline=False,
        )
        embed.set_footer(text="🌀 Helix Collective v16.7 Enhanced - Monitoring active")

    await ctx.send(embed=embed)

    # Log health check
    log_to_shadow(
        "health_checks",
        {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "user": str(ctx.author),
            "ucf_state": ucf,
            "issues_count": len(issues),
            "warnings_count": len(warnings),
        },
    )

    # Send webhook alert for critical issues
    if issues and hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
        try:
            await ctx.bot.zapier_client.send_error_alert(
                error_message=f"Health alert: {'; '.join(issues)}",
                component="UCF_Monitor",
                severity=("critical" if harmony < 0.3 or friction > 0.7 or resilience < 0.3 else "high"),
            )
        except Exception as webhook_error:
            logger.warning("⚠️ Zapier webhook error: %s", webhook_error)


@commands.command(name="heartbeat", aliases=["pulse", "services"])
async def heartbeat_command(ctx: commands.Context) -> None:
    """
    Run heartbeat checks across all Helix services and post results.

    Monitors 7 external service endpoints:
    - Railway Core API
    - GitHub Pages Manifest
    - Zapier Dashboard
    - Creative Studio (arjuna.portal)
    - AI Dashboard (arjuna.portal)
    - Sync Portal (arjuna.portal)
    - Coordination Visualizer (arjuna.portal)

    Usage:
        !heartbeat
    """
    # Send initial message
    msg = await ctx.send("🩺 Running Helix service heartbeat… please wait.")

    try:
        from heartbeat_checker import heartbeat, load_services_manifest

        # Run heartbeat check
        results = heartbeat()
        services_manifest = load_services_manifest()
        services = services_manifest["services"]

        # Calculate summary
        ok_count = results["summary"]["ok"]
        total = results["summary"]["total"]
        failed = results["summary"]["failed"]

        # Determine embed color based on health
        if ok_count == total:
            color = discord.Color.green()
        elif ok_count > total / 2:
            color = discord.Color.orange()
        else:
            color = discord.Color.red()

        # Create embed
        embed = discord.Embed(
            title="🩺 Helix Collective — Service Heartbeat",
            description=f"**{ok_count}/{total}** services responding",
            color=color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Add service status fields
        for service_key, result in results["results"].items():
            service_info = services[service_key]
            service_name = service_info["name"]

            status_icon = "✅" if result["ok"] else "❌"
            status_code = result.get("status", "N/A")
            response_time = result.get("response_time_ms")

            if response_time is not None:
                time_str = f"{response_time}ms"
            else:
                time_str = "N/A"

            value = f"{status_icon} **Status:** `{status_code}`\n⏱️ **Response:** `{time_str}`"

            if result["error"]:
                error_short = result["error"][:50] + "..." if len(result["error"]) > 50 else result["error"]
                value += f"\n⚠️ `{error_short}`"

            embed.add_field(name=service_name, value=value, inline=True)

        # Add health summary
        if failed > 0:
            health_text = f"⚠️ **{failed}** service(s) down - monitoring required"
        else:
            health_text = "✅ All systems operational"

        embed.add_field(name="🌀 Collective Health", value=health_text, inline=False)

        # Add footer with timestamp
        embed.set_footer(text="Helix Service Monitor v16.2 | Logs saved to heartbeat_log.json | Tat Tvam Asi 🕉️")

        # Update message with embed
        await msg.edit(content=None, embed=embed)

        # Log heartbeat check
        log_to_shadow(
            "heartbeat_checks",
            {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "user": str(ctx.author),
                "ok_count": ok_count,
                "total": total,
                "failed": failed,
                "results": results["results"],
            },
        )

        # Send webhook alert if services are down
        if failed > 0 and hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
            try:
                failed_services = [services[k]["name"] for k, r in results["results"].items() if not r["ok"]]

                await ctx.bot.zapier_client.send_error_alert(
                    error_message=f"Service heartbeat alert: {failed} service(s) down",
                    component="Heartbeat_Monitor",
                    severity="high" if failed > 2 else "medium",
                    context={
                        "failed_count": failed,
                        "total_count": total,
                        "failed_services": failed_services,
                        "executor": str(ctx.author),
                    },
                )
            except Exception as webhook_error:
                logger.warning("⚠️ Zapier webhook error: %s", webhook_error)

    except Exception as e:
        await msg.edit(content=f"❌ **Heartbeat check failed:** {e!s}")
        logger.error("Heartbeat command error: %s", e)
        import traceback

        traceback.print_exc()


@commands.command(name="discovery", aliases=["endpoints", "portals", "discover"])
async def discovery_command(ctx: commands.Context) -> None:
    """Display Helix discovery endpoints for external agents (v16.7)"""

    # Fetch live status using aiohttp
    harmony = "N/A"
    agents_count = "N/A"
    operational = False
    health_emoji = "❓"

    try:
        async with ctx.bot.http_session.get(
            "https://helix-unified-production.up.railway.app/status",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status == 200:
                status = await resp.json()
                harmony = status.get("ucf", {}).get("harmony", 0)
                agents_count = status.get("agents", {}).get("count", 0)
                operational = status.get("system", {}).get("operational", False)

                # Determine health emoji
                if operational and harmony >= 0.60:
                    health_emoji = "✅"
                elif operational and harmony >= 0.30:
                    health_emoji = "⚠️"
                else:
                    health_emoji = "❌"
    except Exception as e:
        logger.warning("Discovery command: Failed to fetch live status: %s", e)

    # Create embed
    embed = discord.Embed(
        title="🌀 Helix Discovery Protocol",
        description="External agent discovery endpoints for Helix Collective v16.7",
        color=discord.Color.from_rgb(0, 255, 255),  # Cyan
    )

    embed.add_field(
        name="📚 Manifest (Static Architecture)",
        value=(
            "```\nhttps://deathcharge.github.io/helix-unified/helix-manifest.json\n```\n"
            "→ Codex structure, 18 agents, UCF schema, Ethics Validator\n"
            "→ Static discovery via GitHub Pages"
        ),
        inline=False,
    )

    embed.add_field(
        name="🌐 Discovery Endpoint (.well-known)",
        value=(
            "```\nhttps://helix-unified-production.up.railway.app/.well-known/helix.json\n```\n"
            "→ Complete system manifest with endpoints, features, agents\n"
            "→ Standard discovery protocol for external agents"
        ),
        inline=False,
    )

    embed.add_field(
        name="🌊 Live State (Real-Time UCF)",
        value=(
            "```\nhttps://helix-unified-production.up.railway.app/status\n```\n"
            f"→ Current UCF metrics (Harmony: {harmony})\n"
            f"→ System health: {health_emoji} {agents_count}/18 agents"
        ),
        inline=False,
    )

    embed.add_field(
        name="📡 WebSocket Stream (Live Updates)",
        value=(
            "```\nwss://helix-unified-production.up.railway.app/ws\n```\n"
            "→ Live UCF pulses every 5s\n"
            "→ Cycle events, telemetry stream, agent state changes"
        ),
        inline=False,
    )

    embed.add_field(
        name="📖 API Documentation",
        value=(
            "```\nhttps://helix-unified-production.up.railway.app/docs\n```\n"
            "→ Interactive Swagger/OpenAPI documentation\n"
            "→ Test endpoints directly in browser"
        ),
        inline=False,
    )

    embed.set_footer(text="Tat Tvam Asi 🙏 | Helix Discovery Protocol v16.7")

    await ctx.send(embed=embed)


@commands.command(name="storage")
async def storage_command(ctx: commands.Context, action: str = "status") -> None:
    """
    Storage Telemetry & Control

    Usage:
        !storage status  – Show archive metrics
        !storage sync    – Force upload of all archives
        !storage clean   – Prune old archives (keep latest 20)
    """
    try:
        storage = HelixStorageAdapterAsync()

        if action == "status":
            # Get storage stats
            stats = await storage.get_storage_stats()

            embed = discord.Embed(
                title="🦑 Shadow Storage Status",
                color=discord.Color.teal(),
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.add_field(name="Mode", value=stats.get("mode", "unknown"), inline=True)
            embed.add_field(name="Archives", value=str(stats.get("archive_count", "?")), inline=True)
            embed.add_field(
                name="Total Size",
                value=f"{stats.get('total_size_mb', 0):.2f} MB",
                inline=True,
            )
            embed.add_field(
                name="Free Space",
                value=f"{stats.get('free_gb', 0):.2f} GB",
                inline=True,
            )
            embed.add_field(name="Latest File", value=stats.get("latest", "None"), inline=False)
            embed.set_footer(text="Tat Tvam Asi 🙏")

            await ctx.send(embed=embed)

        elif action == "sync":
            await ctx.send("🔄 **Initiating background upload for all archives...**")

            async def force_sync():
                count = 0
                stats = await storage.get_storage_stats()
                for f in storage.root.glob("*.json"):
                    await storage.upload(str(f))
                    count += 1
                await ctx.send(f"✅ **Sync complete** - {count} files uploaded")

                # Log sync to webhook
                if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
                    try:
                        await ctx.bot.zapier_client.log_event(
                            event_title="Storage Sync Complete",
                            event_type="storage_sync",
                            agent_name="Shadow",
                            description=f"Synced {count} archives - {stats.get('total_size_mb', 0):.2f} MB total",
                            ucf_snapshot={
                                "files_synced": count,
                                "total_size_mb": stats.get("total_size_mb", 0),
                                "archive_count": stats.get("archive_count", 0),
                                "mode": stats.get("mode", "unknown"),
                                "executor": str(ctx.author),
                            },
                        )
                    except Exception as webhook_error:
                        logger.warning("⚠️ Zapier webhook error: %s", webhook_error)

            asyncio.create_task(force_sync())

        elif action == "clean":
            files = sorted(storage.root.glob("*.json"), key=lambda p: p.stat().st_mtime)
            removed = len(files) - 20
            if removed > 0:
                for f in files[:-20]:
                    f.unlink(missing_ok=True)
                await ctx.send(f"🧹 **Cleanup complete** - Removed {removed} old archives (kept latest 20)")

                # Log cleanup to webhook
                if hasattr(ctx.bot, "zapier_client") and ctx.bot.zapier_client:
                    try:
                        await ctx.bot.zapier_client.log_telemetry(
                            metric_name="storage_cleanup",
                            value=removed,
                            component="Shadow",
                            unit="files",
                        )
                    except Exception as webhook_error:
                        logger.warning("⚠️ Zapier webhook error: %s", webhook_error)
            else:
                await ctx.send("✅ **No cleanup needed** - Archive count within limits")

        else:
            await ctx.send("⚠️ **Invalid action**\nUsage: `!storage status | sync | clean`")

    except Exception as e:
        await ctx.send(f"❌ **Storage error:** {e!s}")
        logger.error("Storage command error: %s", e)


@commands.command(name="sync", aliases=["ecosystem", "report"])
async def sync_command(ctx: commands.Context) -> None:
    """
    Trigger manual ecosystem sync and display report.

    Collects data from GitHub, UCF state, and agent metrics,
    then generates a comprehensive sync report.

    Usage:
        !sync
    """
    try:
        msg = await ctx.send("🔄 **Syncing ecosystem...**")

        # Import and run sync daemon
        from helix_sync_daemon_integrated import HelixSyncDaemon

        daemon = HelixSyncDaemon()
        success = await daemon.run_sync_cycle()

        if success:
            # Read the generated Markdown report
            reports = sorted(glob.glob("exports/markdown/*.md"), reverse=True)

            if reports:
                with open(reports[0], encoding="utf-8") as f:
                    report_content = f.read()

                # Truncate if too long for Discord
                if len(report_content) > 1900:
                    report_content = report_content[:1900] + "\n\n*(Report truncated - see full export)*"

                await msg.edit(content=f"✅ **Sync complete!**\n\n```markdown\n{report_content}\n```")
            else:
                await msg.edit(content="✅ **Sync complete!** (No report generated)")
        else:
            await msg.edit(content="❌ **Sync failed** - Check logs for details")

        # Log sync trigger
        log_event(
            "manual_sync",
            {
                "user": str(ctx.author),
                "success": success,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
        )

    except Exception as e:
        await ctx.send(f"❌ **Sync error:** {e!s}")
        logger.error("Sync command error: %s", e)

        traceback.print_exc()
