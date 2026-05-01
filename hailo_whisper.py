import os
import logging
import numpy as np
import sys

try:
    import hailo_platform
    from hailo_platform import VDevice, HEF
    # Tentiamo di usare l'API GenAI introdotta in HailoRT 5.0+ per una gestione più semplice di Whisper
    try:
        from hailo_platform.genai import Speech2Text, Speech2TextTask
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False
    
    HAILO_AVAILABLE = True
    logging.info(f"hailo_platform version {hailo_platform.__version__} detected.")
except ImportError:
    logging.error("hailo_platform not found. Ensure HailoRT is installed.")
    HAILO_AVAILABLE = False
    GENAI_AVAILABLE = False

class HailoWhisperModel:
    def __init__(self, model_size="base", hef_path=None):
        if not HAILO_AVAILABLE:
            raise ImportError("HailoRT components not found. Ensure hailo_platform is installed.")
        
        self.model_size = model_size
        # Percorso di default per il modello HEF (Hailo Executable Format)
        self.hef_path = hef_path or os.path.join("models", f"whisper_{model_size}.hef")
        
        if not os.path.exists(self.hef_path):
            logging.warning(f"HEF model not found at {self.hef_path}. Looking for fallback in hailo-apps...")
            # Se non troviamo il modello locale, proviamo a usare il wrapper di hailo-apps se il path è configurato
            try:
                sys.path.append('/home/devnull/hailo-apps/hailo-apps')
                from hailo_apps.python.standalone_apps.speech_recognition.speech_recognition import WhisperHailo
                self.model = WhisperHailo(model_size=model_size)
                self.mode = "hailo-apps"
                logging.info("Using WhisperHailo from hailo-apps.")
                return
            except ImportError:
                logging.error("Fallback hailo-apps not available.")
                raise FileNotFoundError(f"Model HEF not found at {self.hef_path}")

        logging.info(f"Initializing Hailo Whisper model using hailo_platform ({self.hef_path})...")
        
        self.vdevice = VDevice()
        
        if GENAI_AVAILABLE:
            self.model = Speech2Text(self.vdevice, self.hef_path)
            self.mode = "genai"
            logging.info("Using hailo_platform.genai for transcription.")
        else:
            # Fallback a implementazione manuale o hailo-apps se possibile
            logging.warning("hailo_platform.genai not available. Please ensure HailoRT 5.3+ is installed for best experience.")
            self.mode = "manual"
            # Qui si potrebbe implementare l'inferenza manuale usando InferModel, 
            # ma Whisper richiede una pipeline complessa (Encoder + Decoder).
            # Per ora lanciamo un errore se non abbiamo genai o hailo-apps.
            raise NotImplementedError("Manual Whisper implementation using raw hailo_platform is complex. Please use hailo-apps or upgrade to HailoRT 5.3+")

    def transcribe(self, audio, language="it", beam_size=5):
        """
        Mimics the faster-whisper transcribe interface.
        """
        if self.mode == "genai":
            # L'API GenAI di Hailo accetta audio 16kHz, mono, float32 [-1, 1]
            # stt_manager.py passa già l'audio in questo formato.
            text = self.model.generate_all_text(
                audio_data=audio,
                task=Speech2TextTask.TRANSCRIBE,
                language=language
            )
        elif self.mode == "hailo-apps":
            text = self.model.transcribe(audio, language=language)
        else:
            text = "[ERRORE: Modalità non supportata]"

        # Create a dummy segment object to match faster-whisper API expected by stt_manager.py
        class Segment:
            def __init__(self, text):
                self.text = text
        
        segments = [Segment(text)]
        info = None
        
        return segments, info
