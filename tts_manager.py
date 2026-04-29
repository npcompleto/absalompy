import os
import re
import wave
import urllib.request
import logging
from piper.voice import PiperVoice
import config
from utils import play_audio

class TTSManager:
    _instance = None  # Memorizza l'unica istanza della classe

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logging.info("Creazione istanza Singleton di TTSManager")
            cls._instance = super(TTSManager, cls).__new__(cls)
            # Inizializziamo gli attributi solo la prima volta
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, face=None):
        # Evitiamo di sovrascrivere l'inizializzazione se l'istanza esiste già
        if self._initialized:
            return
            
        self._piper_voice = self.get_piper_voice()
        self.face = face
        self._initialized = True
        self.recurrent_audio = {
            "dimmi": "sounds/dimmi.wav",
            "certo": "sounds/certo.wav",
            "un momento": "sounds/unmomento.wav",
            "ecco": "sounds/ecco.wav"
        }

        #persist recurrent audio files
        for text, filename in self.recurrent_audio.items():
            self.speak(text, filename, play=False)

    def get_piper_voice(self):
        if not os.path.exists(config.PIPER_MODEL_PATH) or not os.path.exists(config.PIPER_CONFIG_PATH):
            logging.info("Download modello Piper in corso...")
            os.makedirs(os.path.dirname(config.PIPER_MODEL_PATH), exist_ok=True)
            urllib.request.urlretrieve(config.PIPER_MODEL_URL, config.PIPER_MODEL_PATH)
            urllib.request.urlretrieve(config.PIPER_CONFIG_URL, config.PIPER_CONFIG_PATH)
            logging.info("Modello Piper pronto.")
        
        # Caricamento del modello
        return PiperVoice.load(config.PIPER_MODEL_PATH, config_path=config.PIPER_CONFIG_PATH)

    def speak(self, text, filename="speech_chunk.wav", play=True):
        if not isinstance(text, str):
            text = str(text)
        
        # Pulizia testo
        text = re.sub(r'[^\w\s\d.,!?;:()\'\"-/]', '', text)
        text = text.replace("**", "")
        sentences = [s.strip() for s in re.split(r'(?<=[!.;?])\s+', text) if s.strip()]
        
        if not sentences:
            return

        logging.info(f"Absalom dice: '{text}' (in {len(sentences)} pezzi)")
        
        
        if self.face:
            self.face.set_speaking(True)
        
        try:
            for i, sentence in enumerate(sentences):
                logging.info(f"Sintesi pezzo {i+1}/{len(sentences)}: '{sentence}'")
                with wave.open(filename, "wb") as wav_file:
                    # self._piper_voice.synthesize restituisce un generatore di chunk audio
                    for j, audio_chunk in enumerate(self._piper_voice.synthesize(sentence)):
                        if j == 0:
                            wav_file.setnchannels(audio_chunk.sample_channels)
                            wav_file.setsampwidth(audio_chunk.sample_width)
                            wav_file.setframerate(audio_chunk.sample_rate)

                        wav_file.writeframes(audio_chunk.audio_int16_bytes)
                
                # Riproduce il pezzo (presume che play_audio sia definita globalmente)
                if play:
                    return_code = play_audio(filename) 
                    if return_code != 0:
                        logging.info(f"Riproduzione interrotta (RC: {return_code})")
                        break
                    
        except Exception as e:
            logging.error(f"Errore durante la sintesi vocale: {e}")
        finally:
            if self.face:
                self.face.set_speaking(False)