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
from stt_manager import STTManager
from tts_manager import TTSManager

import requests

import wave
import subprocess

from db import init_db
from dotenv import load_dotenv
from datetime import datetime
import threading
from telegram_manager import TelegramManager
from face_client import FaceClient
import constants
import config
import logging
from workers.dreaming_worker import DreamingWorker
from workers.remote_commands_worker import RemoteCommandsWorker
from workers.alarm_worker import AlarmWorker
from workers.ingest_worker import IngestWorker
from utils import play_audio
from agent import Agent

logging.basicConfig(
    level=logging.INFO,  # Mostra tutto (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("absalom.log"),  # Scrive su file
        logging.StreamHandler(sys.stdout)    # Scrive anche su console
    ]
)




last_interaction_time = 0

telegram_bot = None

_piper_voice = None

# Inizializzazione Client Faccia
face = FaceClient(config.BASE_URL)

agent = Agent()

def ask_llm(user_input):
    return agent.ask(user_input)

def abk_llm(user_input):
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
        if config.LLM_PROVIDER == "anthropic":
            llm = ChatAnthropic(model=config.ANTHROPIC_MODEL)
        elif config.LLM_PROVIDER == "google":
            llm = ChatGoogleGenerativeAI(model=config.GOOGLE_MODEL, google_api_key=config.GOOGLE_API_KEY)
        else:
            llm = ChatOllama(model=config.OLLAMA_MODEL)
        
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
                        TTSManager().speak("Sto controllando sul registro elettronico.")
                    else:
                        TTSManager().speak(random.choice(constants.TOOL_PHRASES))
                        
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


def bootstrap_model():
    print("--- Avvio bootstrap del modello, solo se locale... ---")
    if config.LLM_PROVIDER == "ollama-local":
        try:
            # Prova a caricare il modello
            llm = ChatOllama(model=config.OLLAMA_MODEL)
            ai_msg = llm.invoke("Hello")
            print("--- Modello locale caricato con successo. ---")
        except Exception as e:
            print(f"Errore durante il caricamento del modello locale: {e}")
            print("Assicurati che Ollama sia in esecuzione e che il modello sia installato.")
    


def start_assistant(debug=False, telegram=False):
    # Esegui il suono di avvio
    print("--- Riproduzione suono di avvio ---")
    face.set_loading(True)
    #play_audio("sounds/startup.mp3")
    init_db()
    bootstrap_model()
    tts_manager = TTSManager(face)
    
    if telegram:
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
            speak_callback=TTSManager().speak,
            set_mode_callback=face.set_mode,
            get_status_callback=face.get_robot_status
        )
        telegram_bot.start()
    
    stt_manager = STTManager()

    logging.info(f"Absalom OS avviato.")
    face.set_loading(False)
    is_busy = face.get_robot_status().get("is_busy", False)
    is_awake = face.get_robot_status().get("is_awake", False)
    last_interaction_time = 0

    #start "firefox --kiosk http://localhost:5000"
    subprocess.run(["firefox", "--kiosk", "http://localhost:5000"])
    try:
        while True:
            if is_awake and (time.time() - last_interaction_time > config.INACTIVITY_TIMEOUT) and not face.is_speaking():
                logging.info("Timeout di inattività raggiunto. Standby...")
                phrase = random.choice(constants.SLEEP_PHRASES)
                TTSManager().speak(phrase)
                face.set_mode("asleep")
                is_awake = False

            if stt_manager.listen_for_wakeword():
                # Riproduce il suono di conferma
                last_interaction_time = time.time()
                play_audio("sounds/bubblepop.mp3")
                if not is_awake:
                    is_awake = True
                    face.set_mode("awake")

    except KeyboardInterrupt:
        logging.info("Spegni assistente...")
    except Exception as e:
        logging.error(f"Errore durante l'esecuzione: {e}")

if __name__ == "__main__":
    # Creazione delle cartelle se mancano
    os.makedirs("persona/memory", exist_ok=True)
    os.makedirs("persona/wiki/raw", exist_ok=True)
    
    # Avvio thread comandi remoti
    remote_commands_worker = RemoteCommandsWorker(face)
    threading.Thread(target=remote_commands_worker.run, daemon=True).start()
    
    # Avvio thread allarmi
    alarm_worker = AlarmWorker(face)
    threading.Thread(target=alarm_worker.run, daemon=True).start()
    
    # Avvio thread sogni
    dreaming_worker = DreamingWorker(face)
    threading.Thread(target=dreaming_worker.run, daemon=True).start()

    # Avvio thread ingestione
    ingest_worker = IngestWorker(face)
    threading.Thread(target=ingest_worker.run, daemon=True).start()
    
    parser = argparse.ArgumentParser(description="Absalom OS Assistant")
    parser.add_argument("--debug", action="store_true", help="Avvia in modalità debug (input da tastiera)")
    parser.add_argument("--telegram", action="store_true", help="Avvia in modalità telegram")
    args = parser.parse_args()
    
    start_assistant(debug=args.debug, telegram=args.telegram)
