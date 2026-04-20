import time
import os
import sys
import argparse
import re
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.school_tool import add_school_event, list_school_events
from tools.time_tool import get_next_week_start_date
from db import init_db
from dotenv import load_dotenv
from datetime import datetime

# Carica variabili d'ambiente da .env
# LLM Configuration

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama-local")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

PIPER_MODEL_DIR = "models/piper"
PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
PIPER_MODEL_PATH = os.path.join(PIPER_MODEL_DIR, PIPER_MODEL_NAME)
PIPER_CONFIG_PATH = PIPER_MODEL_PATH + ".json"
PIPER_MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}?download=true"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}.json?download=true"

BASE_URL = "http://127.0.0.1:5000"

MODEL_PATH = "model"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
WAKE_WORDS = ["absalom","absalon","assalom","assalon","okron","ok ron", "ok on","ciaoron","ciao ron"]
SLEEP_PHRASES = [
    "Vado in standby",
    "Buonanotte",
    "Che sonno! Buonanotte.",
    "Ci sentiamo dopo",
    "A dopo"
]

THINKING_PHRASES = [
    "Fammi pensare",
    "Un momento",
    "Ci penso un attimo",
    "Ok!"
]

TOOL_PHRASES = [
    "Ancora un attimo",
    "Devo verificare ancora una cosa",
    "Ci sono quasi",
    "Controllo prima una cosa"
]

SAMPLE_RATE = 16000

# Audio queue and status
q = queue.Queue()
is_busy = False
is_awake = False
is_speaking = False
INACTIVITY_TIMEOUT = 120  # 10 secondi di inattività per lo standby
last_interaction_time = 0

_piper_voice = None
last_interaction_time = 0

# Lista dei tool disponibili per LangChain
tools = [list_school_events, get_next_week_start_date]
# Mappatura per l'esecuzione automatica dei tool basata sul nome
tool_map = {tool.name: tool for tool in tools}

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

def set_loading(loading_status):
    try:
        requests.post(f"{BASE_URL}/control", json={"loading": loading_status})
    except Exception as e:
        print(f"Errore set_loading: {e}")

def set_angry(angry_status):
    try:
        requests.post(f"{BASE_URL}/control", json={"angry": angry_status})
    except Exception as e:
        print(f"Errore set_angry: {e}")

def set_sad(sad_status):
    try:
        requests.post(f"{BASE_URL}/control", json={"sad": sad_status})
    except Exception as e:
        print(f"Errore set_sad: {e}")

def set_last_interaction(user_text, bot_text):
    try:
        requests.post(f"{BASE_URL}/control", json={
            "last_interaction": {
                "user": user_text,
                "bot": bot_text
            }
        })
    except Exception as e:
        print(f"Errore set_last_interaction: {e}")

def reset_face():
    set_sad(False)
    set_angry(False)
    set_loading(False)
    set_busy(False)
    set_speaking(False)
    set_mode("awake")



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

def play_audio(filepath):
    """Riproduce un file audio specificato. Ritorna il codice di uscita del processo."""
    if os.path.exists(filepath):
        try:
            process = subprocess.run(["ffplay", "-nodisp", "-autoexit", filepath], 
                           stderr=subprocess.DEVNULL, 
                           stdout=subprocess.DEVNULL)
            return process.returncode
        except Exception as e:
            print(f"Errore durante la riproduzione di {filepath}: {e}")
            return -1
    else:
        print(f"File audio non trovato: {filepath}")
        return -1

def speak(text):
    global is_speaking
    
    if not isinstance(text, str):
        text = str(text)
    
    # Rimuove emoji e caratteri speciali
    text = re.sub(r'[^\w\s\d.,!?;:()\'\"-/]', '', text)
    
    # Spezzetta il testo in periodi (usa lookbehind per non rimuovere il delimitatore o semplicemente splitta)
    # Questa regex splitta dopo i caratteri di punteggiatura seguiti da spazio
    sentences = [s.strip() for s in re.split(r'(?<=[!.;?])\s+', text) if s.strip()]
    
    if not sentences:
        return

    print(f"Absalom dice: '{text}' (in {len(sentences)} pezzi)")
    voice = get_piper_voice()
    filename = "speech_chunk.wav"
    
    is_speaking = True
    set_speaking(True)
    
    try:
        for i, sentence in enumerate(sentences):
            print(f"Sintesi pezzo {i+1}/{len(sentences)}: '{sentence}'")
            with wave.open(filename, "wb") as wav_file:
                for j, chunk in enumerate(voice.synthesize(sentence)):
                    if j == 0:
                        wav_file.setnchannels(chunk.sample_channels)
                        wav_file.setsampwidth(chunk.sample_width)
                        wav_file.setframerate(chunk.sample_rate)
                    wav_file.writeframes(chunk.audio_int16_bytes)
            
            # Riproduce il pezzo e controlla se è stato interrotto (pkill)
            return_code = play_audio(filename)
            
            # Se il processo è stato ucciso (non-zero return code), interrompiamo la lettura dei pezzi successivi
            if return_code != 0:
                print(f"Riproduzione interrotta al pezzo {i+1} (RC: {return_code})")
                break
                
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

def save_to_memory(user_input, absalom_response):
    """Salva l'interazione nella memoria persistente in formato yyyy-MM-DD.txt."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder = os.path.join("persona", "memory")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"{date_str}.txt")
        
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"Utente: {user_input}\n")
            f.write(f"Absalom: {absalom_response}\n\n")
    except Exception as e:
        print(f"Errore durante il salvataggio della memoria: {e}")

def get_today_memory():
    """Recupera la memoria della giornata corrente se esistente."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join("persona", "memory", f"{date_str}.txt")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"Errore nel recupero della memoria: {e}")
    return ""



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
    """Interfaccia l'assistente con l'LLM configurato, gestendo i tool e la personalità."""
    system_prompt = get_persona()
    
    # Aggiunge la memoria odierna al prompt di sistema come contesto
    today_memory = get_today_memory()
    if today_memory:
        system_prompt += "\n Oggi è il " + datetime.now().strftime("%Y-%m-%d") + " ed è " + datetime.now().strftime("%A") + ".\n"
        system_prompt += f"\nQui trovi la cronologia della conversazione di oggi per darti contesto:\n{today_memory}\n"
    
    # Inizializzazione del modello LangChain corretto
    try:
        if LLM_PROVIDER == "anthropic":
            llm = ChatAnthropic(model=ANTHROPIC_MODEL)
        elif LLM_PROVIDER == "google":
            llm = ChatGoogleGenerativeAI(model=GOOGLE_MODEL, google_api_key=GOOGLE_API_KEY)
        else:
            llm = ChatOllama(model=OLLAMA_MODEL)
        
        # Binding dei tool alla catena
        llm_with_tools = llm.bind_tools(tools)
        
        # Preparazione dei messaggi per la conversazione
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        # Loop di iterazione per gestire eventuali tool requests
        final_answer = ""
        for step in range(5):  # Limite di sicurezza per evitare loop infiniti
            print(f"--- Richiesta LLM (Passaggio {step + 1})... ---")
            ai_msg = llm_with_tools.invoke(messages)
            messages.append(ai_msg)
            
            # Se l'LLM ha risposto con del testo e NON ha tool call, abbiamo finito
            if not ai_msg.tool_calls:
                content = ai_msg.content
                # Gestione dei contenuti che possono essere una lista di blocchi (comune in alcuni provider)
                if isinstance(content, list):
                    final_answer = " ".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in content])
                else:
                    final_answer = str(content)
                break
                
            # Se l'LLM ha richiesto l'uso di tool, eseguiamo i task
            loop_count = 0
            MAX_LOOP = 3
            for tool_call in ai_msg.tool_calls:
                loop_count += 1
                if loop_count > MAX_LOOP:
                    return "Sono andato in confusione. Riproviamo?"
                tool_name = tool_call["name"].lower()
                # Cerchiamo il tool per nome in modo case-insensitive
                selected_tool = tool_map.get(tool_name)
                
                if selected_tool:
                    print(f"--- Eseguendo tool: {tool_name} ---")
                    if tool_name == "list_school_events":
                        speak("Sto controllando sul registro elettronico.")
                    else:
                        speak(random.choice(TOOL_PHRASES))
                        
                    try:
                        tool_output = selected_tool.invoke(tool_call["args"])
                        print(f"--- Risultato del tool: {tool_output} ---")
                        messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
                    except Exception as te:
                        error_text = f"Errore nell'esecuzione del tool {tool_name}: {te}"
                        print(error_text)
                        messages.append(ToolMessage(content=error_text, tool_call_id=tool_call["id"]))
                else:
                    error_text = f"Tool '{tool_name}' richiesto ma non trovato."
                    print(error_text)
                    messages.append(ToolMessage(content=error_text, tool_call_id=tool_call["id"]))
        
        # Sintesi vocale, salvataggio memoria e log della risposta finale
        if final_answer:
            save_to_memory(user_input, final_answer)
            set_last_interaction(user_input, final_answer)
        else:
            print("--- Nessuna risposta testuale ricevuta dall'LLM. ---")
            
        print("Risposta completa: " + final_answer)
        return final_answer
        
    except Exception as e:
        error_msg = f"Eccezione duranteask_llm: {e}"
        print(error_msg)
        return error_msg



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

def start_assistant(debug=False):
    # Esegui il suono di avvio
    print("--- Riproduzione suono di avvio ---")
    set_loading(True)
    play_audio("sounds/startup.mp3")
    init_db()
    bootstrap_model()
    
    
    set_loading(False)
    if debug:
        print("\n>>> Absalom OS avviato in modalità DEBUG (input da tastiera).")
        print("Scrivi qualcosa per parlare con Absalom (o 'esci' per terminare):")
        set_mode("awake")
        while True:
            try:
                text = input("\nTu: ")
                if not text.strip():
                    continue
                if text.lower() in ["esci", "quit", "exit"]:
                    break
                
                if text.lower().startswith("/emo"):
                    parts = text.split()
                    if len(parts) < 2:
                        print("Uso: /emo [sad|nosad|angry|noangry|loading|noloading|awake|asleep|reset]")
                        continue
                    
                    cmd = parts[1].lower()
                    if cmd == "sad": 
                        reset_face()
                        set_sad(True)
                    elif cmd == "nosad": set_sad(False)
                    elif cmd == "angry": 
                        reset_face()
                        set_angry(True)
                    elif cmd == "noangry": set_angry(False)
                    elif cmd == "loading": 
                        reset_face()
                        set_loading(True)
                    elif cmd == "noloading": set_loading(False)
                    elif cmd == "awake": set_mode("awake")
                    elif cmd == "asleep": set_mode("asleep")
                    elif cmd == "reset":
                        reset_face()
                    else:
                        print(f"Emozione '{cmd}' non riconosciuta.")
                    continue

                print(f"Analisi richiesta: '{text}'")
                # In modalità debug saltiamo i thinking phrases per velocità o li teniamo?
                # Per ora saltiamo sd e vosk
                response = ask_llm(text)
                speak(response)
                
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        print("\nUscita dalla modalità DEBUG.")
        return

    if not os.path.exists(MODEL_PATH):
        download_model()

    # Initialize model
    model = Model(MODEL_PATH)
    # Avviamo con un recognizer completo per catturare sia la wakeword che il comando insieme
    rec = KaldiRecognizer(model, SAMPLE_RATE)

    print(f"\n>>> Absalom OS avviato. In ascolto per la parola chiave: '{WAKE_WORDS}'...")

    global is_busy
    global is_awake
    global last_interaction_time
    
    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            while True:
                # Timer di inattività: se sveglio e timeout superato, vai in standby
                if is_awake and (time.time() - last_interaction_time > INACTIVITY_TIMEOUT):
                    print("\n[!] Timeout di inattività raggiunto. Standby...")
                    phrase = random.choice(SLEEP_PHRASES)
                    speak(phrase)
                    set_mode("asleep")
                    is_awake = False
                
                try:
                    data = q.get(timeout=5) # Timeout per permettere il controllo dell'inattività
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower().strip()
                    
                    if not text:
                        continue
                    
                    print(f"DEBUG: Sentito -> '{text}'")
                    
                    # Cerca se nel testo è presente una delle wakeword
                    trigger_word = next((w for w in WAKE_WORDS if w in text), None)
                    
                    if trigger_word:
                        print(f"\n[!] Wakeword '{trigger_word}' rilevata!")
                        last_interaction_time = time.time()
                        
                        # Estrae il comando rimuovendo la wakeword
                        command = text.replace(trigger_word, "").strip()
                        # Rimuove eventuale punteggiatura iniziale/finale dal comando
                        command = re.sub(r'^[,.!?;:\s]+|[,.!?;:\s]+$', '', command)
                        
                        if not is_awake:
                            is_awake = True
                            set_mode("awake")
                            print("Svegliato dalla wakeword.")
                        
                        is_busy = True
                        set_busy(True)
                        
                        if command:
                            if command == "addormentati":
                                phrase = random.choice(SLEEP_PHRASES)
                                speak(phrase)
                                set_mode("asleep")
                                is_awake = False
                            else:
                                print(f"Comando diretto rilevato: '{command}'")
                                speak(random.choice(THINKING_PHRASES))
                                response = ask_llm(command)
                                speak(response)
                        else:
                            # Solo wakeword pronunciata
                            speak("Eccomi!")
                        
                        # Svuota la coda per evitare loop di feedback o audio accumulato
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        is_busy = False
                        set_busy(False)
                        
                    elif is_awake:
                        # Se siamo già svegli, processiamo tutto come comando (stile sessione)
                        last_interaction_time = time.time()
                        is_busy = True
                        set_busy(True)
                        
                        if text == "addormentati":
                            phrase = random.choice(SLEEP_PHRASES)
                            speak(phrase)
                            set_mode("asleep")
                            is_awake = False
                        else:
                            print(f"Analisi richiesta (sessione): '{text}'")
                            speak(random.choice(THINKING_PHRASES))
                            ask_llm(text)
                        
                        # Svuota la coda
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        is_busy = False
                        set_busy(False)
                    
                    else:
                        # Se siamo addormentati e non sentiamo la wakeword, ignoriamo il testo
                        print(f"DEBUG: Testo ignorato (nessuna wakeword): '{text}'")
                        pass

    except KeyboardInterrupt:
        print("\nSpegni assistente...")
    except Exception as e:
        print(f"\nErrore durante l'esecuzione: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Absalom OS Assistant")
    parser.add_argument("--debug", action="store_true", help="Avvia in modalità debug (input da tastiera)")
    args = parser.parse_args()
    
    start_assistant(debug=args.debug)
