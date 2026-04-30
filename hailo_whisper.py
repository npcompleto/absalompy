import os
import logging
import numpy as np

try:
    from hailo_apps.python.standalone_apps.speech_recognition.speech_recognition import WhisperHailo
    HAILO_AVAILABLE = True
except ImportError:
    try:
        # Alternative import if they used a different structure
        from whisper_hailo import WhisperHailo
        HAILO_AVAILABLE = True
    except ImportError:
        HAILO_AVAILABLE = False

class HailoWhisperModel:
    def __init__(self, model_size="base", device="hailo", compute_type="float16"):
        if not HAILO_AVAILABLE:
            raise ImportError("Hailo Whisper components not found. Ensure hailo-apps or whisper_hailo is installed and correctly configured.")
        
        logging.info(f"Initializing Hailo Whisper model ({model_size})...")
        # Note: The exact initialization depends on the library used.
        # This is a generic wrapper based on common Hailo-Whisper implementations.
        self.model = WhisperHailo(model_size=model_size)
        
    def transcribe(self, audio, language="it", beam_size=5):
        """
        Mimics the faster-whisper transcribe interface.
        """
        # Hailo-Whisper usually returns text directly or segments.
        # We wrap it to match WhisperModel.transcribe output.
        text = self.model.transcribe(audio, language=language)
        
        # Create a dummy segment object to match faster-whisper API
        class Segment:
            def __init__(self, text):
                self.text = text
        
        segments = [Segment(text)]
        info = None # We don't strictly need the info object for now
        
        return segments, info
