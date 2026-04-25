import time
import logging
from tts_manager import TTSManager
from face_client import FaceClient
from agent import Agent

class RemoteCommandsWorker:
    def __init__(self, face: FaceClient):
        self.face = face
    
    def run(self):
        """Thread di background che interroga il server per comandi remoti (es. da Web UI)."""
        logging.info("Remote Commands Worker avviato")
        while True:
            try:
                time.sleep(3) # Polling ogni 3 secondi
                
                # Se siamo già occupati, saltiamo il polling per questo ciclo
                if self.face.get_robot_status().get("is_busy"):
                    continue
                
                state = self.face.get_full_status()
                if state:
                    # Sincronizza lo stato locale con quello del server
                    self.face.set_busy(state.get("busy", False))
                    is_awake = (state.get("mode") == "awake")
                
                    # Controllo Trigger Wiki Ingest
                    """if state.get("ingest_requested"):
                        logging.info("Ricevuto segnale di ingestione Wiki da Web UI.")
                        
                        self.face.set_busy(True)
                        
                        try:
                            # Reset del trigger sul server prima di iniziare
                            face.reset_ingest_trigger()
                            
                            # Feedback vocale come richiesto
                            TTSManager().speak("Ho ricevuto i documenti. Passo subito i documenti al Bibliotecario per l'archiviazione.")
                            
                            # Trigger dell'ingestione tramite LLM con categoria se presente
                            category = state.get("ingest_category")
                            prompt = "Bibliotecario, ingerisci i file presenti nella cartella raw nella Wiki e sintetizzali."
                            if category:
                                prompt += f" La categoria specifica in cui salvare queste informazioni è: {category}."
                                
                            ingest_response = Agent().ask(prompt)
                            TTSManager().speak(ingest_response)
                        finally:
                            face.set_busy(False)
                    """
                    # Controllo Messaggi Chat da Web
                    if state.get("pending_chat_msg"):
                        chat_msg = state.get("pending_chat_msg")
                        logging.info(f"Ricevuto messaggio chat da Web: '{chat_msg}'")
                        
                        face.set_busy(True)
                        
                        try:
                            # Reset del messaggio pendente sul server
                            face.reset_pending_chat()
                            
                            # Elaborazione tramite LLM
                            response = ask_llm(chat_msg)
                            
                            # Salvataggio risposta per la Web UI e speak
                            face.send_chat_response(response)
                            TTSManager().speak(response)
                        finally:
                            face.set_busy(False)
            except Exception as e:
                # Silenzioso per non sporcare i log se il server è momentaneamente giù
                pass
