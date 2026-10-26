"""Regression tests using real Home Assistant classes and a mocked HTTP boundary."""

import base64
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components import stt
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.exceptions import HomeAssistantError

from custom_components.inworld_tts import (
    PLATFORMS,
    async_migrate_entry,
    config_flow,
    tts,
)
from custom_components.inworld_tts import stt as inworld_stt
from custom_components.inworld_tts import voices as voice_api
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
    """The options handler opens and preserves current model selections."""
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
    entity = tts.InworldTTSEntity("test-key", model, [
        {"voiceId": "Japanese", "languageCode": "ja-JP"},
        {"voiceId": "Dennis", "languageCode": "en-US"},
    ], "test-entry")
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
            "voiceId": voice or "Japanese",
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
        await entity.async_get_tts_audio("Hello", "en", {"voice": "Dennis"})


@pytest.mark.parametrize(
    ("old", "new"),
    [("inworld-tts-1.5-max", "inworld-tts-2"),
     ("inworld-tts-1.5-mini", "inworld-tts-2-flash"),
     ("inworld-tts-2-flash", "inworld-tts-2-flash"),
     ("invalid-model", "inworld-tts-2")],
)
@pytest.mark.asyncio
async def test_migrate_retired_models(old, new):
    entry = SimpleNamespace(version=1, options={CONF_MODEL: old, "other": True})
    hass = MagicMock()
    assert await async_migrate_entry(hass, entry)
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, options={CONF_MODEL: new, "other": True}, version=2
    )
    assert set(MODELS) == {"inworld-tts-2", "inworld-tts-2-flash"}
    assert set(PLATFORMS) == {Platform.STT, Platform.TTS}


@pytest.mark.parametrize(
    ("language", "expected"),
    [("ja", ["Japanese", "Localized"]), ("JA_jp", ["Japanese", "Localized"]),
     ("en", ["Dennis", "Localized"]), ("fr", [])],
)
def test_voice_language_filter(language, expected):
    entity = tts.InworldTTSEntity("key", DEFAULT_MODEL, [
        {"voiceId": "Dennis", "languageCode": "en-US"},
        {"voiceId": "Japanese", "langCode": "JA_JP"},
        {"voiceId": "Localized", "languageCode": "en-US",
         "promptLanguages": ["en-US", "ja-JP"]},
        {"voiceId": "Unknown"},
    ], "entry")
    assert [v.voice_id for v in entity.async_get_supported_voices(language)] == expected


@pytest.mark.asyncio
async def test_no_matching_default_voice():
    entity = tts.InworldTTSEntity("key", DEFAULT_MODEL, [
        {"voiceId": "Dennis", "languageCode": "en-US"},
    ], "entry")
    with pytest.raises(HomeAssistantError, match="No Inworld voices"):
        await entity.async_get_tts_audio("こんにちは", "ja", {})


@pytest.mark.asyncio
async def test_paginated_voice_catalog():
    responses = []
    for payload in [
        {"voices": [{"voiceId": "A"}], "nextPageToken": "next"},
        {"voices": [{"voiceId": "A"}, {"voiceId": "B"}]},
    ]:
        response = MagicMock()
        response.json = AsyncMock(return_value=payload)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        responses.append(context)
    session = MagicMock()
    session.get.side_effect = responses
    with patch.object(voice_api, "async_get_clientsession", return_value=session):
        voices = await voice_api.async_list_voices(MagicMock(), "key")
    assert [v["voiceId"] for v in voices] == ["A", "B"]
    assert session.get.call_args_list[1].kwargs["params"]["pageToken"] == "next"


def speech_metadata(**overrides):
    values = {
        "language": "ja", "format": stt.AudioFormats.WAV,
        "codec": stt.AudioCodecs.PCM, "bit_rate": 16,
        "sample_rate": 16000, "channel": 1,
    }
    return stt.SpeechMetadata(**(values | overrides))


async def audio_stream(*chunks):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payload", "expected", "text"),
    [(200, {"transcription": {"transcript": "電気をつけて"}}, "success", "電気をつけて"),
     (200, {"transcription": {"transcript": ""}}, "success", ""),
     (200, {}, "error", None), (401, {}, "error", None), (403, {}, "error", None)],
)
async def test_stt_transcription(status, payload, expected, text):
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=payload)
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    entity = inworld_stt.InworldSTTEntity("test-key", "entry")
    entity.hass = MagicMock()
    pcm = b"\x00\x00" * 100
    with patch.object(inworld_stt, "async_get_clientsession", return_value=session):
        result = await entity.async_process_audio_stream(
            speech_metadata(), audio_stream(pcm[:50], pcm[50:])
        )
    request = session.post.call_args.kwargs
    assert session.post.call_args.args[0].endswith("/stt/v1/transcribe")
    assert request["headers"]["Authorization"] == "Basic test-key"
    assert request["json"]["transcribeConfig"] == {
        "modelId": "inworld/inworld-stt-1", "audioEncoding": "LINEAR16",
        "language": "ja", "sampleRateHertz": 16000, "numberOfChannels": 1,
    }
    assert base64.b64decode(request["json"]["audioData"]["content"]) == pcm
    assert result.result == expected
    assert result.text == text
    assert entity.unique_id == "entry-stt"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["empty", "oversized", "format", "connection"])
async def test_stt_rejections(case):
    entity = inworld_stt.InworldSTTEntity("key", "entry")
    entity.hass = MagicMock()
    session = MagicMock()
    session.post.side_effect = OSError("Connection closed")
    chunks = [] if case == "empty" else [b"00"]
    metadata = speech_metadata(codec=stt.AudioCodecs.OPUS) if case == "format" else speech_metadata()
    with (
        patch.object(inworld_stt, "MAX_AUDIO_BYTES", 1 if case == "oversized" else 100),
        patch.object(inworld_stt, "async_get_clientsession", return_value=session),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream(*chunks))
    assert result.result == stt.SpeechResultState.ERROR
    if case != "connection":
        session.post.assert_not_called()


@pytest.mark.asyncio
async def test_shared_setup_and_unload():
    from custom_components import inworld_tts as integration

    catalog = [{"voiceId": "Japanese", "languageCode": "ja-JP"}]
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.data = {CONF_API_KEY: "key"}
    entry.options = {CONF_MODEL: DEFAULT_MODEL}
    entry.entry_id = "existing-entry"
    with patch.object(integration, "async_list_voices", AsyncMock(return_value=catalog)):
        assert await integration.async_setup_entry(hass, entry)
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, [Platform.TTS, Platform.STT]
    )
    tts_entities = MagicMock()
    stt_entities = MagicMock()
    await tts.async_setup_entry(hass, entry, tts_entities)
    await inworld_stt.async_setup_entry(hass, entry, stt_entities)
    tts_entity = tts_entities.call_args.args[0][0]
    stt_entity = stt_entities.call_args.args[0][0]
    assert tts_entity.unique_id == "existing-entry"
    assert stt_entity.unique_id == "existing-entry-stt"
    assert tts_entity.device_info["identifiers"] == stt_entity.device_info["identifiers"]
    assert len(tts_entity.async_get_supported_voices("ja")) == 1
    assert await integration.async_unload_entry(hass, entry)
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, [Platform.TTS, Platform.STT]
    )


@pytest.mark.asyncio
async def test_repeated_pagination_token():
    response = MagicMock()
    response.json = AsyncMock(return_value={"voices": [], "nextPageToken": "repeat"})
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    with (
        patch.object(voice_api, "async_get_clientsession", return_value=session),
        pytest.raises(ValueError, match="pagination token"),
    ):
        await voice_api.async_list_voices(MagicMock(), "key")
    assert session.get.call_count == 2


@pytest.mark.asyncio
async def test_stt_server_error():
    from aiohttp import ClientResponseError

    response = MagicMock(status=500)
    response.raise_for_status.side_effect = ClientResponseError(
        MagicMock(real_url="https://api.inworld.ai/stt/v1/transcribe"),
        (), status=500, message="Server error",
    )
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    entity = inworld_stt.InworldSTTEntity("key", "entry")
    entity.hass = MagicMock()
    with patch.object(inworld_stt, "async_get_clientsession", return_value=session):
        result = await entity.async_process_audio_stream(
            speech_metadata(), audio_stream(b"00")
        )
    assert result.result == stt.SpeechResultState.ERROR
