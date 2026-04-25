
from tts_manager import TTSManager
from face_client import FaceClient
import logging
import time
import json
import os
from datetime import datetime


class AlarmWorker:
    def __init__(self, face: FaceClient):
        self.face = face
    
    def run(self):
        """Background worker che controlla gli allarmi impostati."""
        logging.info("Alarm Worker avviato")
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
                                logging.info(f"SVEGLIA! Orario raggiunto: {current_time}")
                                
                                # Sveglia Absalom
                                self.face.set_mode("awake")
                                
                                # Messaggio personalizzato o generico
                                msg = alarm.get("message")
                                
                                if not msg:
                                    msg = "Genera un bel messaggio motivaziona per svegliarmi"
                                msg = ask_llm("L'utente ha chiesto di essere avvisato:"+msg)
                                # Esegui la sveglia in modo che possa parlare
                                TTSManager().speak(msg)
                                
                                # Disattiva l'allarme
                                alarm["active"] = False
                                updated = True
                        
                        if updated:
                            with open(alarms_path, "w", encoding="utf-8") as f:
                                json.dump(alarms, f, indent=4)
                            
            except Exception as e:
                logging.error(f"Errore nell'alarm_worker: {e}")
            
            time.sleep(30) # Controlla ogni 30 secondi