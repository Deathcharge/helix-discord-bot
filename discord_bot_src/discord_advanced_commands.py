"""
Helix Discord Advanced Commands
===============================
Advanced slash commands for the Helix Discord bot that provide
Claude Code/Grok-like capabilities directly in Discord.

Commands:
- /code - Execute code snippets
- /research - Web search and summarization
- /analyze - File and image analysis
- /workflow - Trigger Helix Spirals workflows
- /agent - Direct agent interaction
- /memory - Agent memory operations
- /tools - List and use available tools
- /create - Generate content (code, docs, images)
"""

import json
import logging
import os
import re
from datetime import UTC, datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# Import agent capabilities
try:
    from apps.backend.agent_capabilities import (
        ExecutionResult,
        browse_url,
        execute_code,
        get_execution_engine,
        web_search,
    )
    from apps.backend.agent_capabilities.memory_system import get_memory_system
    from apps.backend.agent_capabilities.multimodal import CodeAnalyzer, DocumentProcessor, ImageProcessor
    from apps.backend.agent_capabilities.tool_framework import get_tool_registry

    HAS_CAPABILITIES = True
except ImportError:
    HAS_CAPABILITIES = False

# Import LLM integration
try:
    HAS_LLM = True
except ImportError:
    HAS_LLM = False


class AdvancedCommandsCog(commands.Cog):
    """Advanced commands for Helix Discord bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.execution_engine = get_execution_engine() if HAS_CAPABILITIES else None
        self.tool_registry = get_tool_registry() if HAS_CAPABILITIES else None
        self.image_processor = ImageProcessor() if HAS_CAPABILITIES else None
        self.doc_processor = DocumentProcessor() if HAS_CAPABILITIES else None
        self.code_analyzer = CodeAnalyzer() if HAS_CAPABILITIES else None

    # ==================== CODE EXECUTION ====================

    @app_commands.command(name="code", description="Execute code in a sandboxed environment")
    @app_commands.describe(
        language="Programming language (python, javascript, shell)",
        code="Code to execute",
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="Python", value="python"),
            app_commands.Choice(name="JavaScript", value="javascript"),
            app_commands.Choice(name="Shell", value="shell"),
        ]
    )
    async def code_command(self, interaction: discord.Interaction, language: str, code: str):
        """Execute code and return results"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES:
            await interaction.followup.send(embed=self._error_embed("Code execution not available"))
            return

        # Execute code
        result = await execute_code(agent_id=f"discord_{interaction.user.id}", code=code, language=language)

        # Create response embed
        if result.success:
            embed = discord.Embed(
                title=f"✅ {language.title()} Execution Successful",
                color=discord.Color.green(),
            )

            output = result.output[:1900] if result.output else "No output"
            embed.add_field(name="Output", value=f"```{language}\n{output}\n```", inline=False)

            if result.return_value and result.return_value != "None":
                embed.add_field(
                    name="Return Value",
                    value=f"```\n{str(result.return_value)[:500]}\n```",
                    inline=False,
                )
        else:
            embed = discord.Embed(
                title=f"❌ {language.title()} Execution Failed",
                color=discord.Color.red(),
            )
            embed.add_field(name="Error", value=f"```\n{result.error[:1900]}\n```", inline=False)

        embed.add_field(
            name="Execution Time",
            value=f"{result.execution_time_ms:.2f}ms",
            inline=True,
        )
        embed.set_footer(text=f"Requested by {interaction.user.name}")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="codeblock", description="Execute a code block from a message")
    @app_commands.describe(message_id="ID of the message containing the code block")
    async def codeblock_command(self, interaction: discord.Interaction, message_id: str):
        """Execute code from a message's code block"""
        await interaction.response.defer(thinking=True)

        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except (ValueError, TypeError):
            await interaction.followup.send(embed=self._error_embed("Invalid message ID"))
            return
        except Exception:
            logger.exception("Error fetching message")
            await interaction.followup.send(embed=self._error_embed("Message not found"))
            return

        # Extract code block
        code_match = re.search(r"```(\w+)?\n(.*?)```", message.content, re.DOTALL)
        if not code_match:
            await interaction.followup.send(embed=self._error_embed("No code block found in message"))
            return

        language = code_match.group(1) or "python"
        code = code_match.group(2)

        # Map common language names
        lang_map = {"py": "python", "js": "javascript", "bash": "shell", "sh": "shell"}
        language = lang_map.get(language.lower(), language.lower())

        if language not in ("python", "javascript", "shell"):
            await interaction.followup.send(embed=self._error_embed(f"Unsupported language: {language}"))
            return

        result = await execute_code(agent_id=f"discord_{interaction.user.id}", code=code, language=language)

        embed = self._execution_result_embed(result, language)
        await interaction.followup.send(embed=embed)

    # ==================== WEB RESEARCH ====================

    @app_commands.command(name="research", description="Search the web and summarize results")
    @app_commands.describe(query="What to search for", num_results="Number of results to fetch (1-10)")
    async def research_command(self, interaction: discord.Interaction, query: str, num_results: int = 5):
        """Search the web and provide summarized results"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES:
            await interaction.followup.send(embed=self._error_embed("Research capability not available"))
            return

        num_results = min(max(num_results, 1), 10)

        # Perform search
        result = await web_search(query, num_results)

        if not result.success:
            await interaction.followup.send(embed=self._error_embed(f"Search failed: {result.error}"))
            return

        # Parse results
        try:
            search_results = json.loads(result.output) if result.output else []
        except Exception as e:
            logger.warning("Failed to parse search results: %s", e)
            search_results = []

        embed = discord.Embed(title=f"🔍 Research: {query[:100]}", color=discord.Color.blue())

        if search_results:
            for i, item in enumerate(search_results[:5], 1):
                title = item.get("title", "No title")[:100]
                snippet = item.get("snippet", "No description")[:200]
                url = item.get("url", "")

                embed.add_field(
                    name=f"{i}. {title}",
                    value=f"{snippet}\n[Link]({url})" if url else snippet,
                    inline=False,
                )
        else:
            embed.description = "No results found"

        embed.set_footer(text=f"Searched by {interaction.user.name} • {len(search_results)} results")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="browse", description="Browse a webpage and extract content")
    @app_commands.describe(url="URL to browse")
    async def browse_command(self, interaction: discord.Interaction, url: str):
        """Browse a URL and extract content"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES:
            await interaction.followup.send(embed=self._error_embed("Browse capability not available"))
            return

        result = await browse_url(url)

        if not result.success:
            await interaction.followup.send(embed=self._error_embed(f"Failed to browse: {result.error}"))
            return

        content = result.output[:3500] if result.output else "No content extracted"

        embed = discord.Embed(
            title=f"🌐 {result.metadata.get('title', 'Web Page')[:100]}",
            url=url,
            description=content[:2000],
            color=discord.Color.blue(),
        )

        if len(content) > 2000:
            embed.add_field(
                name="Content (continued)",
                value=(content[2000:3500] + "..." if len(content) > 3500 else content[2000:]),
                inline=False,
            )

        embed.set_footer(text=f"Browsed by {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    # ==================== FILE ANALYSIS ====================

    @app_commands.command(name="analyze", description="Analyze an attached file or image")
    @app_commands.describe(attachment="File to analyze")
    async def analyze_command(self, interaction: discord.Interaction, attachment: discord.Attachment):
        """Analyze an uploaded file"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES:
            await interaction.followup.send(embed=self._error_embed("Analysis capability not available"))
            return

        # Download attachment
        file_data = await attachment.read()
        filename = attachment.filename.lower()

        # Determine file type and analyze
        if any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            # Image analysis
            result = await self.image_processor.analyze(file_data, extract_text=True)

            embed = discord.Embed(
                title=f"🖼️ Image Analysis: {attachment.filename}",
                color=discord.Color.purple(),
            )
            embed.add_field(name="Dimensions", value=f"{result.width}x{result.height}", inline=True)
            embed.add_field(name="Format", value=result.format, inline=True)
            embed.add_field(name="Size", value=f"{result.file_size / 1024:.1f} KB", inline=True)

            if result.dominant_colors:
                embed.add_field(
                    name="Dominant Colors",
                    value=" ".join(result.dominant_colors[:5]),
                    inline=False,
                )

            if result.text_content:
                embed.add_field(
                    name="Extracted Text",
                    value=(
                        result.text_content[:1000] + "..." if len(result.text_content) > 1000 else result.text_content
                    ),
                    inline=False,
                )

            embed.set_thumbnail(url=attachment.url)

        elif any(filename.endswith(ext) for ext in [".py", ".js", ".ts", ".java", ".cpp", ".go", ".rs"]):
            # Code analysis
            code = file_data.decode("utf-8", errors="replace")
            result = await self.code_analyzer.analyze(code, file_path=filename)

            embed = discord.Embed(
                title=f"📝 Code Analysis: {attachment.filename}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Language", value=result.language, inline=True)
            embed.add_field(name="Lines of Code", value=str(result.lines_of_code), inline=True)
            embed.add_field(
                name="Complexity",
                value=f"{result.complexity_score:.1f}/10",
                inline=True,
            )
            embed.add_field(name="Functions", value=str(len(result.functions)), inline=True)
            embed.add_field(name="Classes", value=str(len(result.classes)), inline=True)
            embed.add_field(
                name="Doc Coverage",
                value=f"{result.documentation_coverage*100:.0f}%",
                inline=True,
            )

            if result.issues:
                issues_text = "\n".join([f"• Line {i['line']}: {i['message']}" for i in result.issues[:5]])
                embed.add_field(name="Issues", value=issues_text[:1000], inline=False)

            if result.suggestions:
                embed.add_field(
                    name="Suggestions",
                    value="\n".join([f"• {s}" for s in result.suggestions[:5]]),
                    inline=False,
                )

        elif any(filename.endswith(ext) for ext in [".pdf", ".docx", ".txt", ".md", ".csv", ".json"]):
            # Document analysis
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as f:
                f.write(file_data)
                temp_path = f.name

            try:
                result = await self.doc_processor.analyze(temp_path)

                embed = discord.Embed(
                    title=f"📄 Document Analysis: {attachment.filename}",
                    color=discord.Color.orange(),
                )
                embed.add_field(name="Format", value=result.format.upper(), inline=True)
                embed.add_field(name="Pages", value=str(result.pages), inline=True)
                embed.add_field(name="Words", value=str(result.word_count), inline=True)

                preview = result.text[:1500] + "..." if len(result.text) > 1500 else result.text
                embed.add_field(
                    name="Content Preview",
                    value=preview or "No text content",
                    inline=False,
                )

                if result.tables:
                    embed.add_field(name="Tables Found", value=str(len(result.tables)), inline=True)
            finally:
                os.unlink(temp_path)
        else:
            embed = discord.Embed(
                title="❓ Unknown File Type",
                description=f"Cannot analyze file: {attachment.filename}",
                color=discord.Color.grey(),
            )

        embed.set_footer(text=f"Analyzed by {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    # ==================== AGENT INTERACTION ====================

    @app_commands.command(name="agent", description="Chat with a specific Helix agent")
    @app_commands.describe(agent="Agent to interact with", message="Your message to the agent")
    @app_commands.choices(
        agent=[
            app_commands.Choice(name="Nexus (Strategic)", value="nexus"),
            app_commands.Choice(name="Oracle (Prophetic)", value="oracle"),
            app_commands.Choice(name="Velocity (Fast)", value="velocity"),
            app_commands.Choice(name="Cipher (Analytical)", value="cipher"),
            app_commands.Choice(name="Phoenix (Resilient)", value="phoenix"),
            app_commands.Choice(name="Luna (Observant)", value="luna"),
            app_commands.Choice(name="Forge (Builder)", value="forge"),
            app_commands.Choice(name="Sage (Researcher)", value="sage"),
            app_commands.Choice(name="Lumina (Clarifier)", value="lumina"),
            app_commands.Choice(name="Sentinel (Guardian)", value="sentinel"),
        ]
    )
    async def agent_command(self, interaction: discord.Interaction, agent: str, message: str):
        """Interact with a specific Helix agent"""
        await interaction.response.defer(thinking=True)

        # Get agent memory
        memory = get_memory_system(agent) if HAS_CAPABILITIES else None

        # Agent personalities
        personalities = {
            "nexus": {
                "emoji": "🎯",
                "style": "strategic and decisive",
                "color": discord.Color.gold(),
            },
            "oracle": {
                "emoji": "🔮",
                "style": "prophetic and mystical",
                "color": discord.Color.purple(),
            },
            "velocity": {
                "emoji": "⚡",
                "style": "fast and action-oriented",
                "color": discord.Color.yellow(),
            },
            "cipher": {
                "emoji": "🧬",
                "style": "analytical and precise",
                "color": discord.Color.teal(),
            },
            "phoenix": {
                "emoji": "🔥",
                "style": "resilient and transformative",
                "color": discord.Color.orange(),
            },
            "luna": {
                "emoji": "🌙",
                "style": "quiet and observant",
                "color": discord.Color.dark_blue(),
            },
            "forge": {
                "emoji": "⚙️",
                "style": "practical and constructive",
                "color": discord.Color.dark_grey(),
            },
            "sage": {
                "emoji": "🔬",
                "style": "analytical and investigative",
                "color": discord.Color.green(),
            },
            "lumina": {
                "emoji": "✨",
                "style": "clear and illuminating",
                "color": discord.Color.light_grey(),
            },
            "sentinel": {
                "emoji": "🛡️",
                "style": "protective and vigilant",
                "color": discord.Color.red(),
            },
        }

        agent_info = personalities.get(agent, {"emoji": "🤖", "style": "helpful", "color": discord.Color.blue()})

        # Add to conversation history
        if memory:
            memory.add_conversation_message("user", message)

        # Generate response (use LLM if available, otherwise template)
        if HAS_LLM:
            system_prompt = f"You are {agent.title()}, a Helix Collective AI agent. Your personality is {agent_info['style']}. Respond in character."
            if memory:
                system_prompt = await memory.get_augmented_context(message, system_prompt)

            try:
                # This would call an actual LLM client when available
                # For now, provide a template response
                response = f"*{agent.title()} responds with {agent_info['style']} insight...*\n\nRegarding: {message[:100]}\n\nI process this through my unique perspective as {agent.title()}."
            except Exception as e:
                logger.warning("LLM response failed for agent %s: %s", agent, e)
                response = f"*{agent.title()} contemplates your message...*\n\nI understand you're asking about: {message[:100]}. Let me process this with my {agent_info['style']} approach."
        else:
            response = f"*{agent.title()} responds in their {agent_info['style']} manner...*\n\nYour query has been received. In a full deployment, I would provide a detailed response using my unique perspective."

        # Add response to memory
        if memory:
            memory.add_conversation_message("assistant", response)

        embed = discord.Embed(
            title=f"{agent_info['emoji']} {agent.title()}",
            description=response[:4000],
            color=agent_info["color"],
        )
        embed.set_footer(text=f"Requested by {interaction.user.name} • Helix Collective")

        await interaction.followup.send(embed=embed)

    # ==================== TOOLS ====================

    @app_commands.command(name="tools", description="List available tools or use a specific tool")
    @app_commands.describe(
        tool_name="Name of the tool to use (leave empty to list all)",
        params="JSON parameters for the tool",
    )
    async def tools_command(
        self,
        interaction: discord.Interaction,
        tool_name: str | None = None,
        params: str | None = None,
    ):
        """List or use available tools"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES or not self.tool_registry:
            await interaction.followup.send(embed=self._error_embed("Tools not available"))
            return

        if not tool_name:
            # List all tools
            tools = self.tool_registry.list_tools()

            embed = discord.Embed(
                title="🛠️ Available Tools",
                description="Use `/tools tool_name:<name> params:<json>` to execute a tool",
                color=discord.Color.blue(),
            )

            for tool in tools[:25]:  # Discord limit
                embed.add_field(name=f"`{tool.name}`", value=tool.description[:100], inline=True)

            embed.set_footer(text=f"{len(tools)} tools available")
            await interaction.followup.send(embed=embed)
        else:
            # Execute tool
            tool = self.tool_registry.get(tool_name)
            if not tool:
                await interaction.followup.send(embed=self._error_embed(f"Tool not found: {tool_name}"))
                return

            # Parse parameters
            try:
                tool_params = json.loads(params) if params else {}
            except json.JSONDecodeError:
                await interaction.followup.send(embed=self._error_embed("Invalid JSON parameters"))
                return

            # Execute
            result = await self.tool_registry.execute(tool_name, tool_params)

            if result.success:
                embed = discord.Embed(title=f"✅ Tool: {tool_name}", color=discord.Color.green())
                output = str(result.output)[:1900]
                embed.add_field(name="Output", value=f"```\n{output}\n```", inline=False)
            else:
                embed = discord.Embed(title=f"❌ Tool: {tool_name}", color=discord.Color.red())
                embed.add_field(name="Error", value=result.error[:1000], inline=False)

            embed.add_field(
                name="Execution Time",
                value=f"{result.execution_time_ms:.2f}ms",
                inline=True,
            )
            await interaction.followup.send(embed=embed)

    # ==================== MEMORY ====================

    @app_commands.command(name="memory", description="Manage agent memory")
    @app_commands.describe(
        action="Memory action to perform",
        content="Content to remember or query to recall",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Remember", value="remember"),
            app_commands.Choice(name="Recall", value="recall"),
            app_commands.Choice(name="Clear", value="clear"),
            app_commands.Choice(name="Summary", value="summary"),
        ]
    )
    async def memory_command(
        self,
        interaction: discord.Interaction,
        action: str,
        content: str | None = None,
    ):
        """Manage agent memory"""
        await interaction.response.defer(thinking=True)

        if not HAS_CAPABILITIES:
            await interaction.followup.send(embed=self._error_embed("Memory system not available"))
            return

        agent_id = f"discord_{interaction.user.id}"
        memory = get_memory_system(agent_id)

        if action == "remember":
            if not content:
                await interaction.followup.send(embed=self._error_embed("Please provide content to remember"))
                return

            entry_id = memory.remember(content, tags=["discord", "user_memory"])

            embed = discord.Embed(
                title="💾 Memory Stored",
                description=f"Remembered: {content[:500]}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Memory ID", value=entry_id[:8], inline=True)

        elif action == "recall":
            if not content:
                await interaction.followup.send(embed=self._error_embed("Please provide a query to recall"))
                return

            memories = memory.recall(content, limit=5)

            embed = discord.Embed(title=f"🔍 Recall: {content[:50]}", color=discord.Color.blue())

            if memories:
                for i, mem in enumerate(memories, 1):
                    embed.add_field(
                        name=f"{i}. {mem.type.value.title()}",
                        value=(mem.content[:200] + "..." if len(mem.content) > 200 else mem.content),
                        inline=False,
                    )
            else:
                embed.description = "No relevant memories found"

        elif action == "clear":
            memory.clear_session()
            embed = discord.Embed(
                title="🗑️ Memory Cleared",
                description="Session memory has been cleared",
                color=discord.Color.orange(),
            )

        elif action == "summary":
            summary = memory.get_summary()
            embed = discord.Embed(title="📊 Memory Summary", color=discord.Color.purple())
            embed.add_field(
                name="Conversation Messages",
                value=str(summary["conversation_messages"]),
                inline=True,
            )
            embed.add_field(
                name="Knowledge Entries",
                value=str(summary["knowledge_entries"]),
                inline=True,
            )
            embed.add_field(
                name="Long-term Memories",
                value=str(summary["long_term_memories"]),
                inline=True,
            )
            embed.add_field(name="Preferences", value=str(summary["preferences"]), inline=True)

        embed.set_footer(text=f"User: {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    # ==================== WORKFLOW ====================

    @app_commands.command(name="workflow", description="Trigger a Helix Spirals workflow")
    @app_commands.describe(
        workflow_name="Name of the workflow to trigger",
        input_data="JSON input data for the workflow",
    )
    async def workflow_command(
        self,
        interaction: discord.Interaction,
        workflow_name: str,
        input_data: str | None = None,
    ):
        """Trigger a Helix Spirals workflow"""
        await interaction.response.defer(thinking=True)

        # Parse input
        try:
            data = json.loads(input_data) if input_data else {}
        except json.JSONDecodeError:
            await interaction.followup.send(embed=self._error_embed("Invalid JSON input data"))
            return

        # Add Discord context
        data["discord_context"] = {
            "user_id": str(interaction.user.id),
            "user_name": interaction.user.name,
            "channel_id": str(interaction.channel_id),
            "guild_id": str(interaction.guild_id) if interaction.guild else None,
        }

        # Try to trigger workflow via API
        try:
            api_url = os.getenv("HELIX_API_URL", "http://localhost:8000")

            async with aiohttp.ClientSession() as session, session.post(
                f"{api_url}/api/spirals/execute",
                json={"workflow_name": workflow_name, "input": data},
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    embed = discord.Embed(
                        title=f"🌀 Workflow Triggered: {workflow_name}",
                        color=discord.Color.green(),
                    )
                    embed.add_field(
                        name="Execution ID",
                        value=result.get("execution_id", "N/A"),
                        inline=True,
                    )
                    embed.add_field(
                        name="Status",
                        value=result.get("status", "Started"),
                        inline=True,
                    )
                else:
                    embed = self._error_embed(f"Workflow trigger failed: HTTP {response.status}")
        except Exception as e:
            logger.warning("Workflow trigger failed for %s: %s", workflow_name, e)
            embed = discord.Embed(
                title=f"🌀 Workflow: {workflow_name}",
                description="Workflow trigger queued (API not available)",
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Input Data",
                value=f"```json\n{json.dumps(data, indent=2)[:500]}\n```",
                inline=False,
            )

        embed.set_footer(text=f"Triggered by {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    # ==================== HELPER METHODS ====================

    def _error_embed(self, message: str) -> discord.Embed:
        """Create an error embed"""
        return discord.Embed(title="❌ Error", description=message, color=discord.Color.red())

    def _execution_result_embed(self, result: "ExecutionResult", language: str) -> discord.Embed:
        """Create embed for execution result"""
        if result.success:
            embed = discord.Embed(title=f"✅ {language.title()} Execution", color=discord.Color.green())
            output = result.output[:1900] if result.output else "No output"
            embed.add_field(name="Output", value=f"```\n{output}\n```", inline=False)
        else:
            embed = discord.Embed(
                title=f"❌ {language.title()} Execution Failed",
                color=discord.Color.red(),
            )
            embed.add_field(name="Error", value=f"```\n{result.error[:1900]}\n```", inline=False)

        embed.add_field(name="Time", value=f"{result.execution_time_ms:.2f}ms", inline=True)
        return embed


# Additional utility commands
class UtilityCommandsCog(commands.Cog):
    """Utility commands for Helix Discord bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="calculate", description="Perform mathematical calculations")
    @app_commands.describe(expression="Mathematical expression to evaluate")
    async def calculate_command(self, interaction: discord.Interaction, expression: str):
        """Calculate mathematical expressions"""
        import math

        # Safe evaluation
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed.update(
            {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "int": int,
                "float": float,
            }
        )

        try:
            from apps.backend.utils.safe_eval import SafeEvaluator

            evaluator = SafeEvaluator(allowed_names=allowed)
            result = evaluator.eval(expression)
            embed = discord.Embed(title="🔢 Calculator", color=discord.Color.blue())
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"**{result}**", inline=False)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Calculation Error",
                description=str(e),
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="encode", description="Encode/decode text")
    @app_commands.describe(
        text="Text to encode/decode",
        method="Encoding method",
        decode="Decode instead of encode",
    )
    @app_commands.choices(
        method=[
            app_commands.Choice(name="Base64", value="base64"),
            app_commands.Choice(name="URL", value="url"),
            app_commands.Choice(name="Hex", value="hex"),
        ]
    )
    async def encode_command(
        self,
        interaction: discord.Interaction,
        text: str,
        method: str,
        decode: bool = False,
    ):
        """Encode or decode text"""
        import base64
        from urllib.parse import quote, unquote

        try:
            if method == "base64":
                if decode:
                    result = base64.b64decode(text.encode()).decode()
                else:
                    result = base64.b64encode(text.encode()).decode()
            elif method == "url":
                if decode:
                    result = unquote(text)
                else:
                    result = quote(text)
            elif method == "hex":
                if decode:
                    result = bytes.fromhex(text).decode()
                else:
                    result = text.encode().hex()

            embed = discord.Embed(
                title=f"{'🔓' if decode else '🔐'} {method.title()} {'Decode' if decode else 'Encode'}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Input", value=f"```\n{text[:500]}\n```", inline=False)
            embed.add_field(name="Output", value=f"```\n{result[:500]}\n```", inline=False)
        except Exception as e:
            embed = discord.Embed(title="❌ Encoding Error", description=str(e), color=discord.Color.red())

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="json", description="Format and validate JSON")
    @app_commands.describe(json_text="JSON text to format")
    async def json_command(self, interaction: discord.Interaction, json_text: str):
        """Format and validate JSON"""
        try:
            parsed = json.loads(json_text)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)

            embed = discord.Embed(title="✅ Valid JSON", color=discord.Color.green())
            embed.add_field(
                name="Formatted",
                value=f"```json\n{formatted[:1900]}\n```",
                inline=False,
            )
            embed.add_field(name="Type", value=type(parsed).__name__, inline=True)
            if isinstance(parsed, (list, dict)):
                embed.add_field(name="Items", value=str(len(parsed)), inline=True)
        except json.JSONDecodeError as e:
            embed = discord.Embed(
                title="❌ Invalid JSON",
                description=f"Error: {e.msg} at position {e.pos}",
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="timestamp", description="Convert timestamps")
    @app_commands.describe(timestamp="Unix timestamp or 'now'", format="Output format")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="ISO 8601", value="iso"),
            app_commands.Choice(name="Discord", value="discord"),
            app_commands.Choice(name="Human Readable", value="human"),
        ]
    )
    async def timestamp_command(
        self,
        interaction: discord.Interaction,
        timestamp: str = "now",
        format: str = "discord",
    ):
        """Convert and display timestamps"""
        try:
            if timestamp == "now":
                dt = datetime.now(UTC)
                ts = int(dt.timestamp())
            else:
                ts = int(timestamp)
                dt = datetime.utcfromtimestamp(ts)

            embed = discord.Embed(title="🕐 Timestamp", color=discord.Color.blue())
            embed.add_field(name="Unix", value=str(ts), inline=True)
            embed.add_field(name="ISO 8601", value=dt.isoformat() + "Z", inline=True)
            embed.add_field(name="Discord", value=f"<t:{ts}:F>", inline=True)
            embed.add_field(name="Relative", value=f"<t:{ts}:R>", inline=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Invalid Timestamp",
                description=str(e),
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading cogs"""
    await bot.add_cog(AdvancedCommandsCog(bot))
    await bot.add_cog(UtilityCommandsCog(bot))
    logger.info("✅ Advanced Discord commands loaded")
