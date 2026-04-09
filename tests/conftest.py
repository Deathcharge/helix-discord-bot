"""
Comprehensive Pytest Configuration and Fixtures for Helix Discord Bot

Provides mocks, fixtures, and utilities for testing all bot components.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "command: mark test as command test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# =============================================================================
# EVENT LOOP FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# DISCORD BOT MOCKS
# =============================================================================

@pytest.fixture
def mock_bot():
    """Create mock Discord bot."""
    bot = AsyncMock()
    bot.user = Mock(name="HelixBot", id=123456789)
    bot.latency = 0.05
    bot.guilds = []
    bot.cogs = {}
    bot.commands = {}
    bot.add_cog = AsyncMock()
    bot.remove_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.unload_extension = AsyncMock()
    bot.close = AsyncMock()
    bot.wait_until_ready = AsyncMock()
    return bot


@pytest.fixture
def mock_context():
    """Create mock Discord context."""
    ctx = AsyncMock()
    ctx.bot = AsyncMock()
    ctx.author = Mock(name="TestUser", id=987654321, bot=False)
    ctx.guild = Mock(name="TestGuild", id=111111111)
    ctx.channel = Mock(name="test-channel", id=222222222)
    ctx.message = Mock(id=333333333)
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()
    ctx.invoke = AsyncMock()
    ctx.command = Mock(name="test_command")
    ctx.subcommand_passed = None
    return ctx


@pytest.fixture
def mock_guild():
    """Create mock Discord guild."""
    guild = Mock()
    guild.id = 111111111
    guild.name = "Test Guild"
    guild.owner = Mock(name="GuildOwner", id=444444444)
    guild.members = []
    guild.channels = []
    guild.roles = []
    guild.get_member = Mock(return_value=None)
    guild.get_channel = Mock(return_value=None)
    return guild


@pytest.fixture
def mock_member():
    """Create mock Discord member."""
    member = Mock()
    member.id = 987654321
    member.name = "TestUser"
    member.bot = False
    member.roles = []
    member.guild = Mock(id=111111111)
    member.top_role = Mock(position=0)
    return member


@pytest.fixture
def mock_message():
    """Create mock Discord message."""
    message = Mock()
    message.id = 333333333
    message.author = Mock(name="TestUser", id=987654321, bot=False)
    message.guild = Mock(id=111111111)
    message.channel = Mock(id=222222222)
    message.content = "test message"
    message.created_at = Mock()
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    message.add_reaction = AsyncMock()
    message.remove_reaction = AsyncMock()
    return message


# =============================================================================
# BOT COMPONENT MOCKS
# =============================================================================

@pytest.fixture
def mock_memory_service():
    """Create mock memory service."""
    service = AsyncMock()
    service.store_memory = AsyncMock(return_value=True)
    service.retrieve_memory = AsyncMock(return_value={"data": "test"})
    service.clear_memory = AsyncMock(return_value=True)
    service.get_memory_stats = AsyncMock(return_value={"size": 0})
    return service


@pytest.fixture
def mock_agent_factory():
    """Create mock agent factory."""
    factory = Mock()
    factory.create_agent = Mock(return_value=Mock(name="TestAgent", id="agent_001"))
    factory.create_swarm = Mock(return_value=Mock(agents=[]))
    factory.get_agent = Mock(return_value=Mock(name="TestAgent"))
    return factory


@pytest.fixture
def mock_performance_monitor():
    """Create mock performance monitor."""
    monitor = Mock()
    monitor.get_latency = Mock(return_value=0.05)
    monitor.get_memory_usage = Mock(return_value={"rss": 100000000})
    monitor.get_cpu_usage = Mock(return_value=5.0)
    monitor.get_command_stats = Mock(return_value={"total": 100, "success": 95})
    return monitor


@pytest.fixture
def mock_agent_swarm():
    """Create mock agent swarm."""
    swarm = AsyncMock()
    swarm.agents = []
    swarm.add_agent = AsyncMock(return_value=True)
    swarm.remove_agent = AsyncMock(return_value=True)
    swarm.execute_task = AsyncMock(return_value={"status": "success"})
    swarm.get_status = AsyncMock(return_value={"active_agents": 0})
    return swarm


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_command_config():
    """Create sample command configuration."""
    return {
        "name": "test_command",
        "description": "Test command",
        "aliases": ["tc"],
        "permissions": ["send_messages"],
        "cooldown": 5,
        "enabled": True
    }


@pytest.fixture
def sample_user_data():
    """Create sample user data."""
    return {
        "user_id": 987654321,
        "username": "TestUser",
        "commands_used": 10,
        "last_command": "test_command",
        "reputation": 100,
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_guild_data():
    """Create sample guild data."""
    return {
        "guild_id": 111111111,
        "guild_name": "Test Guild",
        "member_count": 100,
        "command_prefix": "!",
        "language": "en",
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_agent_config():
    """Create sample agent configuration."""
    return {
        "agent_id": "agent_001",
        "agent_name": "TestAgent",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": "You are a helpful assistant"
    }


# =============================================================================
# COMMAND TEST FIXTURES
# =============================================================================

@pytest.fixture
def command_test_setup(mock_bot, mock_context, mock_memory_service):
    """Setup for command tests."""
    return {
        "bot": mock_bot,
        "ctx": mock_context,
        "memory": mock_memory_service
    }


@pytest.fixture
def admin_command_setup(mock_bot, mock_context, mock_member):
    """Setup for admin command tests."""
    mock_context.author = mock_member
    mock_context.author.guild_permissions = Mock(administrator=True)
    return {
        "bot": mock_bot,
        "ctx": mock_context,
        "member": mock_member
    }


@pytest.fixture
def moderation_command_setup(mock_bot, mock_context, mock_guild):
    """Setup for moderation command tests."""
    mock_context.guild = mock_guild
    mock_context.author.guild_permissions = Mock(moderate_members=True)
    return {
        "bot": mock_bot,
        "ctx": mock_context,
        "guild": mock_guild
    }


# =============================================================================
# INTEGRATION TEST FIXTURES
# =============================================================================

@pytest.fixture
def bot_integration_setup(mock_bot, mock_memory_service, mock_agent_factory):
    """Setup for bot integration tests."""
    mock_bot.memory_service = mock_memory_service
    mock_bot.agent_factory = mock_agent_factory
    return {
        "bot": mock_bot,
        "memory": mock_memory_service,
        "factory": mock_agent_factory
    }


@pytest.fixture
def multi_agent_setup(mock_bot, mock_agent_swarm, mock_agent_factory):
    """Setup for multi-agent tests."""
    mock_bot.agent_swarm = mock_agent_swarm
    mock_bot.agent_factory = mock_agent_factory
    return {
        "bot": mock_bot,
        "swarm": mock_agent_swarm,
        "factory": mock_agent_factory
    }


# =============================================================================
# PERFORMANCE TEST FIXTURES
# =============================================================================

@pytest.fixture
def performance_timer():
    """Create performance timer."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            import time
            self.start_time = time.time()
        
        def stop(self):
            import time
            self.end_time = time.time()
            return self.end_time - self.start_time
    
    return Timer()


@pytest.fixture
def mock_performance_data():
    """Create mock performance data."""
    return {
        "command_latency": 0.05,
        "memory_usage": 100000000,
        "cpu_usage": 5.0,
        "uptime": 3600,
        "commands_executed": 100,
        "errors": 5
    }


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def mock_http_client():
    """Create mock HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=Mock(status=200, json=AsyncMock(return_value={})))
    client.post = AsyncMock(return_value=Mock(status=200, json=AsyncMock(return_value={})))
    client.put = AsyncMock(return_value=Mock(status=200, json=AsyncMock(return_value={})))
    client.delete = AsyncMock(return_value=Mock(status=200))
    return client


@pytest.fixture
def mock_database():
    """Create mock database."""
    db = AsyncMock()
    db.connect = AsyncMock(return_value=True)
    db.disconnect = AsyncMock(return_value=True)
    db.query = AsyncMock(return_value=[])
    db.insert = AsyncMock(return_value={"id": 1})
    db.update = AsyncMock(return_value=True)
    db.delete = AsyncMock(return_value=True)
    return db


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


# =============================================================================
# ASSERTION HELPERS
# =============================================================================

@pytest.fixture
def assertion_helpers():
    """Provide assertion helper functions."""
    class AssertionHelpers:
        @staticmethod
        def assert_command_success(result):
            assert result is not None
            assert "status" in result
            assert result["status"] == "success"
        
        @staticmethod
        def assert_command_error(result):
            assert result is not None
            assert "status" in result
            assert result["status"] == "error"
        
        @staticmethod
        def assert_valid_response(response):
            assert response is not None
            assert isinstance(response, (dict, str))
        
        @staticmethod
        def assert_async_called(mock_obj):
            assert mock_obj.called
            assert mock_obj.call_count > 0
    
    return AssertionHelpers()


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test."""
    yield
    # Cleanup code here if needed
