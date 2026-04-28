from dotenv import load_dotenv
import os
import sounddevice as sd
load_dotenv()

INACTIVITY_TIMEOUT = 120  # 120 secondi di inattività per lo standby

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama-local").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip()
MAIN_LLM_MODEL = None
if LLM_PROVIDER == "ollama-local":
    MAIN_LLM_MODEL = OLLAMA_MODEL
elif LLM_PROVIDER == "anthropic":
    MAIN_LLM_MODEL = ANTHROPIC_MODEL
elif LLM_PROVIDER == "google":
    MAIN_LLM_MODEL = GOOGLE_MODEL

PIPER_MODEL_DIR = "models/piper"
#PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
PIPER_MODEL_NAME = "it_IT_RON.onnx"
PIPER_MODEL_PATH = os.path.join(PIPER_MODEL_DIR, PIPER_MODEL_NAME)
PIPER_CONFIG_PATH = PIPER_MODEL_PATH + ".json"
PIPER_MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}?download=true"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}.json?download=true"

BASE_URL = "http://127.0.0.1:5000"

VOSK_MODEL_NAME = "vosk-model-small-it-0.22"
VOSK_MODEL_PATH = os.path.join("models", VOSK_MODEL_NAME)
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
WAKE_WORDS = ["absalom","absalon","assalom","assalon","okron","ok ron", "ok on","ciaoron","ciao ron","sauron", "ciao", "ciao rom"]

VOSK_RATE = 16000


AUDIO_DEVICE_INDEX = os.getenv("AUDIO_DEVICE_INDEX")
if AUDIO_DEVICE_INDEX:
    try:
        AUDIO_DEVICE_INDEX = int(AUDIO_DEVICE_INDEX)
    except ValueError:
        pass
# Rilevamento automatico SAMPLE_RATE dal sistema
try:
    device_info = sd.query_devices(AUDIO_DEVICE_INDEX, 'input')
    SAMPLE_RATE = int(device_info['default_samplerate'])
    print(f"--- Audio device [{AUDIO_DEVICE_INDEX if AUDIO_DEVICE_INDEX is not None else 'default'}] detected: {device_info['name']} at {SAMPLE_RATE} Hz ---")
except Exception as e:
    print(f"!!! Error querying audio device: {e}. Falling back to 44100 Hz !!!")
    SAMPLE_RATE = 44100