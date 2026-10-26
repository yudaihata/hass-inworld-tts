<p align="center">
  <img src="img/logo.png" alt="Inworld AI Logo">
</p>

# Inworld AI Speech for Home Assistant

A fork of [notf0und/hass-inworld-tts](https://github.com/notf0und/hass-inworld-tts), providing **TTS-2, TTS-2 Flash, and speech recognition**.

A Home Assistant integration for [Inworld AI](https://platform.inworld.ai/) text-to-speech (TTS) and speech-to-text (STT), using one API key.


[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yudaihata&repository=hass-inworld-tts&category=Integration)


[![GitHub Release](https://img.shields.io/github/release/yudaihata/hass-inworld-tts.svg?style=flat-square)](https://github.com/yudaihata/hass-inworld-tts/releases)
[![GitHub Activity](https://img.shields.io/github/commit-activity/y/yudaihata/hass-inworld-tts.svg?style=flat-square)](https://github.com/yudaihata/hass-inworld-tts/commits/main)
[![License](https://img.shields.io/github/license/yudaihata/hass-inworld-tts.svg?style=flat-square)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.1+-blue?style=flat-square)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat-square)](https://hacs.xyz/)

[![GitHub Sponsors][sponsorsbadge]][sponsors]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]


## Features

- 🔊 High-quality text-to-speech powered by Inworld AI
- 🎯 Easy configuration through Home Assistant UI
- 🔐 Secure API key management
- ☁️ Cloud-based processing
- 🌍 TTS voice choices filtered by the selected language, including localized voice prompts
- 🎤 STT in 30 languages for Home Assistant Assist
- 🚀 Choose between TTS-2 (best quality) and TTS-2 Flash (lowest latency)

## Installation

### Via HACS (Recommended)

Click the button above or follow these steps:

1. Open Home Assistant
2. Go to **Settings** → **Devices & Services** → **Home Assistant Community Store (HACS)**
3. Open the HACS menu → **Custom repositories**
4. Add `https://github.com/yudaihata/hass-inworld-tts` with type **Integration**
5. Search for **Inworld AI Speech** and click **Download**
6. Restart Home Assistant

### Manual Installation

1. Copy the `inworld_tts` folder from `custom_components` to your Home Assistant `custom_components` directory:
   ```bash
   cp -r inworld_tts config/custom_components/
   ```

2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **+ Add Integration**
2. Search for **Inworld AI Speech**
3. Enter your [Inworld AI API key](https://platform.inworld.ai/api-keys)
4. Select **TTS-2** (default) or **TTS-2 Flash**
5. Click **Submit**

For an existing integration, open **Configure** to change the model. TTS 1.5 has been removed: existing Max selections automatically migrate to TTS-2, and Mini selections to TTS-2 Flash. Existing TTS entity IDs and API keys are preserved. Select a voice in your Assist pipeline or pass `options: {voice: Dennis}` to `tts.speak`.

## Usage

Once configured, you can use the TTS service:

```yaml
action: tts.speak
target:
   entity_id: tts.inworld_ai
data:
   message: Hello, this is a test message
   media_player_entity_id: media_player.living_room
```

Or in automations:

```yaml
automation:
  - alias: "Announce motion detection"
    trigger:
      platform: state
      entity_id: binary_sensor.motion_sensor
      to: "on"
    action: tts.speak
    target:
      entity_id: tts.inworld_ai
    data:
      message: Motion detected in the living room
      media_player_entity_id: media_player.living_room
```

Or add it to your voice assistant pipeline:

1. Go to **Settings** → **Voice Assistants** → **+ Add Assistant**
2. Choose your assistant language (e.g. Japanese)
3. Set **Speech-to-text** → **Inworld AI**
4. Set **Text-to-speech** → **Inworld AI**, then choose a voice from the language-filtered list
5. Select a conversation agent and save the assistant

TTS and STT are separate entities and can also be used independently. The conversation agent remains your choice; this integration handles speech recognition and synthesis.

## Getting an API Key

1. Visit [Inworld AI Portal](https://platform.inworld.ai/api-keys)
2. Sign up or log in
3. Click **API Keys** in the bottom left sidebar
4. Click **Generate new key**
5. Copy the **Basic (Base64)** authorization signature — this is your API key

> **Note:** Use the **Basic (Base64)** value, not the raw key or secret.

## Available Models

| Model | ID | Description |
|-------|----|-------------|
| TTS-2 | `inworld-tts-2` | Default; highest quality and expressiveness |
| TTS-2 Flash | `inworld-tts-2-flash` | Lowest latency |
| STT-1 | `inworld/inworld-stt-1` | Speech recognition (fixed model) |

See the [official model documentation](https://docs.inworld.ai/tts/tts-models). The integration uses the [synchronous API](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech), returns WAV audio, and sends the selected language explicitly. Requests are limited by the API to 2,000 UTF-16 code units.

## Speech recognition

The integration adds an STT entity automatically alongside TTS; no second API key is needed. Select **Inworld AI** under Speech-to-text in your Assist pipeline.

It uses the [synchronous STT API](https://docs.inworld.ai/api-reference/sttAPI/speechtotext/transcribe). Home Assistant supplies 16 kHz, 16-bit mono PCM. The utterance is buffered until capture ends, wrapped in a WAV container required by the synchronous API, then uploaded with the pipeline language as a hint; transcription is returned to Assist. This is utterance-based transcription, without interim transcripts or WebSocket streaming. Capture is limited to 120 seconds and 10 MiB, with a 60-second API timeout. Audio is held in memory, not saved to disk. Audio and text are sent to Inworld for cloud processing.

## Voice language filtering

The integration fetches all pages from the current [Voice API](https://docs.inworld.ai/api-reference/voiceAPI/voiceservice/list-voices) at setup. Your API key needs Voice API read access. The picker includes voices whose primary language or localized `promptLanguages` match the selected language. For example, `ja`, `ja-JP`, and `JA_JP` match Japanese. Voices without matching language metadata are excluded. Reload the integration after creating/localizing a voice to refresh the catalog.

When no voice is explicitly supplied, the integration uses a voice from the filtered list (Dennis for English when available, otherwise the first alphabetically). If the list is empty it reports an error instead of silently using an English voice. Explicit voice IDs in `tts.speak` remain available for cross-language synthesis.

## Supported Languages

TTS exposes the 15 Tier 1 languages in Home Assistant (the models themselves support more):

English, Chinese, Japanese, Korean, Russian, Italian, Spanish, Portuguese, French, German, Polish, Dutch, Hindi, Hebrew, Arabic.

STT exposes the [30 documented recognition languages](https://docs.inworld.ai/stt/languages), including Japanese, English, Chinese, Cantonese, Korean, and the European/Asian languages listed there.

## Development

The regression suite uses Home Assistant 2026.1.3 and Python 3.13 on Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
```

## Support

For issues or feature requests, please visit the [GitHub Issues](https://github.com/yudaihata/hass-inworld-tts/issues) page.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not officially affiliated with Inworld AI. It is a community-maintained integration.

[sponsorsbadge]: https://img.shields.io/badge/sponsor-GitHub-blue?style=flat-square
[sponsors]: https://github.com/sponsors/notf0und
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow?style=flat-square
[buymecoffee]: https://buymeacoffee.com/gonzarturm
