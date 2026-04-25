import os
import subprocess
import logging

def play_audio(filepath):
    """Riproduce un file audio specificato. Ritorna il codice di uscita del processo."""
    if os.path.exists(filepath):
        try:
            process = subprocess.run(["ffplay", "-nodisp", "-autoexit", filepath], 
                           stderr=subprocess.DEVNULL, 
                           stdout=subprocess.DEVNULL)
            return process.returncode
        except Exception as e:
            logging.error(f"Errore durante la riproduzione di {filepath}: {e}")
            return -1
    else:
        logging.error(f"File audio non trovato: {filepath}")
        return -1
