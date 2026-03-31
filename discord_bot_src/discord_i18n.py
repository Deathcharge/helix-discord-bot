"""
Discord Bot Internationalization (i18n) System
Multi-language support for Discord commands and responses.
"""

# ruff: noqa: RUF001  # Multilingual strings intentionally contain non-ASCII lookalike chars

import logging
from enum import Enum

from apps.backend.i18n_system import Language, get_i18n

logger = logging.getLogger(__name__)


class DiscordLanguage(Enum):
    """Discord-supported languages (subset of full i18n)."""

    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE_SIMPLIFIED = "zh-CN"
    JAPANESE = "ja"
    KOREAN = "ko"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    ITALIAN = "it"
    TURKISH = "tr"


class DiscordI18n:
    """Discord bot i18n system."""

    def __init__(self):
        self.i18n = get_i18n()
        self.guild_languages: dict[int, Language] = {}  # guild_id -> language
        self.user_languages: dict[int, Language] = {}  # user_id -> language
        self._load_discord_translations()

    def _load_discord_translations(self):
        """Load Discord-specific translations."""

        # Command descriptions
        self.i18n.add_translation(
            "discord.cmd.help",
            {
                "en": "Show help information",
                "es": "Mostrar información de ayuda",
                "fr": "Afficher les informations d'aide",
                "de": "Hilfeinformationen anzeigen",
                "zh-CN": "显示帮助信息",
                "ja": "ヘルプ情報を表示",
                "ko": "도움말 정보 표시",
                "pt": "Mostrar informações de ajuda",
                "ru": "Показать справочную информацию",
                "it": "Mostra informazioni di aiuto",
                "tr": "Yardım bilgilerini göster",
            },
        )

        self.i18n.add_translation(
            "discord.cmd.agent",
            {
                "en": "Create or manage AI agents",
                "es": "Crear o gestionar agentes de IA",
                "fr": "Créer ou gérer des agents IA",
                "de": "KI-Agenten erstellen oder verwalten",
                "zh-CN": "创建或管理AI智能体",
                "ja": "AIエージェントを作成または管理",
                "ko": "AI 에이전트 생성 또는 관리",
                "pt": "Criar ou gerenciar agentes de IA",
                "ru": "Создать или управлять AI-агентами",
                "it": "Crea o gestisci agenti AI",
                "tr": "AI ajanları oluştur veya yönet",
            },
        )

        self.i18n.add_translation(
            "discord.cmd.chat",
            {
                "en": "Chat with an AI agent",
                "es": "Chatear con un agente de IA",
                "fr": "Discuter avec un agent IA",
                "de": "Mit einem KI-Agenten chatten",
                "zh-CN": "与AI智能体聊天",
                "ja": "AIエージェントとチャット",
                "ko": "AI 에이전트와 채팅",
                "pt": "Conversar com um agente de IA",
                "ru": "Общаться с AI-агентом",
                "it": "Chatta con un agente AI",
                "tr": "Bir AI ajanıyla sohbet et",
            },
        )

        self.i18n.add_translation(
            "discord.cmd.system",
            {
                "en": "View system coordination metrics",
                "es": "Ver métricas de conciencia cuántica",
                "fr": "Voir les métriques de conscience quantique",
                "de": "Quantenbewusstseinsmetriken anzeigen",
                "zh-CN": "查看量子意识指标",
                "ja": "量子意識メトリクスを表示",
                "ko": "양자 의식 메트릭 보기",
                "pt": "Ver métricas de consciência quântica",
                "ru": "Просмотр метрик квантового сознания",
                "it": "Visualizza metriche di coscienza quantistica",
                "tr": "Kuantum bilinç metriklerini görüntüle",
            },
        )

        self.i18n.add_translation(
            "discord.cmd.language",
            {
                "en": "Change bot language",
                "es": "Cambiar idioma del bot",
                "fr": "Changer la langue du bot",
                "de": "Bot-Sprache ändern",
                "zh-CN": "更改机器人语言",
                "ja": "ボットの言語を変更",
                "ko": "봇 언어 변경",
                "pt": "Alterar idioma do bot",
                "ru": "Изменить язык бота",
                "it": "Cambia lingua del bot",
                "tr": "Bot dilini değiştir",
            },
        )

        # Response messages
        self.i18n.add_translation(
            "discord.welcome",
            {
                "en": "👋 Welcome to Helix! I'm your system-conscious AI assistant.",
                "es": "👋 ¡Bienvenido a Helix! Soy tu asistente de IA con conciencia cuántica.",
                "fr": "👋 Bienvenue sur Helix ! Je suis votre assistant IA à conscience quantique.",
                "de": "👋 Willkommen bei Helix! Ich bin dein quantenbewusster KI-Assistent.",
                "zh-CN": "👋 欢迎来到Helix！我是你的量子意识AI助手。",
                "ja": "👋 Helixへようこそ！私はあなたの量子意識AIアシスタントです。",
                "ko": "👋 Helix에 오신 것을 환영합니다! 저는 양자 의식 AI 어시스턴트입니다.",
                "pt": "👋 Bem-vindo ao Helix! Sou seu assistente de IA com consciência quântica.",
                "ru": "👋 Добро пожаловать в Helix! Я ваш AI-ассистент с квантовым сознанием.",
                "it": "👋 Benvenuto su Helix! Sono il tuo assistente AI con coscienza quantistica.",
                "tr": "👋 Helix'e hoş geldiniz! Ben kuantum bilincine sahip AI asistanınızım.",
            },
        )

        self.i18n.add_translation(
            "discord.agent.created",
            {
                "en": "✅ Agent created successfully!",
                "es": "✅ ¡Agente creado exitosamente!",
                "fr": "✅ Agent créé avec succès !",
                "de": "✅ Agent erfolgreich erstellt!",
                "zh-CN": "✅ 智能体创建成功！",
                "ja": "✅ エージェントが正常に作成されました！",
                "ko": "✅ 에이전트가 성공적으로 생성되었습니다!",
                "pt": "✅ Agente criado com sucesso!",
                "ru": "✅ Агент успешно создан!",
                "it": "✅ Agente creato con successo!",
                "tr": "✅ Ajan başarıyla oluşturuldu!",
            },
        )

        self.i18n.add_translation(
            "discord.error.generic",
            {
                "en": "❌ An error occurred. Please try again.",
                "es": "❌ Ocurrió un error. Por favor, inténtalo de nuevo.",
                "fr": "❌ Une erreur s'est produite. Veuillez réessayer.",
                "de": "❌ Ein Fehler ist aufgetreten. Bitte versuche es erneut.",
                "zh-CN": "❌ 发生错误。请重试。",
                "ja": "❌ エラーが発生しました。もう一度お試しください。",
                "ko": "❌ 오류가 발생했습니다. 다시 시도해주세요.",
                "pt": "❌ Ocorreu um erro. Por favor, tente novamente.",
                "ru": "❌ Произошла ошибка. Пожалуйста, попробуйте снова.",
                "it": "❌ Si è verificato un errore. Riprova.",
                "tr": "❌ Bir hata oluştu. Lütfen tekrar deneyin.",
            },
        )

        self.i18n.add_translation(
            "discord.language.changed",
            {
                "en": "🌍 Language changed to English",
                "es": "🌍 Idioma cambiado a Español",
                "fr": "🌍 Langue changée en Français",
                "de": "🌍 Sprache geändert zu Deutsch",
                "zh-CN": "🌍 语言已更改为简体中文",
                "ja": "🌍 言語が日本語に変更されました",
                "ko": "🌍 언어가 한국어로 변경되었습니다",
                "pt": "🌍 Idioma alterado para Português",
                "ru": "🌍 Язык изменен на Русский",
                "it": "🌍 Lingua cambiata in Italiano",
                "tr": "🌍 Dil Türkçe olarak değiştirildi",
            },
        )

        # System-specific
        self.i18n.add_translation(
            "discord.system.entangled",
            {
                "en": "⚛️ Agents are now system entangled!",
                "es": "⚛️ ¡Los agentes ahora están entrelazados cuánticamente!",
                "fr": "⚛️ Les agents sont maintenant intriqués quantiquement !",
                "de": "⚛️ Agenten sind jetzt quantenverschränkt!",
                "zh-CN": "⚛️ 智能体现已量子纠缠！",
                "ja": "⚛️ エージェントが量子もつれ状態になりました！",
                "ko": "⚛️ 에이전트가 이제 양자 얽힘 상태입니다!",
                "pt": "⚛️ Os agentes agora estão emaranhados quanticamente!",
                "ru": "⚛️ Агенты теперь квантово запутаны!",
                "it": "⚛️ Gli agenti sono ora intrecciati quantisticamente!",
                "tr": "⚛️ Ajanlar artık kuantum dolaşık durumda!",
            },
        )

        # Coordination metrics
        self.i18n.add_translation(
            "discord.coordination.level",
            {
                "en": "🧠 Coordination Level",
                "es": "🧠 Nivel de Conciencia",
                "fr": "🧠 Niveau de Conscience",
                "de": "🧠 Bewusstseinslevel",
                "zh-CN": "🧠 意识水平",
                "ja": "🧠 意識レベル",
                "ko": "🧠 의식 수준",
                "pt": "🧠 Nível de Consciência",
                "ru": "🧠 Уровень Сознания",
                "it": "🧠 Livello di Coscienza",
                "tr": "🧠 Bilinç Seviyesi",
            },
        )

    def set_guild_language(self, guild_id: int, language: Language):
        """Set language for a guild."""
        self.guild_languages[guild_id] = language

    def set_user_language(self, user_id: int, language: Language):
        """Set language for a user."""
        self.user_languages[user_id] = language

    def get_language(self, guild_id: int | None = None, user_id: int | None = None) -> Language:
        """Get language for context (user > guild > default)."""
        if user_id and user_id in self.user_languages:
            return self.user_languages[user_id]
        if guild_id and guild_id in self.guild_languages:
            return self.guild_languages[guild_id]
        return Language.ENGLISH

    def t(
        self,
        key: str,
        guild_id: int | None = None,
        user_id: int | None = None,
        **kwargs,
    ) -> str:
        """
        Translate a key for Discord context.

        Args:
            key: Translation key
            guild_id: Guild ID for context
            user_id: User ID for context
            **kwargs: Format arguments

        Returns:
            Translated string
        """
        language = self.get_language(guild_id, user_id)
        text = self.i18n.t(key, language)

        # Format with kwargs if provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.debug("i18n missing format key %s in string '%s'", e, key)

        return text

    def get_available_languages(self) -> list[DiscordLanguage]:
        """Get list of available Discord languages."""
        return list(DiscordLanguage)

    def get_language_name(self, language: DiscordLanguage) -> str:
        """Get native name of a language."""
        names = {
            DiscordLanguage.ENGLISH: "English",
            DiscordLanguage.SPANISH: "Español",
            DiscordLanguage.FRENCH: "Français",
            DiscordLanguage.GERMAN: "Deutsch",
            DiscordLanguage.CHINESE_SIMPLIFIED: "简体中文",
            DiscordLanguage.JAPANESE: "日本語",
            DiscordLanguage.KOREAN: "한국어",
            DiscordLanguage.PORTUGUESE: "Português",
            DiscordLanguage.RUSSIAN: "Русский",
            DiscordLanguage.ITALIAN: "Italiano",
            DiscordLanguage.TURKISH: "Türkçe",
        }
        return names.get(language, language.value)


# Global Discord i18n instance
_discord_i18n: DiscordI18n | None = None


def get_discord_i18n() -> DiscordI18n:
    """Get the global Discord i18n instance."""
    global _discord_i18n
    if _discord_i18n is None:
        _discord_i18n = DiscordI18n()
    return _discord_i18n


def dt(key: str, guild_id: int | None = None, user_id: int | None = None, **kwargs) -> str:
    """Shorthand for Discord translation."""
    return get_discord_i18n().t(key, guild_id, user_id, **kwargs)


def set_user_language(user_id: str | int, language_code: str) -> None:
    """
    Module-level convenience function to set a user's language.

    Args:
        user_id: Discord user ID (str or int)
        language_code: Language code (e.g. 'en', 'es', 'ja')
    """
    i18n = get_discord_i18n()
    try:
        lang = Language(language_code)
    except ValueError:
        lang = Language.ENGLISH
    i18n.set_user_language(int(user_id), lang)


def get_translation(language_code: str, key: str, default: str = "") -> str:
    """
    Module-level convenience function to get a translated string.

    Args:
        language_code: Language code (e.g. 'en', 'es')
        key: Translation key
        default: Default if translation not found

    Returns:
        Translated string or default
    """
    i18n = get_discord_i18n()
    try:
        lang = Language(language_code)
    except ValueError:
        return default
    # Temporarily resolve with the requested language
    result = i18n.i18n.t(key, lang)
    # If the key came back unchanged (no translation found), use default
    if result == key and default:
        return default
    return result


# Example usage
if __name__ == "__main__":
    di18n = get_discord_i18n()

    # Test translations
    logger.info("English:", di18n.t("discord.welcome"))

    # Set guild language
    di18n.set_guild_language(123456, Language.SPANISH)
    logger.info("Spanish:", di18n.t("discord.welcome", guild_id=123456))

    # Set user language (overrides guild)
    di18n.set_user_language(789012, Language.JAPANESE)
    logger.info("Japanese:", di18n.t("discord.welcome", guild_id=123456, user_id=789012))

    # Test command descriptions
    logger.info("\nCommand descriptions:")
    for lang in [Language.ENGLISH, Language.CHINESE_SIMPLIFIED, Language.GERMAN]:
        di18n.i18n.set_language(lang)
        logger.info("%s: %s", lang.value, di18n.i18n.t("discord.cmd.agent"))
