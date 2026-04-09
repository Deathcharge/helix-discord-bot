# Helix Discord Bot: Getting Started Guide

**Quick start guide for setting up and running the Helix Discord Bot**

---

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.8 or higher
- pip (Python package manager)
- Git
- Discord account with server admin privileges

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/Deathcharge/helix-discord-bot.git
cd helix-discord-bot
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Helix API Configuration
HELIX_API_KEY=your_helix_api_key_here
HELIX_API_URL=https://api.helix.example.com

# Bot Settings
BOT_COMMAND_PREFIX=!
BOT_STATUS=online
BOT_ACTIVITY=Helix AI

# Memory Service Configuration
MEMORY_BACKEND=redis
MEMORY_CONNECTION=redis://localhost:6379

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=bot.log
```

---

## Getting Discord Bot Token

### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Enter a name for your application
4. Click "Create"

### Step 2: Create Bot User

1. Go to the "Bot" section
2. Click "Add Bot"
3. Under the TOKEN section, click "Copy"
4. Paste the token in your `.env` file as `DISCORD_BOT_TOKEN`

### Step 3: Set Bot Permissions

1. Go to "OAuth2" → "URL Generator"
2. Select scopes: `bot`
3. Select permissions:
   - Send Messages
   - Read Message History
   - Manage Messages
   - Add Reactions
   - Embed Links
   - Attach Files
4. Copy the generated URL
5. Open the URL in your browser to invite the bot to your server

---

## Running the Bot

### Start the Bot

```bash
python -m discord_bot_src.main
```

You should see output like:

```
2024-01-01 12:00:00 - INFO - Connecting to Discord...
2024-01-01 12:00:02 - INFO - Bot logged in as HelixBot#1234
2024-01-01 12:00:02 - INFO - Bot is ready!
```

### Verify Bot is Running

In your Discord server, type:

```
!ping
```

The bot should respond with the current latency.

---

## Basic Commands

### Help Command

Get a list of all available commands:

```
!help
```

Get help for a specific command:

```
!help command_name
```

### Ping Command

Check bot latency:

```
!ping
```

### Info Command

Display bot information:

```
!info
```

---

## Configuration

### Command Prefix

Change the command prefix by setting the environment variable:

```bash
BOT_COMMAND_PREFIX=/
```

Now commands use `/` instead of `!`:

```
/ping
/help
```

### Logging Level

Control logging verbosity:

```bash
LOG_LEVEL=DEBUG  # Most verbose
LOG_LEVEL=INFO   # Default
LOG_LEVEL=WARNING # Less verbose
LOG_LEVEL=ERROR  # Only errors
```

### Memory Backend

Choose where to store memory:

```bash
# In-memory storage (fast, not persistent)
MEMORY_BACKEND=memory

# Redis storage (persistent, recommended for production)
MEMORY_BACKEND=redis
MEMORY_CONNECTION=redis://localhost:6379

# Database storage (persistent, slower)
MEMORY_BACKEND=database
MEMORY_CONNECTION=postgresql://user:pass@localhost/helix_bot
```

---

## Docker Deployment

### Build Docker Image

```bash
docker build -t helix-discord-bot:latest .
```

### Run in Docker

```bash
docker run -d \
  --name helix-bot \
  -e DISCORD_BOT_TOKEN=your_token \
  -e HELIX_API_KEY=your_key \
  -e HELIX_API_URL=https://api.helix.example.com \
  helix-discord-bot:latest
```

### View Logs

```bash
docker logs -f helix-bot
```

---

## Kubernetes Deployment

### Create ConfigMap

```bash
kubectl create configmap helix-bot-config \
  --from-literal=BOT_COMMAND_PREFIX=! \
  --from-literal=LOG_LEVEL=INFO
```

### Create Secret

```bash
kubectl create secret generic helix-bot-secrets \
  --from-literal=DISCORD_BOT_TOKEN=your_token \
  --from-literal=HELIX_API_KEY=your_key
```

### Deploy

```bash
kubectl apply -f k8s/deployment.yaml
```

---

## Testing

### Run Tests

```bash
pytest tests/
```

### Run Tests with Coverage

```bash
pytest tests/ --cov=discord_bot_src --cov-report=html
```

### Run Specific Test

```bash
pytest tests/test_bot_core.py::test_bot_initialization
```

---

## Troubleshooting

### Bot Not Responding

1. Verify bot token is correct in `.env`
2. Check bot has send message permission in the channel
3. Ensure bot is online (check Discord Developer Portal)
4. Check logs: `tail -f bot.log`

### Connection Errors

```
discord.errors.HTTPException: 429 Too Many Requests
```

The bot is being rate limited. Wait a few minutes before restarting.

### Memory Issues

If bot is using too much memory:

1. Check memory service configuration
2. Clear old memory entries: `!clear_memory`
3. Restart the bot

### Helix API Errors

```
Error connecting to Helix API
```

1. Verify `HELIX_API_URL` is correct
2. Verify `HELIX_API_KEY` is valid
3. Check Helix API is running and accessible

---

## Development

### Adding a New Command

Create a new file in `discord_bot_src/commands/`:

```python
# discord_bot_src/commands/my_commands.py
from discord.ext import commands

class MyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="mycommand")
    async def my_command(self, ctx, *, argument: str):
        """My custom command."""
        await ctx.send(f"You said: {argument}")

async def setup(bot):
    await bot.add_cog(MyCommands(bot))
```

The command will be automatically loaded when the bot starts.

### Code Style

Follow PEP 8 style guide:

```bash
# Format code
black discord_bot_src/

# Check style
flake8 discord_bot_src/

# Type checking
mypy discord_bot_src/
```

---

## Monitoring

### Check Bot Status

```
!status
```

### View Performance Metrics

```
!metrics
```

### View Command Statistics

```
!stats
```

---

## Updating

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Update Bot Code

```bash
git pull origin main
pip install -r requirements.txt
```

---

## Support

For issues and questions:

1. Check the [GitHub Issues](https://github.com/Deathcharge/helix-discord-bot/issues)
2. Review the [API Reference](API_REFERENCE.md)
3. Check the [Troubleshooting](#troubleshooting) section
4. Create a new issue with detailed information

---

## Next Steps

1. **Customize Commands**: Add your own commands
2. **Integrate Agents**: Connect to Helix agents
3. **Setup Monitoring**: Configure performance monitoring
4. **Deploy to Production**: Use Docker or Kubernetes
5. **Join Community**: Share your bot with others

---

**Last Updated**: April 9, 2026  
**Version**: 1.0  
**Status**: Production Ready
