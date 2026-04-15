import os
import sys
import json
import queue
import zipfile
import urllib.request
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import requests
import asyncio
import edge_tts
import subprocess

BASE_URL = "http://127.0.0.1:5000"

def blink():
    print("Inviando comando blink...")
    requests.post(f"{BASE_URL}/blink")

def set_mode(mode):
    print(f"Impostando modalità a: {mode}")
    try:
        r = requests.post(f"{BASE_URL}/control", json={"mode": mode})
        return r.json()
    except Exception as e:
        print(f"Errore: {e}")

VOICE = "it-IT-DiegoNeural"

async def _speak_async(text):
    communicate = edge_tts.Communicate(text, VOICE)
    # Use a temporary file name to avoid collisions if called rapidly
    filename = "speech.mp3"
    await communicate.save(filename)
    # ffplay handles the playback
    subprocess.run(["ffplay", "-nodisp", "-autoexit", filename], 
                   stderr=subprocess.DEVNULL, 
                   stdout=subprocess.DEVNULL)

def speak(text):
    print(f"Absalom dice: '{text}'")
    asyncio.run(_speak_async(text))

# Configuration
MODEL_PATH = "model"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
WAKE_WORDS = ["absalom","absalon","assalom","assalon","addormentati"]
SAMPLE_RATE = 16000

# Audio queue
q = queue.Queue()

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def download_model():
    print(f"--- Modello non trovato. Download in corso da {MODEL_URL} ---")
    zip_path = "model.zip"
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    print("Download completato. Estrazione...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(".")
    
    # Rename extracted folder to 'model'
    extracted_folder = "vosk-model-small-it-0.22"
    if os.path.exists(extracted_folder):
        os.rename(extracted_folder, MODEL_PATH)
    
    os.remove(zip_path)
    print("Modello pronto.\n")

def start_assistant():
    if not os.path.exists(MODEL_PATH):
        download_model()

    # Initialize model
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(WAKE_WORDS))

    print(f"\n>>> Absalom OS avviato. In ascolto per la parola chiave: '{WAKE_WORDS}'...")

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower()
                    
                    if text:
                        print(f"DEBUG: Sentito -> '{text}'")
                    
                    if any(word in text for word in WAKE_WORDS):
                        if "addormentati" in text:
                            print("\n[!] Notte ...")
                            set_mode("asleep")
                            speak("D'accordo, vado a dormire. Buonanotte.")
                        else:
                            print("\n[!] Ti ho sentito")
                            set_mode("awake")
                            speak("Ciao!")
                else:
                    # Partial record?
                    # partial = json.loads(rec.PartialResult())
                    pass

    except KeyboardInterrupt:
        print("\nSpegni assistente...")
    except Exception as e:
        print(f"\nErrore durante l'esecuzione: {e}")

if __name__ == "__main__":
    start_assistant()
