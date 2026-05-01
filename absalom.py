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
        logging.info("Avvio Telegram Bot")
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
        logging.info("Telegram Bot avviato.")
    
    stt_manager = STTManager()

    logging.info(f"Absalom OS avviato.")
    face.set_loading(False)
    is_busy = face.get_robot_status().get("is_busy", False)
    is_awake = face.get_robot_status().get("is_awake", False)
    last_interaction_time = 0

    # Avvio interfaccia in background
    logging.info("Avvio interfaccia grafica (Firefox Kiosk)...")
    subprocess.Popen(["firefox", "--kiosk", "http://localhost:5000"], 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                
                if not is_awake:
                    is_awake = True
                    face.set_mode("awake")
                face.set_speaking(True)
                play_audio(TTSManager().recurrent_audio.get("dimmi"))
                face.set_speaking(False)
                face.set_loading(True)
                question = stt_manager.listen_for_question_realtime()
                face.set_loading(False)
                play_audio(TTSManager().recurrent_audio.get("ricevuto"))
                logging.info(f">>> Domanda: {question}")
                if question != "":
                    answer = agent.ask(question)
                    TTSManager().speak(answer)

    except KeyboardInterrupt:
        logging.info("Spegni assistente...")
    except Exception as e:
        logging.error(f"Errore durante l'esecuzione: {e}")

if __name__ == "__main__":
    # Creazione delle cartelle se mancano
    os.makedirs("persona/memory", exist_ok=True)
    
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
    parser.add_argument("--hailo", action="store_true", help="Usa Hailo per l'accelerazione di Whisper")
    args = parser.parse_args()
    
    if args.hailo:
        config.USE_HAILO = True
        logging.info("Hailo acceleration enabled via flag.")
    
    start_assistant(debug=args.debug, telegram=args.telegram)
