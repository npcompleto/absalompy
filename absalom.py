import time
import numpy as np
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
from faster_whisper import WhisperModel
import requests
from piper.voice import PiperVoice
import wave
import subprocess
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.memory import remember
from tools.school_tool import add_school_event, list_school_events
from tools.time_tool import get_next_week_start_date, set_alarm
from tools.wiki_tool import wiki_list_entries, wiki_read, wiki_write, wiki_search, wiki_ingest_raw
from db import init_db
from dotenv import load_dotenv
from datetime import datetime
import threading
from telegram_manager import TelegramManager
from face_client import FaceClient
from constants import SLEEP_PHRASES, THINKING_PHRASES, TOOL_PHRASES

# Carica variabili d'ambiente da .env
# LLM Configuration

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama-local").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip()

PIPER_MODEL_DIR = "models/piper"
PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
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

# Inizializza Whisper (usiamo tiny per velocità, soprattutto su Raspberry Pi)
print("--- Caricamento modello Whisper (tiny)... ---")
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

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

q = queue.Queue()
INACTIVITY_TIMEOUT = 120  # 120 secondi di inattività per lo standby
last_interaction_time = 0

telegram_bot = None

_piper_voice = None

# Lista dei tool disponibili per LangChain
tools = [
    list_school_events, 
    get_next_week_start_date, 
    set_alarm,
    wiki_list_entries, 
    wiki_read, 
    wiki_write, 
    wiki_search, 
    wiki_ingest_raw,
    remember
]
# Mappatura per l'esecuzione automatica dei tool basata sul nome
tool_map = {tool.name: tool for tool in tools}

# Inizializzazione Client Faccia
face = FaceClient(BASE_URL)

def download_model():
    os.makedirs(os.path.dirname(VOSK_MODEL_PATH), exist_ok=True)
    print(f"--- Modello non trovato. Download in corso da {VOSK_MODEL_URL} ---")
    zip_path = VOSK_MODEL_NAME + ".zip"
    urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path)
    print("Download completato. Estrazione...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("models")
    
    os.remove(zip_path)
    print("Modello pronto.\n")

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
    
    face.set_speaking(True)
    
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
            face.set_speaking(True)
            return_code = play_audio(filename)
            face.set_speaking(False)
            
            # Se il processo è stato ucciso (non-zero return code), interrompiamo la lettura dei pezzi successivi
            if return_code != 0:
                print(f"Riproduzione interrotta al pezzo {i+1} (RC: {return_code})")
                break
                
    except Exception as e:
        print(f"Errore durante la sintesi vocale: {e}")
    finally:
        face.set_speaking(False)

def get_persona():
    """Carica e concatena i file della personalità."""
    persona = ""
    try:
        # Carichiamo sia l'identità principale che quella del Bibliotecario/Wiki
        for filename in ["Identity.md", "Librarian.md", "Researcher.md"]:
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

def get_long_term_memory():
    try:
        with open("persona/memory/long_term_memory.txt", "r", encoding="utf-8") as f:
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
    
    long_term_memory = get_long_term_memory()
    if long_term_memory:
        system_prompt += f"\nQui trovi la memoria a lungo termine:\n{long_term_memory}\n"
    
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
            MAX_LOOP = 20
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
                        
                        # Gestione Multimodale: se il tool restituisce dati multimediali (es. wiki_ingest_raw)
                        if isinstance(tool_output, str) and tool_output.startswith("__INGEST_DATA__:"):
                            try:
                                data_json = tool_output.split("__INGEST_DATA__:", 1)[1]
                                data = json.loads(data_json)
                                
                                if data.get("type") == "media_list":
                                    content_blocks = [{"type": "text", "text": data.get("text_info", "Dati estratti dai file:")}]
                                    
                                    # Aggiunta blocchi di testo
                                    for t in data.get("text_blocks", []):
                                        content_blocks.append({"type": "text", "text": f"\n\nCONTENUTO FILE {t['filename']}:\n{t['content']}"})
                                    
                                    # Aggiunta immagini
                                    prov = LLM_PROVIDER.lower().strip()
                                    for m in data["media"]:
                                        if prov == "google":
                                            content_blocks.append({
                                                "type": "media",
                                                "mime_type": "image/jpeg",
                                                "data": m["data"]
                                            })
                                        elif prov == "anthropic":
                                            content_blocks.append({
                                                "type": "image",
                                                "source": {
                                                    "type": "base64",
                                                    "media_type": "image/jpeg",
                                                    "data": m["data"]
                                                }
                                            })
                                        else:
                                            # Fallback per altri provider multimodali (es standard LangChain)
                                            content_blocks.append({
                                                "type": "image_url",
                                                "image_url": {"url": f"data:image/jpeg;base64,{m['data']}"}
                                            })
                                    messages.append(ToolMessage(content=content_blocks, tool_call_id=tool_call["id"]))
                                else:
                                    messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
                            except Exception as je:
                                print(f"Errore parsing dati ingest: {je}")
                                messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
                        else:
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
            face.set_last_interaction(user_input, final_answer)
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
    if not face.get_robot_status().get("is_busy"):
        q.put(bytes(indata))

def start_assistant(debug=False):
    # Esegui il suono di avvio
    print("--- Riproduzione suono di avvio ---")
    face.set_loading(True)
    #play_audio("sounds/startup.mp3")
    init_db()
    bootstrap_model()
    
    # Inizializza Telegram Bot
    global telegram_bot
    def ask_llm_with_busy(text):
        face.set_busy(True)
        try:
            return ask_llm(text)
        finally:
            face.set_busy(False)
            
    telegram_bot = TelegramManager(
        ask_callback=ask_llm_with_busy,
        speak_callback=speak,
        set_mode_callback=face.set_mode,
        get_status_callback=face.get_robot_status
    )
    telegram_bot.start()

    if not os.path.exists(VOSK_MODEL_PATH):
        download_model()
    
    # Initialize model
    model = Model(VOSK_MODEL_PATH)
    # Avviamo con un recognizer LIMITATO alle sole wakewords + [unk] per efficienza
    grammar = json.dumps(WAKE_WORDS + ["[unk]"])
    rec = KaldiRecognizer(model, VOSK_RATE, grammar)

    print(f"\n>>> Absalom OS avviato. In ascolto per la parola chiave: '{WAKE_WORDS}'...")
    face.set_loading(False)
    is_busy = face.get_robot_status().get("is_busy", False)
    is_awake = face.get_robot_status().get("is_awake", False)
    last_interaction_time = 0
    
    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=16000, dtype='int16',
                               channels=1, callback=callback, device=AUDIO_DEVICE_INDEX):
            while True:
                # Timer di inattività: se sveglio e timeout superato, vai in standby
                if is_awake and (time.time() - last_interaction_time > INACTIVITY_TIMEOUT) and not face.is_speaking():
                    print("\n[!] Timeout di inattività raggiunto. Standby...")
                    phrase = random.choice(SLEEP_PHRASES)
                    speak(phrase)
                    face.set_mode("asleep")
                    is_awake = False
                
                try:
                    data = q.get(timeout=5) # Timeout per permettere il controllo dell'inattività
                    
                    # Se la frequenza hardware è diversa da quella di Vosk (16000), ricampioniamo nel thread principale
                    if SAMPLE_RATE != VOSK_RATE:
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        num_samples = len(audio_data)
                        new_num_samples = int(num_samples * VOSK_RATE / SAMPLE_RATE)
                        resampled_audio = np.interp(
                            np.linspace(0, num_samples, new_num_samples, endpoint=False),
                            np.arange(num_samples),
                            audio_data
                        ).astype(np.int16)
                        data = resampled_audio.tobytes()
                        
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower().strip()
                    
                    # Se non abbiamo sentito nulla, ignoriamo
                    if not text:
                        continue
                        
                    # Cerchiamo se una delle wakeword è stata rilevata da Vosk
                    trigger_word = next((w for w in WAKE_WORDS if w in text), None)
                    
                    if trigger_word:
                        print(f"\n[!] Wakeword '{trigger_word}' rilevata tramite Vosk!")
                        
                        # Riproduce il suono di conferma
                        play_audio("sounds/bubblepop.mp3")
                        
                        if not is_awake:
                            is_awake = True
                            face.set_mode("awake")
                        
                        # Svuotiamo la coda per ignorare l'audio precedente (inclusa la wakeword e il bip)
                        while not q.empty():
                            try:
                                q.get_nowait()
                            except queue.Empty:
                                break
                                
                        print(">>> In ascolto per 5 secondi con Whisper...")
                        face.set_loading(True)
                        
                        whisper_buffer = []
                        start_time = time.time()
                        
                        # Ascolto per 5 secondi esatti
                        while time.time() - start_time < 5:
                            try:
                                # Timeout breve per controllare il ciclo del tempo
                                d = q.get(timeout=0.5)
                                if SAMPLE_RATE != VOSK_RATE:
                                    audio_data = np.frombuffer(d, dtype=np.int16)
                                    num_samples = len(audio_data)
                                    new_num_samples = int(num_samples * VOSK_RATE / SAMPLE_RATE)
                                    resampled_audio = np.interp(
                                        np.linspace(0, num_samples, new_num_samples, endpoint=False),
                                        np.arange(num_samples),
                                        audio_data
                                    ).astype(np.int16)
                                    whisper_buffer.append(resampled_audio)
                                else:
                                    whisper_buffer.append(np.frombuffer(d, dtype=np.int16))
                            except queue.Empty:
                                continue
                        
                        if not whisper_buffer:
                            face.set_loading(False)
                            continue
                        play_audio("sounds/bubblepop.mp3")    
                        # Uniamo il buffer e convertiamo in float32 per Whisper
                        full_audio = np.concatenate(whisper_buffer).astype(np.float32) / 32768.0
                        
                        # Trascrizione con Whisper
                        print("--- Trascrizione in corso... ---")
                        segments, info = whisper_model.transcribe(full_audio, language="it", beam_size=5)
                        text = " ".join([s.text for s in segments]).strip().lower()
                        
                        face.set_loading(False)
                        
                        if not text:
                            print("DEBUG: Whisper non ha rilevato testo.")
                            continue
                            
                        print(f"DEBUG: Whisper ha trascritto -> '{text}'")
                        
                        last_interaction_time = time.time()
                        
                        # Pulisce il testo dalle wakeword se presenti
                        command = text
                        for w in WAKE_WORDS:
                            command = command.replace(w, "")
                        command = re.sub(r'^[,.!?;:\s]+|[,.!?;:\s]+$', '', command).strip()
                        
                        if not command:
                            print("DEBUG: Nessun comando dopo la wakeword.")
                            continue
                            
                        # Procediamo con l'elaborazione del comando
                        face.set_busy(True)
                        try:
                            response = ask_llm(command)
                            face.send_chat_response(response)
                            speak(response)
                        finally:
                            face.set_busy(False)
                            # Resetta il recognizer per il prossimo ciclo
                            rec.Reset()
                            
                        # Gestione speciale per comando di addormentamento se vogliamo forzarlo via codice
                        if "addormentati" in command:
                           face.set_mode("asleep")
                           is_awake = False
                        
                        # Svuota la coda per evitare loop di feedback o audio accumulato
                        while not q.empty():
                            try: q.get_nowait()
                            except queue.Empty: break
                        face.set_busy(False)
                        
                    else:
                        # Se siamo addormentati e non sentiamo la wakeword, ignoriamo il testo
                        print(f"DEBUG: Testo ignorato (nessuna wakeword): '{text}'")
                        pass

    except KeyboardInterrupt:
        print("\nSpegni assistente...")
    except Exception as e:
        print(f"\nErrore durante l'esecuzione: {e}")

def remote_commands_worker():
    """Thread di background che interroga il server per comandi remoti (es. da Web UI)."""
    print("--- Remote Commands Worker avviato ---")
    while True:
        try:
            time.sleep(3) # Polling ogni 3 secondi
            
            # Se siamo già occupati, saltiamo il polling per questo ciclo
            if face.get_robot_status().get("is_busy"):
                continue
                
            state = face.get_full_status()
            if state:
                # Sincronizza lo stato locale con quello del server
                face.set_busy(state.get("busy", False))
                is_awake = (state.get("mode") == "awake")
                
                # Controllo Trigger Wiki Ingest
                if state.get("ingest_requested"):
                    print("[!] Ricevuto segnale di ingestione Wiki da Web UI.")
                    
                    face.set_busy(True)
                    
                    try:
                        # Reset del trigger sul server prima di iniziare
                        face.reset_ingest_trigger()
                        
                        # Feedback vocale come richiesto
                        speak("Ho ricevuto i documenti. Passo subito i documenti al Bibliotecario per l'archiviazione.")
                        
                        # Trigger dell'ingestione tramite LLM con categoria se presente
                        category = state.get("ingest_category")
                        prompt = "Bibliotecario, ingerisci i file presenti nella cartella raw nella Wiki e sintetizzali."
                        if category:
                            prompt += f" La categoria specifica in cui salvare queste informazioni è: {category}."
                            
                        ingest_response = ask_llm(prompt)
                        speak(ingest_response)
                    finally:
                        face.set_busy(False)
                
                # Controllo Messaggi Chat da Web
                if state.get("pending_chat_msg"):
                    chat_msg = state.get("pending_chat_msg")
                    print(f"[!] Ricevuto messaggio chat da Web: '{chat_msg}'")
                    
                    face.set_busy(True)
                    
                    try:
                        # Reset del messaggio pendente sul server
                        face.reset_pending_chat()
                        
                        # Elaborazione tramite LLM
                        response = ask_llm(chat_msg)
                        
                        # Salvataggio risposta per la Web UI e speak
                        face.send_chat_response(response)
                        speak(response)
                    finally:
                        face.set_busy(False)
        except Exception as e:
            # Silenzioso per non sporcare i log se il server è momentaneamente giù
            pass

def alarm_worker():
    """Background worker che controlla gli allarmi impostati."""
    print("--- Alarm Worker avviato ---")
    alarms_path = "persona/alarms.json"
    
    last_checked_minute = ""
    
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Controlla solo una volta al minuto
            if current_time != last_checked_minute:
                last_checked_minute = current_time
                
                if os.path.exists(alarms_path):
                    with open(alarms_path, "r", encoding="utf-8") as f:
                        alarms = json.load(f)
                    
                    updated = False
                    for alarm in alarms:
                        if alarm.get("active") and alarm.get("time") == current_time:
                            print(f"[!] SVEGLIA! Orario raggiunto: {current_time}")
                            
                            # Sveglia Absalom
                            face.set_mode("awake")
                            
                            # Messaggio personalizzato o generico
                            msg = alarm.get("message")
                            
                            if not msg:
                                msg = "Genera un bel messaggio motivaziona per svegliarmi"
                            msg = ask_llm("L'utente ha chiesto di essere avvisato:"+msg)
                            # Esegui la sveglia in modo che possa parlare
                            speak(msg)
                            
                            # Disattiva l'allarme
                            alarm["active"] = False
                            updated = True
                    
                    if updated:
                        with open(alarms_path, "w", encoding="utf-8") as f:
                            json.dump(alarms, f, indent=4)
                            
        except Exception as e:
            print(f"Errore nell'alarm_worker: {e}")
        
        time.sleep(30) # Controlla ogni 30 secondi

def dreaming_worker():
    """Processo di background che 'sogna' quando il robot dorme."""
    print("--- Dreaming Worker avviato ---")
    while True:
        try:
            if not face.is_awake() and not face.is_loading():
                print("sto sognando")
        except Exception:
            pass
        time.sleep(120) # Aspetta 2 minuti (120 secondi)

if __name__ == "__main__":
    # Creazione delle cartelle se mancano
    os.makedirs("persona/memory", exist_ok=True)
    os.makedirs("persona/wiki/raw", exist_ok=True)
    
    # Avvio thread comandi remoti
    threading.Thread(target=remote_commands_worker, daemon=True).start()
    
    # Avvio thread allarmi
    threading.Thread(target=alarm_worker, daemon=True).start()
    
    # Avvio thread sogni
    threading.Thread(target=dreaming_worker, daemon=True).start()
    
    parser = argparse.ArgumentParser(description="Absalom OS Assistant")
    parser.add_argument("--debug", action="store_true", help="Avvia in modalità debug (input da tastiera)")
    args = parser.parse_args()
    
    start_assistant(debug=args.debug)
