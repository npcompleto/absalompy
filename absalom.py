import os
import sys
import json
import queue
import zipfile
import urllib.request
import random
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import requests
from piper.voice import PiperVoice
import wave
import subprocess
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.time_tool import get_current_time
from dotenv import load_dotenv

# Carica variabili d'ambiente da .env
# LLM Configuration
LLM_PROVIDER = "ollama-local" # "ollama-local" or "anthropic"
OLLAMA_MODEL = "llama3.2:1b"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
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

def set_speaking(speaking_status):
    try:
        requests.post(f"{BASE_URL}/control", json={"speaking": speaking_status})
    except Exception as e:
        print(f"Errore set_speaking: {e}")

PIPER_MODEL_DIR = "models/piper"
PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
PIPER_MODEL_PATH = os.path.join(PIPER_MODEL_DIR, PIPER_MODEL_NAME)
PIPER_CONFIG_PATH = PIPER_MODEL_PATH + ".json"
PIPER_MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}?download=true"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}.json?download=true"

_piper_voice = None

def get_piper_voice():
    global _piper_voice
    if _piper_voice is None:
        if not os.path.exists(PIPER_MODEL_PATH) or not os.path.exists(PIPER_CONFIG_PATH):
            print("--- Download modello Piper in corso... ---")
            os.makedirs(PIPER_MODEL_DIR, exist_ok=True)
            urllib.request.urlretrieve(PIPER_MODEL_URL, PIPER_MODEL_PATH)
            urllib.request.urlretrieve(PIPER_CONFIG_URL, PIPER_CONFIG_PATH)
            print("--- Modello Piper pronto. ---")
        _piper_voice = PiperVoice.load(PIPER_MODEL_PATH, config_path=PIPER_CONFIG_PATH)
    return _piper_voice

def speak(text):
    global is_speaking
    
    print(f"Absalom dice: '{text}'")
    voice = get_piper_voice()
    filename = "speech.wav"
    try:
        with wave.open(filename, "wb") as wav_file:
            # Sostituisci la sintesi diretta con l'iteratore corretta
            for i, chunk in enumerate(voice.synthesize(text)):
                if i == 0:
                    wav_file.setnchannels(chunk.sample_channels)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setframerate(chunk.sample_rate)
                wav_file.writeframes(chunk.audio_int16_bytes)
        is_speaking = True
        set_speaking(True)
        # ffplay handles the playback
        subprocess.run(["ffplay", "-nodisp", "-autoexit", filename], 
                       stderr=subprocess.DEVNULL, 
                       stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"Errore durante la sintesi vocale: {e}")
    finally:
        is_speaking = False
        set_speaking(False)

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


# Lista dei tool disponibili per LangChain
tools = [get_current_time]
# Mappatura per l'esecuzione automatica dei tool basata sul nome
tool_map = {tool.name: tool for tool in tools}

def bootstrap_model():
    print("--- Avvio bootstrap del modello, solo se locale... ---")
    if LLM_PROVIDER == "ollama-local":
        try:
            # Prova a caricare il modello
            llm = ChatOllama(model=OLLAMA_MODEL)
            ai_msg = llm.invoke("Hello")
            print("--- Modello locale caricato con successo. ---")
        except Exception as e:
            print(f"Errore durante il caricamento del modello locale: {e}")
            print("Assicurati che Ollama sia in esecuzione e che il modello sia installato.")
    

def ask_llm(user_input):
    """Interroga il provider configurato usando LangChain e supporta i tool."""
    system_prompt = get_persona()
    
    # Inizializza il modello corretto tramite LangChain
    if LLM_PROVIDER == "anthropic":
        llm = ChatAnthropic(model=ANTHROPIC_MODEL)
    else:
        llm = ChatOllama(model=OLLAMA_MODEL)
    
    # Associa i tool al modello
    llm_with_tools = llm.bind_tools(tools)
    
    # Prepara la cronologia dei messaggi
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]
    
    try:
        # Prima chiamata: il modello decide se usare tool o rispondere
        ai_msg = llm_with_tools.invoke(messages)
        messages.append(ai_msg)
        # Se il modello ha richiesto l'uso di tool, esegui ogni chiamata
        if ai_msg.tool_calls:
            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call["name"].lower()
                if tool_name in tool_map:
                    selected_tool = tool_map[tool_name]
                    print(f"--- Eseguendo tool LangChain: {tool_name} ---")
                    # Invocazione del tool e concatenazione del messaggio di output
                    tool_output = selected_tool.invoke(tool_call["args"])
                    print(f"--- Output del tool: {tool_output} ---")
                    messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
            
            # Seconda chiamata dopo che i tool sono stati eseguiti per generare la risposta finale
            final_msg = llm_with_tools.invoke(messages)
            return final_msg.content
            
        return ai_msg.content
    except Exception as e:
        print(f"Errore durante l'interazione con l'LLM via LangChain: {e}")
        return f"Spiacente, ho avuto un intoppo tecnico con il mio cervello LangChain: {e}"

# Configuration
MODEL_PATH = "model"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
WAKE_WORDS = ["absalom","absalon","assalom","assalon"]
SLEEP_PHRASES = [
    "Vado in standby",
    "Buonanotte",
    "Sogni digitali",
    "Circuiti a riposo",
    "Off...",
    "Mi aggiusto i cavi",
    "A dopo",
    "Batteria in risparmio"
]
SAMPLE_RATE = 16000

# Audio queue and status
q = queue.Queue()
is_busy = False
is_awake = False
is_speaking = False

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
    bootstrap_model()
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
                    print(f"DEBUG: Sentito -> '{text}'")
                    if any(word in text for word in WAKE_WORDS):
                        print("\n[!] Ti ho sentito")
                        is_busy = True
                        set_busy(True)
                        # Identifica quale parola chiave è stata usata per rimuoverla dal prompt
                        trigger_word = next((w for w in WAKE_WORDS if w in text), None)
                        print("\n[!] Ti ho sentito")
                        speak("Eccomi!")
                        set_mode("awake")
                        is_awake = True
                        
                        # reset recognizer  
                        rec = KaldiRecognizer(model, SAMPLE_RATE)
                        
                        
                        # Svuota la coda per evitare di processare audio accumulato
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        is_busy = False
                        set_busy(False)
                    elif is_awake and text == "addormentati":
                        rec = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(WAKE_WORDS))
                        phrase = random.choice(SLEEP_PHRASES)
                        speak(phrase)
                        set_mode("asleep")
                        is_awake = False
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
