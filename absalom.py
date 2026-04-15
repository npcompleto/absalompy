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
import ollama
import anthropic
from dotenv import load_dotenv

# Carica variabili d'ambiente da .env
load_dotenv()

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

def set_busy(busy_status):
    try:
        requests.post(f"{BASE_URL}/control", json={"busy": busy_status})
    except Exception as e:
        print(f"Errore set_busy: {e}")

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

def get_persona():
    """Carica e concatena i file della personalità."""
    persona = ""
    try:
        for filename in ["Identity.md"]:
            path = os.path.join("persona", filename)
            if os.path.exists(path):
                with open(path, "r") as f:
                    persona += f.read() + "\n\n"
    except Exception as e:
        print(f"Errore nel caricamento della persona: {e}")
    return persona

# LLM Configuration
LLM_PROVIDER = "anthropic" # "ollama-local" or "anthropic"
OLLAMA_MODEL = "llama3.2:1b"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

def ask_ollama(user_input, system_prompt):
    """Interroga Ollama localmente."""
    try:
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_input},
        ]
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        return response['message']['content']
    except Exception as e:
        print(f"Errore Ollama: {e}")
        return "Errore di connessione a Ollama. Glitch!"

def ask_anthropic(user_input, system_prompt):
    """Interroga Anthropic Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Errore: ANTHROPIC_API_KEY non configurata nel file .env."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Errore Anthropic: {e}")
        return "Errore di connessione a Claude. Glitch nel cloud!"

def ask_llm(user_input):
    """Interroga il provider configurato."""
    system_prompt = get_persona()
    if LLM_PROVIDER == "anthropic":
        return ask_anthropic(user_input, system_prompt)
    else:
        return ask_ollama(user_input, system_prompt)

# Configuration
MODEL_PATH = "model"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
WAKE_WORDS = ["absalom","absalon","assalom","assalon"]
SAMPLE_RATE = 16000

# Audio queue and status
q = queue.Queue()
is_busy = False
is_awake = False

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    if not is_busy:
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

    global is_busy
    global is_awake

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower()
                    
                    if any(word in text for word in WAKE_WORDS):
                        is_busy = True
                        set_busy(True)
                        # Identifica quale parola chiave è stata usata per rimuoverla dal prompt
                        trigger_word = next((w for w in WAKE_WORDS if w in text), None)
                        print("\n[!] Ti ho sentito")
                        set_mode("awake")
                        is_awake = True
                        
                        # reset recognizer
                        rec = KaldiRecognizer(model, SAMPLE_RATE)
                        speak("Eccomi!")
                        
                        # Svuota la coda per evitare di processare audio accumulato
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        is_busy = False
                        set_busy(False)
                    elif is_awake and text != "" and text != " ":
                        is_busy = True
                        set_busy(True)
                        print(f"DEBUG: Sentito -> '{text}'")
                        print(f"Analisi richiesta: '{text}'")
                        response = ask_llm(text)
                        speak(response)
                        
                        # Svuota la coda
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        is_busy = False
                        set_busy(False)
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
