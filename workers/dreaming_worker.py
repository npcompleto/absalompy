import time
import logging
from face_client import FaceClient


class DreamingWorker:
    def __init__(self, face: FaceClient):
        self.face = face
    
    def run(self):
        """Processo di background che 'sogna' quando il robot dorme."""
        logging.info("Dreaming Worker avviato")
        while True:
            try:
                if not self.face.is_awake() and not self.face.is_loading():
                    logging.info("sto sognando")
            except Exception:
                pass
            time.sleep(120) # Aspetta 2 minuti (120 secondi)
