import os
import time
from tts_manager import TTSManager
from agent import Agent
from face_client import FaceClient
import logging

class IngestWorker:
    def __init__(self, face: FaceClient):
        self.face = face
    
    def run(self):
        while True:
            # Check if there are at least a file in the raw folder
            try:
                raw_files = os.listdir("persona/knowledge/raw_documents")
            except Exception as e:
                logging.error(f"Errore durante la lettura della cartella raw_documents, la creo: {e}")
                #create folder
                os.makedirs("persona/knowledge/raw_documents", exist_ok=True)
                continue
            if len(raw_files) > 0:
                TTSManager().speak("Ho dei documenti da archiviare.")
                response = Agent().ask("Aggiorna knowledge raw_documents")
                TTSManager().speak(response)
            time.sleep(2) # Wait 1 second before checking again