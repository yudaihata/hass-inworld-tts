"""Support for the Inworld AI text-to-speech service."""

from __future__ import annotations

import base64
import logging
from typing import Any, ClassVar

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InworldTTSConfigEntry
from .const import (
    CONF_MODEL,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    DOMAIN,
    INWORLD_TTS_API_URL,
    INWORLD_VOICES_API_URL,
    MODELS,
)

_LOGGER = logging.getLogger(__name__)

# Tier 1 languages, also supported by the legacy TTS 1.5 models.
# https://docs.inworld.ai/tts/capabilities/multilingual
SUPPORTED_LANGUAGES = [
    "en",
    "zh",
    "ja",
    "ko",
    "ru",
    "it",
    "es",
    "pt",
    "fr",
    "de",
    "pl",
    "nl",
    "hi",
    "he",
    "ar",
]

SAMPLE_RATE_HZ = 22050


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: InworldTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Inworld AI TTS platform via config entry."""
    api_key = config_entry.runtime_data.api_key
    model = config_entry.options.get(CONF_MODEL, DEFAULT_MODEL)

    # Fetch available voices once at setup so the pipeline dropdown is populated
    voices: list[Voice] = []
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            INWORLD_VOICES_API_URL,
            headers={"Authorization": f"Basic {api_key}"},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        for v in data.get("voices", []):
            voice_id = v.get("voiceId")
            display_name = v.get("displayName") or voice_id
            if voice_id:
                voices.append(Voice(voice_id=voice_id, name=display_name))
        voices.sort(key=lambda v: v.name.lower())
    except Exception:
        _LOGGER.exception("Could not fetch Inworld AI voices at setup")

    _LOGGER.debug("Inworld AI TTS: setup with %d voices, model=%s", len(voices), model)
    async_add_entities(
        [
            InworldTTSEntity(
                api_key=api_key,
                model=model,
                voices=voices,
                entry_id=config_entry.entry_id,
            )
        ]
    )


class InworldTTSEntity(TextToSpeechEntity):
    """The Inworld AI TTS entity."""

    _attr_supported_options: ClassVar[list[str]] = [ATTR_VOICE]

    def __init__(
        self,
        api_key: str,
        model: str,
        voices: list[Voice],
        entry_id: str,
    ) -> None:
        """Initialize the Inworld AI TTS entity."""
        self._api_key = api_key
        self._model = model
        self._voices = voices
        self._attr_name = "Inworld AI"
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Inworld AI",
            model=MODELS.get(model, model),
            name="Inworld AI",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_supported_languages = SUPPORTED_LANGUAGES
        self._attr_default_language = "en"

    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return voices fetched at setup time for the pipeline dropdown."""
        return self._voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech using the Inworld AI TTS API."""
        voice_id = options.get(ATTR_VOICE) or DEFAULT_VOICE
        _LOGGER.debug(
            "Inworld AI TTS: model=%s voice=%s text=%r", self._model, voice_id, message
        )

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                INWORLD_TTS_API_URL,
                headers={
                    "Authorization": f"Basic {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": message,
                    "voiceId": voice_id,
                    "modelId": self._model,
                    "language": language,
                    "audioConfig": {
                        "audioEncoding": "LINEAR16",
                        "sampleRateHertz": SAMPLE_RATE_HZ,
                    },
                },
            ) as resp:
                if resp.status in (401, 403):
                    raise HomeAssistantError("Inworld AI authentication failed")
                resp.raise_for_status()
                result = await resp.json()
        except HomeAssistantError:
            raise
        except Exception as exc:
            _LOGGER.exception("Inworld AI TTS API error")
            raise HomeAssistantError(f"Inworld AI TTS request failed: {exc}") from exc

        audio_content = result.get("audioContent")
        if not audio_content:
            raise HomeAssistantError("Inworld AI returned no audio content")

        audio_bytes = base64.b64decode(audio_content)
        _LOGGER.debug("Inworld AI TTS success: %d bytes", len(audio_bytes))
        return "wav", audio_bytes
