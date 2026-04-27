import os
import time
from tts_manager import TTSManager
from agent import Agent
from face_client import FaceClient

class IngestWorker:
    def __init__(self, face: FaceClient):
        self.face = face
    
    def run(self):
        while True:
            # Check if there are at least a file in the raw folder
            raw_files = os.listdir("persona/knowledge/raw_documents")
            if len(raw_files) > 0:
                TTSManager().speak("Ho dei documenti da archiviare.")
                response = Agent().ask("Aggiorna knowledge raw_documents")
                TTSManager().speak(response)
            time.sleep(2) # Wait 1 second before checking again