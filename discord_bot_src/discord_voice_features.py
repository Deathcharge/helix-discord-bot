"""
Voice channel integration for the Helix Discord bot including:
- Voice channel join/leave
- Text-to-Speech (TTS) for agent responses
- Voice command recognition
- Audio transcription
- Voice activity detection
"""

import asyncio
import io
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import cachetools
import discord
import openai
from discord.ext import commands

logger = logging.getLogger(__name__)

# Optional voice dependencies
try:
    from gtts import gTTS

    HAS_GTTS_IMPORT = True
except ImportError:
    gTTS = None  # type: ignore[assignment,misc]
    HAS_GTTS_IMPORT = False
    logger.warning("gTTS not installed — text-to-speech features disabled")

try:
    from pydub import AudioSegment

    HAS_PYDUB_IMPORT = True
except ImportError:
    AudioSegment = None  # type: ignore[assignment,misc]
    HAS_PYDUB_IMPORT = False
    logger.warning("pydub not installed — audio processing features disabled")

# Optional imports for voice features
try:
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

try:
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

HAS_GOOGLE_TTS = HAS_GTTS

try:
    import speech_recognition as sr

    HAS_SPEECH_RECOGNITION = True
except ImportError:
    sr = None
    HAS_SPEECH_RECOGNITION = False

try:
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


class VoiceState(Enum):
    """Voice connection states"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PLAYING = "playing"
    LISTENING = "listening"
    ERROR = "error"


@dataclass
class VoiceSession:
    """Represents a voice session in a channel"""

    session_id: str
    guild_id: int
    channel_id: int
    voice_client: discord.VoiceClient | None = None
    state: VoiceState = VoiceState.DISCONNECTED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    audio_queue: list[str] = field(default_factory=list)
    transcription_enabled: bool = False
    auto_respond: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "queue_length": len(self.audio_queue),
            "transcription_enabled": self.transcription_enabled,
            "auto_respond": self.auto_respond,
        }


class TextToSpeech:
    """Text-to-Speech engine for voice responses"""

    def __init__(self):
        self.cache_dir = tempfile.mkdtemp(prefix="helix_tts_")
        # Bounded cache with TTL to prevent memory leak from unbounded dict
        # Max 512 entries, 1 hour TTL - evicts oldest entries automatically
        self._cache: cachetools.TTLCache[str, str] = cachetools.TTLCache(maxsize=512, ttl=3600)

    async def synthesize(self, text: str, language: str = "en", slow: bool = False) -> str | None:
        """Convert text to speech audio file"""
        # Check cache
        cache_key = f"{text}_{language}_{slow}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if HAS_GOOGLE_TTS:
                # Use Google TTS
                tts = gTTS(text=text, lang=language, slow=slow)
                filename = os.path.join(self.cache_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")
                tts.save(filename)
                self._cache[cache_key] = filename
                return filename
            elif HAS_OPENAI:
                # Use OpenAI TTS
                client = openai.OpenAI()
                response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
                filename = os.path.join(self.cache_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")
                response.stream_to_file(filename)
                self._cache[cache_key] = filename
                return filename
            else:
                return None
        except Exception as e:
            logger.error("TTS Error: %s", e)
            return None

    def clear_cache(self):
        """Clear the TTS cache"""
        for filepath in self._cache.values():
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.warning("Failed to remove cached file %s: %s", filepath, e)
        self._cache.clear()

    def cleanup(self):
        """Cleanup temporary files"""
        try:
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to cleanup voice features: %s", e)


class SpeechRecognition:
    """Speech recognition for voice commands"""

    def __init__(self):
        if HAS_SPEECH_RECOGNITION:
            self.recognizer = sr.Recognizer()
        else:
            self.recognizer = None

    async def transcribe_file(self, audio_path: str, language: str = "en-US") -> str | None:
        """Transcribe audio file to text"""
        if not self.recognizer:
            return await self._transcribe_with_openai(audio_path)

        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)

            # Try Google Speech Recognition first
            try:
                text = self.recognizer.recognize_google(audio, language=language)
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                # Fall back to OpenAI Whisper
                return await self._transcribe_with_openai(audio_path)
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return None

    async def _transcribe_with_openai(self, audio_path: str) -> str | None:
        """Transcribe using OpenAI Whisper"""
        if not HAS_OPENAI:
            return None

        try:
            client = openai.OpenAI()
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            return transcript.text
        except Exception as e:
            logger.error("OpenAI transcription error: %s", e)
            return None

    async def transcribe_bytes(self, audio_data: bytes, format: str = "wav") -> str | None:
        """Transcribe audio bytes to text"""
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            result = await self.transcribe_file(temp_path)
            return result
        finally:
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning("Failed to remove temp file %s: %s", temp_path, e)


class VoiceActivityDetector:
    """Detects voice activity in audio streams"""

    def __init__(self, threshold: float = 0.02):
        self.threshold = threshold
        self.is_speaking = False
        self.speech_start_time: datetime | None = None
        self.silence_duration = 0.0
        self.min_speech_duration = 0.5  # seconds
        self.max_silence_duration = 1.5  # seconds

    def process_audio(self, audio_data: bytes) -> bool:
        """Process audio data and detect speech"""
        if not HAS_PYDUB:
            return False

        try:
            audio = AudioSegment.from_raw(io.BytesIO(audio_data), sample_width=2, frame_rate=48000, channels=2)

            # Calculate RMS (volume level)
            rms = audio.rms / 32768.0  # Normalize to 0-1

            if rms > self.threshold:
                if not self.is_speaking:
                    self.is_speaking = True
                    self.speech_start_time = datetime.now(UTC)
                self.silence_duration = 0.0
            else:
                if self.is_speaking:
                    self.silence_duration += len(audio_data) / (48000 * 2 * 2)
                    if self.silence_duration > self.max_silence_duration:
                        self.is_speaking = False
                        return True  # Speech ended

            return False
        except Exception as e:
            logger.error("VAD error: %s", e)
            return False


class VoiceManager:
    """Manages voice connections and features"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, VoiceSession] = {}  # guild_id -> session
        self.tts = TextToSpeech()
        self.stt = SpeechRecognition()
        self.vad = VoiceActivityDetector()
        self._audio_buffers: dict[int, list[bytes]] = {}  # user_id -> audio chunks

    async def join_channel(
        self,
        channel: discord.VoiceChannel,
        transcription: bool = False,
        auto_respond: bool = False,
    ) -> VoiceSession:
        """Join a voice channel"""
        guild_id = channel.guild.id

        # Check if already in a channel in this guild
        if guild_id in self.sessions:
            existing = self.sessions[guild_id]
            if existing.voice_client and existing.voice_client.is_connected():
                if existing.channel_id != channel.id:
                    await existing.voice_client.move_to(channel)
                    existing.channel_id = channel.id
                return existing

        # Create new session
        session = VoiceSession(
            session_id=str(uuid.uuid4()),
            guild_id=guild_id,
            channel_id=channel.id,
            state=VoiceState.CONNECTING,
            transcription_enabled=transcription,
            auto_respond=auto_respond,
        )

        try:
            voice_client = await channel.connect()
            session.voice_client = voice_client
            session.state = VoiceState.CONNECTED

            # Set up audio sink for transcription if enabled
            if transcription and HAS_NACL:
                # Note: Discord.py doesn't natively support receiving audio
                # This would require additional setup with voice receive
                pass

            self.sessions[guild_id] = session
            return session
        except Exception as e:
            session.state = VoiceState.ERROR
            raise e

    async def leave_channel(self, guild_id: int) -> bool:
        """Leave the voice channel in a guild"""
        if guild_id not in self.sessions:
            return False

        session = self.sessions[guild_id]
        if session.voice_client:
            await session.voice_client.disconnect()

        session.state = VoiceState.DISCONNECTED
        del self.sessions[guild_id]
        return True

    async def speak(self, guild_id: int, text: str, language: str = "en", wait: bool = True) -> bool:
        """Speak text in the voice channel"""
        if guild_id not in self.sessions:
            return False

        session = self.sessions[guild_id]
        if not session.voice_client or not session.voice_client.is_connected():
            return False

        # Generate TTS audio
        audio_path = await self.tts.synthesize(text, language)
        if not audio_path:
            return False

        try:
            audio_source = discord.FFmpegPCMAudio(audio_path)

            # Play audio
            session.state = VoiceState.PLAYING
            session.voice_client.play(audio_source)

            if wait:
                while session.voice_client.is_playing():
                    await asyncio.sleep(0.1)

            session.state = VoiceState.CONNECTED
            session.last_activity = datetime.now(UTC)
            return True
        except Exception as e:
            logger.error("Voice playback error: %s", e)
            session.state = VoiceState.ERROR
            return False

    async def play_audio(self, guild_id: int, audio_path: str, wait: bool = True) -> bool:
        """Play an audio file in the voice channel"""
        if guild_id not in self.sessions:
            return False

        session = self.sessions[guild_id]
        if not session.voice_client or not session.voice_client.is_connected():
            return False

        try:
            audio_source = discord.FFmpegPCMAudio(audio_path)
            session.state = VoiceState.PLAYING
            session.voice_client.play(audio_source)

            if wait:
                while session.voice_client.is_playing():
                    await asyncio.sleep(0.1)

            session.state = VoiceState.CONNECTED
            return True
        except Exception as e:
            logger.error("Audio playback error: %s", e)
            return False

    def get_session(self, guild_id: int) -> VoiceSession | None:
        """Get the voice session for a guild"""
        return self.sessions.get(guild_id)

    def get_all_sessions(self) -> list[VoiceSession]:
        """Get all active voice sessions"""
        return list(self.sessions.values())

    async def cleanup(self):
        """Cleanup all voice connections"""
        for guild_id in list(self.sessions.keys()):
            await self.leave_channel(guild_id)
        self.tts.cleanup()


class VoiceCommandsCog(commands.Cog):
    """Discord cog for voice commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_manager = VoiceManager(bot)

    @commands.command(name="join", aliases=["connect"])
    async def join_voice(self, ctx: commands.Context):
        """Join the user's voice channel"""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return

        channel = ctx.author.voice.channel

        try:
            await ctx.send(f"🎤 Joined **{channel.name}**!")
        except Exception as e:
            await ctx.send(f"❌ Failed to join: {e}")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    async def leave_voice(self, ctx: commands.Context):
        """Leave the voice channel"""
        if await self.voice_manager.leave_channel(ctx.guild.id):
            await ctx.send("👋 Left the voice channel!")
        else:
            await ctx.send("❌ Not in a voice channel!")

    @commands.command(name="speak", aliases=["say", "tts"])
    async def speak_text(self, ctx: commands.Context, *, text: str):
        """Speak text in the voice channel"""
        if ctx.guild.id not in self.voice_manager.sessions:
            await ctx.send("❌ Not in a voice channel! Use `!join` first.")
            return

        async with ctx.typing():
            success = await self.voice_manager.speak(ctx.guild.id, text)

        if success:
            await ctx.message.add_reaction("🔊")
        else:
            await ctx.send("❌ Failed to speak. TTS may not be available.")

    @commands.command(name="voicestatus")
    async def voice_status(self, ctx: commands.Context):
        """Show voice session status"""
        session = self.voice_manager.get_session(ctx.guild.id)

        if not session:
            await ctx.send("❌ No active voice session in this server.")
            return

        embed = discord.Embed(title="🎤 Voice Session Status", color=discord.Color.blue())
        embed.add_field(name="State", value=session.state.value, inline=True)
        embed.add_field(name="Channel", value=f"<#{session.channel_id}>", inline=True)
        embed.add_field(
            name="Transcription",
            value="✅ Enabled" if session.transcription_enabled else "❌ Disabled",
            inline=True,
        )
        embed.add_field(
            name="Auto-Respond",
            value="✅ Enabled" if session.auto_respond else "❌ Disabled",
            inline=True,
        )
        embed.add_field(name="Queue Length", value=str(len(session.audio_queue)), inline=True)
        embed.set_footer(text=f"Session ID: {session.session_id[:8]}...")

        await ctx.send(embed=embed)

    @commands.command(name="transcribe")
    async def toggle_transcription(self, ctx: commands.Context):
        """Toggle voice transcription"""
        session = self.voice_manager.get_session(ctx.guild.id)

        if not session:
            await ctx.send("❌ No active voice session!")
            return

        session.transcription_enabled = not session.transcription_enabled
        status = "enabled" if session.transcription_enabled else "disabled"
        await ctx.send(f"🎙️ Transcription {status}!")

    @commands.command(name="autorespond")
    async def toggle_auto_respond(self, ctx: commands.Context):
        """Toggle automatic voice responses"""
        session = self.voice_manager.get_session(ctx.guild.id)

        if not session:
            await ctx.send("❌ No active voice session!")
            return

        session.auto_respond = not session.auto_respond
        status = "enabled" if session.auto_respond else "disabled"
        await ctx.send(f"🤖 Auto-respond {status}!")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        asyncio.create_task(self.voice_manager.cleanup())


# Slash command versions
class VoiceSlashCog(commands.Cog):
    """Slash commands for voice features"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_manager = VoiceManager(bot)

    @discord.app_commands.command(name="voice-join", description="Join your voice channel")
    @discord.app_commands.describe(
        transcription="Enable voice transcription",
        auto_respond="Enable automatic voice responses",
    )
    async def voice_join(
        self,
        interaction: discord.Interaction,
        transcription: bool = False,
        auto_respond: bool = False,
    ):
        """Join the user's voice channel"""
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        await interaction.response.defer()

        try:
            await self.voice_manager.join_voice_channel(channel, transcription=transcription, auto_respond=auto_respond)

            embed = discord.Embed(
                title="🎤 Joined Voice Channel",
                description=f"Connected to **{channel.name}**",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Transcription",
                value="✅ Enabled" if transcription else "❌ Disabled",
                inline=True,
            )
            embed.add_field(
                name="Auto-Respond",
                value="✅ Enabled" if auto_respond else "❌ Disabled",
                inline=True,
            )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to join: {e}")

    @discord.app_commands.command(name="voice-leave", description="Leave the voice channel")
    async def voice_leave(self, interaction: discord.Interaction):
        """Leave the voice channel"""
        if await self.voice_manager.leave_channel(interaction.guild_id):
            await interaction.response.send_message("👋 Left the voice channel!")
        else:
            await interaction.response.send_message("❌ Not in a voice channel!", ephemeral=True)

    @discord.app_commands.command(name="voice-speak", description="Speak text in voice channel")
    @discord.app_commands.describe(text="Text to speak", language="Language code (e.g., en, es, fr)")
    async def voice_speak(self, interaction: discord.Interaction, text: str, language: str = "en"):
        """Speak text in the voice channel"""
        if interaction.guild_id not in self.voice_manager.sessions:
            await interaction.response.send_message(
                "❌ Not in a voice channel! Use `/voice-join` first.", ephemeral=True
            )
            return

        await interaction.response.defer()

        success = await self.voice_manager.speak(interaction.guild_id, text, language=language)

        if success:
            await interaction.followup.send(f"🔊 Speaking: *{text[:100]}{'...' if len(text) > 100 else ''}*")
        else:
            await interaction.followup.send("❌ Failed to speak. TTS may not be available.", ephemeral=True)

    @discord.app_commands.command(name="voice-status", description="Show voice session status")
    async def voice_status(self, interaction: discord.Interaction):
        """Show voice session status"""
        session = self.voice_manager.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("❌ No active voice session in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="🎤 Voice Session Status", color=discord.Color.blue())
        embed.add_field(name="State", value=session.state.value, inline=True)
        embed.add_field(name="Channel", value=f"<#{session.channel_id}>", inline=True)
        embed.add_field(
            name="Transcription",
            value="✅" if session.transcription_enabled else "❌",
            inline=True,
        )
        embed.add_field(
            name="Auto-Respond",
            value="✅" if session.auto_respond else "❌",
            inline=True,
        )
        embed.set_footer(text=f"Session: {session.session_id[:8]}...")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog"""
    await bot.add_cog(VoiceCommandsCog(bot))
    await bot.add_cog(VoiceSlashCog(bot))


# ==================== EXPORTS ====================

__all__ = [
    "SpeechRecognition",
    "TextToSpeech",
    "VoiceActivityDetector",
    "VoiceCommandsCog",
    "VoiceManager",
    "VoiceSession",
    "VoiceSlashCog",
    "VoiceState",
    "setup",
]
