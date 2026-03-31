# Helix Discord Bot

A comprehensive Discord bot powered by the Helix AI ecosystem, featuring multi-agent coordination, advanced commands, and real-time monitoring.

## Features

- **Multi-Agent Coordination** - Agents working together on Discord
- **Advanced Commands** - 50+ commands across multiple categories
- **Real-time Monitoring** - Performance tracking and optimization
- **Content Generation** - Image, text, and creative content
- **Admin & Moderation** - Server management tools
- **Fun Minigames** - Interactive entertainment
- **Portal Deployment** - Deploy Helix portals from Discord
- **Context Management** - Advanced context and memory systems

## Components

- `agent_bot_factory.py` - Bot creation and initialization
- `agent_memory_service.py` - Memory management for agents
- `agent_performance_commands.py` - Performance monitoring
- `commands/` - Command modules (admin, advanced, content, etc.)
- `discord_helix_bot.py` - Main bot implementation

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set up your Discord bot token and Helix configuration in environment variables.

## Usage

```python
from discord_bot_src import HelixBot

bot = HelixBot()
bot.run(token)
```

## Commands

### Admin Commands
- `/admin` - Administrative functions
- `/moderation` - Moderation tools

### Content Commands
- `/image` - Generate images
- `/content` - Create content

### Advanced Commands
- `/advanced` - Advanced AI features
- `/optimization` - System optimization

### Monitoring
- `/monitoring` - Performance monitoring
- `/performance` - Performance metrics

## License

Apache 2.0 + Proprietary Commercial License

See LICENSING.md for details.
