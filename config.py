from dotenv import load_dotenv
import os
import sounddevice as sd
load_dotenv()
USE_HAILO = os.getenv("USE_HAILO", "false").lower() == "true"
HAILO_MODEL_PATH = os.getenv("HAILO_MODEL_PATH", "models/Whisper-Small.hef")

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
PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
#PIPER_MODEL_NAME = "it_IT_RON.onnx"
PIPER_MODEL_PATH = os.path.join(PIPER_MODEL_DIR, PIPER_MODEL_NAME)
PIPER_CONFIG_PATH = PIPER_MODEL_PATH + ".json"
PIPER_MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}?download=true"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}.json?download=true"

BASE_URL = "http://127.0.0.1:5000"

VOSK_MODEL_NAME = "vosk-model-small-it-0.22"
VOSK_MODEL_PATH = os.path.join("models", VOSK_MODEL_NAME)
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
WAKE_WORDS = ["absalom"]

VOSK_RATE = 16000


AUDIO_DEVICE_INDEX = os.getenv("AUDIO_DEVICE_INDEX")
if AUDIO_DEVICE_INDEX:
    try:
        AUDIO_DEVICE_INDEX = int(AUDIO_DEVICE_INDEX)
    except ValueError:
        AUDIO_DEVICE_INDEX = None

# Rilevamento automatico del dispositivo di input e SAMPLE_RATE
def find_input_device(requested_index):
    devices = []
    try:
        host_apis = sd.query_hostapis()
        print("--- Host APIs Rilevate ---")
        for i, api in enumerate(host_apis):
            print(f"[{i}] {api['name']} (Default Input: {api['default_input_device']}, Default Output: {api['default_output_device']})")
        
        devices = sd.query_devices()
        print("--- Elenco Dispositivi Audio Rilevati ---")
        for i, d in enumerate(devices):
            print(f"[{i}] {d['name']} - HostAPI: {d['hostapi']}, Input: {d['max_input_channels']}, Output: {d['max_output_channels']}")
        print("-----------------------------------------")
    except Exception as e:
        print(f"!!! Impossibile elencare i dispositivi audio: {e} !!!")

    # 1. Prova l'indice richiesto
    if requested_index is not None:
        try:
            info = sd.query_devices(requested_index, 'input')
            return requested_index, int(info['default_samplerate']), info['name']
        except Exception as e:
            print(f"!!! Errore query su indice {requested_index}: {e} !!!")

    # 2. Prova a cercare per nome in modo più aggressivo
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            lower_name = d['name'].lower()
            if any(x in lower_name for x in ["usb", "micro", "hw:", "input"]):
                print(f"--- Dispositivo compatibile trovato per nome: {d['name']} all'indice {i} ---")
                return i, int(d['default_samplerate']), d['name']

    # 3. Prova il default di sistema
    try:
        info = sd.query_devices(None, 'input')
        return None, int(info['default_samplerate']), info['name']
    except Exception:
        # 4. Ultimo tentativo: il primo con input > 0
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                return i, int(d['default_samplerate']), d['name']

    return None, 16000, "Default/Fallback"

AUDIO_DEVICE_INDEX, SAMPLE_RATE, AUDIO_DEVICE_NAME = find_input_device(AUDIO_DEVICE_INDEX)
print(f"--- Audio device FINAL: [{AUDIO_DEVICE_INDEX}] {AUDIO_DEVICE_NAME} at {SAMPLE_RATE} Hz ---")