"""Constants for the Inworld AI TTS integration."""

DOMAIN = "inworld_tts"

CONF_MODEL = "model"

MODEL_TTS_2 = "inworld-tts-2"
MODEL_TTS_2_FLASH = "inworld-tts-2-flash"

MODEL_TTS_1_5_MAX = "inworld-tts-1.5-max"
MODEL_TTS_1_5_MINI = "inworld-tts-1.5-mini"

MODELS = {
    MODEL_TTS_2: "TTS-2 (Best quality)",
    MODEL_TTS_2_FLASH: "TTS-2 Flash (Fastest)",
    MODEL_TTS_1_5_MAX: "TTS 1.5 Max (Legacy)",
    MODEL_TTS_1_5_MINI: "TTS 1.5 Mini (Legacy)",
}

DEFAULT_MODEL = MODEL_TTS_2
DEFAULT_VOICE = "Dennis"

INWORLD_TTS_API_URL = "https://api.inworld.ai/tts/v1/voice"
INWORLD_VOICES_API_URL = "https://api.inworld.ai/tts/v1/voices"
