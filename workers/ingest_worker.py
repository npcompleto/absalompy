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
            raw_files = os.listdir("persona/wiki/raw")
            if len(raw_files) > 0:
                TTSManager().speak("Ho ricevuto dei documenti da archiviare.")
                response = Agent().ask("Ingerisci i file presenti nella cartella raw nella Wiki e sintetizzali. La prima parte del nome del file rappresenta la categoria. Ad esempio geografia_ indica che il file ha categoria geografia.")
                TTSManager().speak(response)
            time.sleep(2) # Wait 1 second before checking again