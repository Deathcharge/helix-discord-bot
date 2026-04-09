# Helix Discord Bot: Complete API Reference

**Comprehensive documentation for all bot components, commands, and integrations**

---

## Table of Contents

1. [Bot Core API](#bot-core-api)
2. [Command System](#command-system)
3. [Memory Service](#memory-service)
4. [Agent Integration](#agent-integration)
5. [Performance Monitoring](#performance-monitoring)
6. [Configuration](#configuration)
7. [Error Handling](#error-handling)
8. [Examples](#examples)

---

## Bot Core API

### HelixBot

The main bot class that orchestrates all Discord interactions and Helix ecosystem integration.

#### Initialization

```python
from discord_bot_src.discord_bot_helix import HelixBot

bot = HelixBot(
    command_prefix="!",
    intents=discord.Intents.default(),
    helix_api_key="your_api_key",
    helix_api_url="https://api.helix.example.com"
)
```

#### Core Methods

**`async def on_ready()`**

Called when the bot successfully connects to Discord.

```python
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    print(f"Latency: {bot.latency * 1000:.2f}ms")
```

**`async def on_message(message)`**

Called when a message is received in any channel the bot can see.

```python
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)
```

**`async def on_command_error(ctx, error)`**

Called when a command raises an exception.

```python
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found!")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command!")
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `user` | `discord.ClientUser` | The bot's user object |
| `latency` | `float` | Latency to Discord in seconds |
| `guilds` | `List[discord.Guild]` | List of guilds the bot is in |
| `cogs` | `Dict[str, Cog]` | Dictionary of loaded cogs |

---

## Command System

### Command Structure

All commands are organized into modules (Cogs) for better organization and maintainability.

#### Creating a Command

```python
from discord.ext import commands
import discord

class MyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="mycommand", aliases=["mc"])
    @commands.has_permissions(send_messages=True)
    async def my_command(self, ctx, *, argument: str):
        """
        Description of my command.
        
        Args:
            argument: The argument for the command
        """
        await ctx.send(f"You said: {argument}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

async def setup(bot):
    await bot.add_cog(MyCommands(bot))
```

### Command Decorators

**`@commands.command()`**

Marks a function as a command.

```python
@commands.command(name="hello", aliases=["hi", "hey"])
async def hello(ctx):
    """Say hello to the user."""
    await ctx.send(f"Hello, {ctx.author.name}!")
```

**`@commands.has_permissions()`**

Checks if the user has specific permissions.

```python
@commands.command()
@commands.has_permissions(administrator=True)
async def admin_command(ctx):
    """Admin-only command."""
    await ctx.send("This is an admin command!")
```

**`@commands.has_role()`**

Checks if the user has a specific role.

```python
@commands.command()
@commands.has_role("Moderator")
async def mod_command(ctx):
    """Moderator-only command."""
    await ctx.send("This is a moderator command!")
```

**`@commands.cooldown()`**

Adds a cooldown to prevent command spam.

```python
@commands.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def limited_command(ctx):
    """This command can only be used once per minute per user."""
    await ctx.send("Command executed!")
```

### Command Context

The `ctx` parameter provides information about the command invocation.

#### Context Properties

| Property | Type | Description |
|----------|------|-------------|
| `author` | `discord.Member` | The user who invoked the command |
| `guild` | `discord.Guild` | The guild where the command was invoked |
| `channel` | `discord.TextChannel` | The channel where the command was invoked |
| `message` | `discord.Message` | The message that triggered the command |
| `bot` | `HelixBot` | The bot instance |

#### Context Methods

**`async def send(content=None, *, embed=None, file=None, ...)`**

Send a message to the channel.

```python
await ctx.send("Hello!")
await ctx.send(embed=discord.Embed(title="Title", description="Description"))
```

**`async def reply(content=None, *, mention_author=True, ...)`**

Reply to the message that triggered the command.

```python
await ctx.reply("This is a reply!")
```

**`async def invoke(command)`**

Invoke another command.

```python
await ctx.invoke(self.bot.get_command("other_command"))
```

---

## Memory Service

### AgentMemoryService

Manages persistent memory for agents and users.

#### Initialization

```python
from discord_bot_src.agent_memory_service import AgentMemoryService

memory_service = AgentMemoryService(
    storage_backend="redis",  # or "memory", "database"
    connection_string="redis://localhost:6379"
)

await memory_service.initialize()
```

#### Methods

**`async def store_memory(key, value, ttl=None)`**

Store a value in memory.

```python
await memory_service.store_memory(
    f"user_{user_id}_context",
    {"last_command": "hello", "timestamp": datetime.now()},
    ttl=3600  # 1 hour
)
```

**`async def retrieve_memory(key)`**

Retrieve a value from memory.

```python
context = await memory_service.retrieve_memory(f"user_{user_id}_context")
if context:
    print(f"Last command: {context['last_command']}")
```

**`async def clear_memory(key)`**

Clear a specific memory entry.

```python
await memory_service.clear_memory(f"user_{user_id}_context")
```

**`async def get_memory_stats()`**

Get memory statistics.

```python
stats = await memory_service.get_memory_stats()
print(f"Memory size: {stats['size']} bytes")
print(f"Keys stored: {stats['key_count']}")
```

---

## Agent Integration

### AgentBotFactory

Creates and manages agents for the bot.

#### Initialization

```python
from discord_bot_src.agent_bot_factory import AgentBotFactory

factory = AgentBotFactory(
    helix_core_url="https://helix-core.example.com",
    helix_api_key="your_api_key"
)
```

#### Methods

**`def create_agent(name, model="gpt-4", temperature=0.7)`**

Create a new agent.

```python
agent = factory.create_agent(
    name="ContentGenerator",
    model="gpt-4",
    temperature=0.7
)
```

**`def create_swarm(agents, consensus_type="voting")`**

Create a swarm of agents.

```python
swarm = factory.create_swarm(
    agents=[agent1, agent2, agent3],
    consensus_type="voting"
)
```

**`def get_agent(agent_id)`**

Retrieve an existing agent.

```python
agent = factory.get_agent("agent_001")
```

---

## Performance Monitoring

### PerformanceMonitor

Tracks bot performance metrics.

#### Methods

**`def get_latency()`**

Get current latency to Discord.

```python
latency = monitor.get_latency()
print(f"Latency: {latency * 1000:.2f}ms")
```

**`def get_memory_usage()`**

Get current memory usage.

```python
memory = monitor.get_memory_usage()
print(f"RSS: {memory['rss'] / 1024 / 1024:.2f} MB")
```

**`def get_cpu_usage()`**

Get current CPU usage.

```python
cpu = monitor.get_cpu_usage()
print(f"CPU: {cpu:.2f}%")
```

**`def get_command_stats()`**

Get command execution statistics.

```python
stats = monitor.get_command_stats()
print(f"Total commands: {stats['total']}")
print(f"Success rate: {stats['success'] / stats['total'] * 100:.2f}%")
```

---

## Configuration

### Environment Variables

Configure the bot using environment variables.

```bash
# Discord Bot Token
export DISCORD_BOT_TOKEN="your_token_here"

# Helix API Configuration
export HELIX_API_KEY="your_api_key"
export HELIX_API_URL="https://api.helix.example.com"

# Bot Configuration
export BOT_COMMAND_PREFIX="!"
export BOT_INTENTS="default"

# Memory Service Configuration
export MEMORY_BACKEND="redis"
export MEMORY_CONNECTION="redis://localhost:6379"

# Logging Configuration
export LOG_LEVEL="INFO"
export LOG_FILE="bot.log"
```

### Configuration File

Create a `config.json` file for advanced configuration.

```json
{
  "bot": {
    "command_prefix": "!",
    "intents": "default",
    "status": "online",
    "activity": "Helix AI"
  },
  "helix": {
    "api_url": "https://api.helix.example.com",
    "api_key": "${HELIX_API_KEY}",
    "timeout": 30
  },
  "memory": {
    "backend": "redis",
    "connection": "redis://localhost:6379",
    "ttl": 3600
  },
  "logging": {
    "level": "INFO",
    "file": "bot.log",
    "max_size": 10485760,
    "backup_count": 5
  }
}
```

---

## Error Handling

### Common Exceptions

**`discord.Forbidden`**

Raised when the bot doesn't have permission to perform an action.

```python
try:
    await message.delete()
except discord.Forbidden:
    print("Bot doesn't have permission to delete messages")
```

**`discord.HTTPException`**

Raised when an HTTP request fails.

```python
try:
    await ctx.send("Hello!")
except discord.HTTPException as e:
    print(f"HTTP error: {e.status} - {e.text}")
```

**`commands.CommandNotFound`**

Raised when a command is not found.

```python
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found!")
```

**`commands.MissingPermissions`**

Raised when the user doesn't have required permissions.

```python
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission!")
```

---

## Examples

### Example 1: Simple Command

```python
@commands.command()
async def greet(ctx, name: str):
    """Greet a user by name."""
    await ctx.send(f"Hello, {name}! 👋")
```

**Usage**: `!greet Alice`

### Example 2: Command with Embed

```python
@commands.command()
async def info(ctx):
    """Display bot information."""
    embed = discord.Embed(
        title="Helix Discord Bot",
        description="Powered by the Helix AI ecosystem",
        color=discord.Color.blue()
    )
    embed.add_field(name="Version", value="1.0.0", inline=False)
    embed.add_field(name="Latency", value=f"{ctx.bot.latency * 1000:.2f}ms", inline=False)
    await ctx.send(embed=embed)
```

### Example 3: Admin Command

```python
@commands.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int):
    """Clear messages from the channel."""
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Deleted {len(deleted)} messages!")
```

### Example 4: Agent Integration

```python
@commands.command()
async def generate(ctx, *, prompt: str):
    """Generate content using an AI agent."""
    agent = factory.get_agent("content_generator")
    
    result = await agent.generate(prompt)
    await ctx.send(result)
```

### Example 5: Memory Usage

```python
@commands.command()
async def remember(ctx, *, text: str):
    """Remember something for later."""
    await memory_service.store_memory(
        f"user_{ctx.author.id}_note",
        {"text": text, "timestamp": datetime.now()}
    )
    await ctx.send("I'll remember that! 📝")

@commands.command()
async def recall(ctx):
    """Recall what you asked me to remember."""
    note = await memory_service.retrieve_memory(f"user_{ctx.author.id}_note")
    if note:
        await ctx.send(f"You asked me to remember: {note['text']}")
    else:
        await ctx.send("I don't have any notes for you!")
```

---

## Best Practices

### 1. Always Check Permissions

Before performing actions, verify the bot has necessary permissions.

```python
if ctx.channel.permissions_for(ctx.me).send_messages:
    await ctx.send("Message sent!")
else:
    print("Bot doesn't have permission to send messages")
```

### 2. Use Embeds for Rich Content

Embeds provide better formatting and visual appeal.

```python
embed = discord.Embed(
    title="Title",
    description="Description",
    color=discord.Color.green()
)
embed.add_field(name="Field", value="Value")
await ctx.send(embed=embed)
```

### 3. Handle Errors Gracefully

Always catch and handle exceptions appropriately.

```python
try:
    # Command logic
    pass
except Exception as e:
    await ctx.send(f"An error occurred: {str(e)}")
    print(f"Error: {e}")
```

### 4. Use Cooldowns to Prevent Spam

Implement cooldowns on frequently used commands.

```python
@commands.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def limited(ctx):
    await ctx.send("This command is limited!")
```

### 5. Document Your Commands

Always include docstrings for commands.

```python
@commands.command()
async def mycommand(ctx, arg: str):
    """
    This is my command.
    
    Args:
        arg: The argument for the command
    """
    await ctx.send(f"Argument: {arg}")
```

---

**Last Updated**: April 9, 2026  
**Version**: 1.0  
**Status**: Production Ready
