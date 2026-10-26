"""Constants for the Inworld AI TTS integration."""

DOMAIN = "inworld_tts"

CONF_MODEL = "model"

MODEL_TTS_2 = "inworld-tts-2"
MODEL_TTS_2_FLASH = "inworld-tts-2-flash"

MODELS = {
    MODEL_TTS_2: "TTS-2 (Best quality)",
    MODEL_TTS_2_FLASH: "TTS-2 Flash (Fastest)",
}

DEFAULT_MODEL = MODEL_TTS_2
DEFAULT_VOICE = "Dennis"

INWORLD_TTS_API_URL = "https://api.inworld.ai/tts/v1/voice"
INWORLD_VOICES_API_URL = "https://api.inworld.ai/voices/v1/voices"

INWORLD_STT_API_URL = "https://api.inworld.ai/stt/v1/transcribe"
STT_MODEL = "inworld/inworld-stt-1"
