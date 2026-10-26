"""Regression tests using real Home Assistant classes and a mocked HTTP boundary."""

import base64
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import HomeAssistantError

from custom_components.inworld_tts import config_flow, tts
from custom_components.inworld_tts.const import (
    CONF_MODEL,
    DEFAULT_MODEL,
    INWORLD_TTS_API_URL,
    MODELS,
)


@pytest.mark.asyncio
async def test_initial_form():
    """New installations default to TTS-2 and offer both new models."""
    flow = config_flow.InworldTTSConfigFlow()
    result = await flow.async_step_user()
    assert result["data_schema"]({CONF_API_KEY: "test-key"})[CONF_MODEL] == "inworld-tts-2"
    selector = next(
        value for key, value in result["data_schema"].schema.items()
        if key.schema == CONF_MODEL
    )
    assert {option["value"] for option in selector.config["options"]} == set(MODELS)


@pytest.mark.asyncio
@pytest.mark.parametrize("model", MODELS)
async def test_options_flow(model):
    """The options handler opens and preserves old and new model selections."""
    flow = config_flow.InworldTTSConfigFlow.async_get_options_flow(None)
    with patch.object(
        type(flow), "config_entry", new=property(
            lambda self: SimpleNamespace(options={CONF_MODEL: model})
        )
    ):
        result = await flow.async_step_init()
    model_field = next(iter(result["data_schema"].schema))
    assert model_field.description["suggested_value"] == model
    result = await flow.async_step_init({CONF_MODEL: model})
    assert result["data"] == {CONF_MODEL: model}


def wav_audio():
    """Return a valid, small mono WAV fixture."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b"\x00\x00" * 100)
    return buffer.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("voice", [None, "Ashley"])
async def test_synthesis(model, voice):
    """Each selected model reaches the API and yields a playable WAV."""
    audio = wav_audio()
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={"audioContent": base64.b64encode(audio).decode()}
    )
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    entity = tts.InworldTTSEntity("test-key", model, [], "test-entry")
    entity.hass = MagicMock()
    with patch.object(tts, "async_get_clientsession", return_value=session):
        extension, result = await entity.async_get_tts_audio(
            "こんにちは", "ja", {"voice": voice}
        )
    session.post.assert_called_once_with(
        INWORLD_TTS_API_URL,
        headers={"Authorization": "Basic test-key", "Content-Type": "application/json"},
        json={
            "text": "こんにちは",
            "voiceId": voice or "Dennis",
            "modelId": model,
            "language": "ja",
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 22050},
        },
    )
    assert extension == "wav"
    assert result == audio
    with wave.open(io.BytesIO(result)) as output:
        assert output.getnframes() == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [(401, {}, "authentication failed"), (403, {}, "authentication failed"),
     (200, {}, "no audio content")],
)
async def test_api_errors(status, payload, error):
    """Authentication and missing audio fail as Home Assistant errors."""
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=payload)
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    entity = tts.InworldTTSEntity("test-key", DEFAULT_MODEL, [], "test-entry")
    entity.hass = MagicMock()
    with (
        patch.object(tts, "async_get_clientsession", return_value=session),
        pytest.raises(HomeAssistantError, match=error),
    ):
        await entity.async_get_tts_audio("Hello", "en", {})
