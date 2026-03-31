# Helix Discord Bot

A comprehensive, production-ready Discord bot powered by the Helix AI ecosystem. Features multi-agent coordination, advanced commands, real-time monitoring, and seamless integration with Helix's autonomous systems.

## Overview

The Helix Discord Bot brings the power of multi-agent AI orchestration to Discord servers. With 50+ commands spanning admin, content generation, advanced AI features, performance monitoring, and more, it transforms Discord into a hub for AI-powered collaboration and automation.

## Key Features

- **Multi-Agent Coordination** - Agents working together on Discord workflows
- **50+ Advanced Commands** - Organized across 15+ command modules
- **Real-time Monitoring** - Performance tracking and system optimization
- **Content Generation** - Images, text, and creative content
- **Admin & Moderation** - Server management and moderation tools
- **Voice Features** - Audio integration and voice commands
- **Memory Management** - Persistent context and conversation history
- **Webhook Integration** - Seamless Discord integration
- **Portal Deployment** - Deploy Helix portals directly from Discord
- **Fun Minigames** - Interactive entertainment and engagement

## Architecture

```
discord_bot_src/
├── agent_bot_factory.py              # Bot creation and initialization
├── agent_memory_service.py           # Memory management for agents
├── agent_performance_commands.py     # Performance monitoring
├── discord_bot_helix.py              # Main bot implementation
├── discord_agent_swarm_integration.py # Agent coordination
├── discord_multi_agent_enhancements.py # Multi-agent features
├── commands/                         # 15 command modules
│   ├── admin_commands.py
│   ├── advanced_commands.py
│   ├── content_commands.py
│   ├── image_commands.py
│   ├── moderation_commands.py
│   ├── monitoring_commands.py
│   ├── optimization_commands.py
│   ├── voice_commands.py
│   └── ...more
└── ...additional modules
```

## Installation

### Prerequisites
- Python 3.9+
- Discord.py library
- Helix ecosystem components

### Setup

```bash
# Clone the repository
git clone https://github.com/Deathcharge/helix-discord-bot.git
cd helix-discord-bot

# Install dependencies
pip install -r requirements.txt

# Configure your bot token
export DISCORD_BOT_TOKEN="your_token_here"

# Run the bot
python discord_bot_src/discord_bot_helix.py
```

## Command Categories

### Admin Commands
Administrative functions for server management and configuration.

### Advanced Commands
Leverage advanced AI capabilities for complex tasks.

### Content Commands
Generate and manage content (images, text, creative).

### Image Commands
Image generation, manipulation, and analysis.

### Moderation Commands
Server moderation and user management tools.

### Monitoring Commands
Real-time performance monitoring and analytics.

### Optimization Commands
System optimization and performance tuning.

### Voice Commands
Voice integration and audio features.

### Fun Minigames
Interactive games and entertainment.

### Portal Deployment
Deploy Helix portals from Discord.

## Integration

The bot integrates seamlessly with:
- **Helix Agent Swarm** - Multi-agent coordination
- **Routine Engine** - Workflow automation
- **UCF Protocol** - Consciousness metrics
- **Helix Core** - LLM reasoning

## Configuration

Set environment variables for:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `HELIX_API_KEY` - Helix API credentials
- `HELIX_API_URL` - Helix API endpoint

## Development

### Adding New Commands

Create a new file in `discord_bot_src/commands/`:

```python
import discord
from discord.ext import commands

class MyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def mycommand(self, ctx):
        """My custom command"""
        await ctx.send("Hello!")

async def setup(bot):
    await bot.add_cog(MyCommands(bot))
```

### Testing

```bash
# Run with test token
python discord_bot_src/discord_bot_helix.py --test
```

## Performance

The bot is optimized for:
- Low latency command execution
- Efficient memory management
- Scalable multi-agent coordination
- Real-time monitoring and analytics

## Security

- Secure token management
- Permission-based command access
- Rate limiting and abuse prevention
- Encrypted credential storage

## License

Dual Licensed:
- **Apache 2.0** - For open-source use
- **Proprietary Commercial** - For enterprise deployments

See LICENSE and LICENSE.PROPRIETARY for details.

## Support

For issues, feature requests, or contributions:
- Open an issue on GitHub
- Check the documentation
- Review command examples

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See CONTRIBUTING.md for guidelines.

## Roadmap

- [ ] Advanced scheduling system
- [ ] Custom command builder
- [ ] Analytics dashboard
- [ ] Multi-server coordination
- [ ] Advanced AI training
- [ ] Community marketplace

## Credits

Built with the Helix Collective ecosystem and powered by advanced AI coordination.

---

**Tat Tvam Asi** 🕉️ - Thou Art That
