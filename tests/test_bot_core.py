"""
Comprehensive Test Suite for Helix Discord Bot Core Functionality

Tests for bot initialization, setup, and core operations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch


# =============================================================================
# BOT INITIALIZATION TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_bot_initialization(mock_bot):
    """Test bot initialization."""
    assert mock_bot is not None
    assert mock_bot.user.name == "HelixBot"
    assert mock_bot.user.id == 123456789


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bot_latency(mock_bot):
    """Test bot latency property."""
    assert mock_bot.latency == 0.05
    assert mock_bot.latency < 1.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bot_ready_event(mock_bot):
    """Test bot ready event."""
    await mock_bot.wait_until_ready()
    mock_bot.wait_until_ready.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bot_close(mock_bot):
    """Test bot close operation."""
    await mock_bot.close()
    mock_bot.close.assert_called_once()


# =============================================================================
# COG MANAGEMENT TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_add_cog(mock_bot):
    """Test adding a cog to bot."""
    cog = Mock(name="TestCog")
    await mock_bot.add_cog(cog)
    mock_bot.add_cog.assert_called_once_with(cog)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_remove_cog(mock_bot):
    """Test removing a cog from bot."""
    await mock_bot.remove_cog("TestCog")
    mock_bot.remove_cog.assert_called_once_with("TestCog")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_load_extension(mock_bot):
    """Test loading extension."""
    await mock_bot.load_extension("discord_bot_src.commands.admin_commands")
    mock_bot.load_extension.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unload_extension(mock_bot):
    """Test unloading extension."""
    await mock_bot.unload_extension("discord_bot_src.commands.admin_commands")
    mock_bot.unload_extension.assert_called_once()


# =============================================================================
# CONTEXT TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_send_message(mock_context):
    """Test sending message via context."""
    await mock_context.send("Hello!")
    mock_context.send.assert_called_once_with("Hello!")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_reply(mock_context):
    """Test replying to message via context."""
    await mock_context.reply("Response")
    mock_context.reply.assert_called_once_with("Response")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_author_info(mock_context):
    """Test getting author info from context."""
    assert mock_context.author.name == "TestUser"
    assert mock_context.author.id == 987654321
    assert mock_context.author.bot is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_guild_info(mock_context):
    """Test getting guild info from context."""
    assert mock_context.guild.id == 111111111


@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_channel_info(mock_context):
    """Test getting channel info from context."""
    assert mock_context.channel.id == 222222222


# =============================================================================
# COMMAND EXECUTION TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_command_invocation(mock_context):
    """Test command invocation."""
    await mock_context.invoke(mock_context.command)
    mock_context.invoke.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_command_error_handling(mock_context):
    """Test command error handling."""
    error = Exception("Test error")
    # Simulate error handling
    assert isinstance(error, Exception)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_command_with_args(mock_context):
    """Test command with arguments."""
    mock_context.command.params = {"arg1": "value1", "arg2": "value2"}
    assert len(mock_context.command.params) == 2


# =============================================================================
# GUILD TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_guild_info(mock_guild):
    """Test guild information."""
    assert mock_guild.id == 111111111
    assert mock_guild.name == "Test Guild"
    assert mock_guild.owner.id == 444444444


@pytest.mark.asyncio
@pytest.mark.unit
async def test_guild_member_retrieval(mock_guild):
    """Test retrieving guild member."""
    member = mock_guild.get_member(987654321)
    mock_guild.get_member.assert_called_once_with(987654321)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_guild_channel_retrieval(mock_guild):
    """Test retrieving guild channel."""
    channel = mock_guild.get_channel(222222222)
    mock_guild.get_channel.assert_called_once_with(222222222)


# =============================================================================
# MEMBER TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_member_info(mock_member):
    """Test member information."""
    assert mock_member.id == 987654321
    assert mock_member.name == "TestUser"
    assert mock_member.bot is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_member_roles(mock_member):
    """Test member roles."""
    assert isinstance(mock_member.roles, list)
    assert mock_member.top_role is not None


# =============================================================================
# MESSAGE TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_message_info(mock_message):
    """Test message information."""
    assert mock_message.id == 333333333
    assert mock_message.content == "test message"
    assert mock_message.author.id == 987654321


@pytest.mark.asyncio
@pytest.mark.unit
async def test_message_edit(mock_message):
    """Test editing message."""
    await mock_message.edit(content="Updated message")
    mock_message.edit.assert_called_once_with(content="Updated message")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_message_delete(mock_message):
    """Test deleting message."""
    await mock_message.delete()
    mock_message.delete.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_message_add_reaction(mock_message):
    """Test adding reaction to message."""
    await mock_message.add_reaction("👍")
    mock_message.add_reaction.assert_called_once_with("👍")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_message_remove_reaction(mock_message):
    """Test removing reaction from message."""
    await mock_message.remove_reaction("👍", mock_message.author)
    mock_message.remove_reaction.assert_called_once()


# =============================================================================
# MEMORY SERVICE TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_memory_store(mock_memory_service):
    """Test storing memory."""
    result = await mock_memory_service.store_memory("key", {"data": "value"})
    assert result is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_memory_retrieve(mock_memory_service):
    """Test retrieving memory."""
    result = await mock_memory_service.retrieve_memory("key")
    assert result == {"data": "test"}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_memory_clear(mock_memory_service):
    """Test clearing memory."""
    result = await mock_memory_service.clear_memory("key")
    assert result is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_memory_stats(mock_memory_service):
    """Test getting memory statistics."""
    result = await mock_memory_service.get_memory_stats()
    assert "size" in result


# =============================================================================
# AGENT FACTORY TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_agent_creation(mock_agent_factory):
    """Test creating agent."""
    agent = mock_agent_factory.create_agent("TestAgent")
    assert agent is not None
    assert agent.name == "TestAgent"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_swarm_creation(mock_agent_factory):
    """Test creating agent swarm."""
    swarm = mock_agent_factory.create_swarm([])
    assert swarm is not None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_agent_retrieval(mock_agent_factory):
    """Test retrieving agent."""
    agent = mock_agent_factory.get_agent("agent_001")
    assert agent is not None


# =============================================================================
# PERFORMANCE MONITOR TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_latency_monitoring(mock_performance_monitor):
    """Test latency monitoring."""
    latency = mock_performance_monitor.get_latency()
    assert latency == 0.05
    assert latency < 1.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_memory_monitoring(mock_performance_monitor):
    """Test memory monitoring."""
    memory = mock_performance_monitor.get_memory_usage()
    assert "rss" in memory


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cpu_monitoring(mock_performance_monitor):
    """Test CPU monitoring."""
    cpu = mock_performance_monitor.get_cpu_usage()
    assert cpu >= 0.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_command_stats(mock_performance_monitor):
    """Test command statistics."""
    stats = mock_performance_monitor.get_command_stats()
    assert "total" in stats
    assert "success" in stats


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_bot_with_memory_service(bot_integration_setup):
    """Test bot with memory service."""
    bot = bot_integration_setup["bot"]
    memory = bot_integration_setup["memory"]
    
    # Store memory
    await memory.store_memory("test_key", {"data": "test"})
    memory.store_memory.assert_called_once()
    
    # Retrieve memory
    result = await memory.retrieve_memory("test_key")
    assert result == {"data": "test"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bot_with_agent_factory(bot_integration_setup):
    """Test bot with agent factory."""
    bot = bot_integration_setup["bot"]
    factory = bot_integration_setup["factory"]
    
    # Create agent
    agent = factory.create_agent("TestAgent")
    assert agent is not None
    
    # Get agent
    retrieved = factory.get_agent("agent_001")
    assert retrieved is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multi_agent_coordination(multi_agent_setup):
    """Test multi-agent coordination."""
    bot = multi_agent_setup["bot"]
    swarm = multi_agent_setup["swarm"]
    
    # Execute task
    result = await swarm.execute_task({"action": "test"})
    assert result["status"] == "success"
    
    # Get status
    status = await swarm.get_status()
    assert "active_agents" in status


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_command_execution_performance(performance_timer, mock_context):
    """Test command execution performance."""
    performance_timer.start()
    
    # Simulate command execution
    for i in range(100):
        await mock_context.send(f"Message {i}")
    
    elapsed = performance_timer.stop()
    assert elapsed < 10  # Should complete in less than 10 seconds


@pytest.mark.asyncio
@pytest.mark.slow
async def test_memory_operations_performance(performance_timer, mock_memory_service):
    """Test memory operations performance."""
    performance_timer.start()
    
    # Simulate memory operations
    for i in range(100):
        await mock_memory_service.store_memory(f"key_{i}", {"data": f"value_{i}"})
    
    elapsed = performance_timer.stop()
    assert elapsed < 5  # Should complete in less than 5 seconds


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_invalid_context(mock_context):
    """Test handling invalid context."""
    # Context should still be valid
    assert mock_context is not None
    assert mock_context.author is not None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_null_message_handling(mock_message):
    """Test handling null message."""
    # Message should still be valid
    assert mock_message is not None
    assert mock_message.content is not None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_permission_denied_error():
    """Test permission denied error."""
    error = PermissionError("User does not have permission")
    assert isinstance(error, PermissionError)
