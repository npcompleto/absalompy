import os
import subprocess
import logging
from datetime import datetime

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

def write_today_memory(text):
    """Scrive un testo nella memoria odierna."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join("persona", "memory", f"{date_str}.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        logging.error(f"Errore durante il salvataggio della memoria: {e}")