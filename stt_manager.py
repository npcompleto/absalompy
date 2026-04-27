from faster_whisper import WhisperModel
from vosk import Model, KaldiRecognizer
import os
import config
import sounddevice
import json
import queue
import logging
import numpy as np

# Inizializza Whisper (usiamo tiny per velocità, soprattutto su Raspberry Pi)



def download_model():
    os.makedirs(os.path.dirname(config.VOSK_MODEL_PATH), exist_ok=True)
    logging.info(f"Modello non trovato. Download in corso da {config.VOSK_MODEL_URL}")
    zip_path = config.VOSK_MODEL_NAME + ".zip"
    urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path)
    logging.info("Download completato. Estrazione...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("models")
    
    os.remove(zip_path)
    logging.info("Modello pronto.\n")

class STTManager:
    def __init__(self):
        try:
            logging.info("Caricamento modello Whisper (large-v3)...")
            self.whisper_model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            if not os.path.exists(config.VOSK_MODEL_PATH):
                download_model()
            # Initialize model
            model = Model(config.VOSK_MODEL_PATH)
            grammar = json.dumps(config.WAKE_WORDS + ["[unk]"])
            # Avviamo con un recognizer LIMITATO alle sole wakewords + [unk] per efficienza
            self.vosk_recognizer = KaldiRecognizer(model, config.VOSK_RATE, grammar)
            self.stream = sounddevice.RawInputStream(samplerate=config.SAMPLE_RATE, blocksize=16000, dtype='int16',
                                channels=1, callback=self.callback, device=config.AUDIO_DEVICE_INDEX)
            self.stream.start()
            self.q = queue.Queue()
            logging.info(f"Listening for wakeword: {config.WAKE_WORDS}")
        except Exception as e:
            logging.error(f"Errore in STTManager: {e}")
        
        
    def callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            logging.debug(f"DEBUG: Audio status: {status}")
        self.q.put(bytes(indata))
            
    def listen_for_wakeword(self):
        try:
            logging.debug(f"DEBUG: Listening for wakeword")
            data = self.q.get(timeout=5) # Timeout per permettere il controllo dell'inattività
            logging.debug(f"DEBUG: Audio data received: {len(data)} bytes")
            # Se la frequenza hardware è diversa da quella di Vosk (16000), ricampioniamo nel thread principale
            if config.SAMPLE_RATE != config.VOSK_RATE:
                audio_data = np.frombuffer(data, dtype=np.int16)
                num_samples = len(audio_data)
                new_num_samples = int(num_samples * config.VOSK_RATE / config.SAMPLE_RATE)
                resampled_audio = np.interp(
                    np.linspace(0, num_samples, new_num_samples, endpoint=False),
                    np.arange(num_samples),
                    audio_data
                ).astype(np.int16)
                data = resampled_audio.tobytes()
                
        except queue.Empty:
            return False

        if self.vosk_recognizer.AcceptWaveform(data):
            result = json.loads(self.vosk_recognizer.Result())
            text = result.get("text", "").lower().strip()
            
            # Se non abbiamo sentito nulla, ignoriamo
            if not text:
                return False
                
            # Cerchiamo se una delle wakeword è stata rilevata da Vosk
            trigger_word = next((w for w in config.WAKE_WORDS if w in text), None)
            
            if trigger_word:
                print(f"\n[!] Wakeword '{trigger_word}' rilevata tramite Vosk!")
                # Svuotiamo la coda per ignorare l'audio precedente (inclusa la wakeword e il bip)
                while not self.q.empty():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        break
                return True
            else:
                print(f"DEBUG: Vosk ha trascritto -> '{text}'")
                # Svuotiamo la coda per ignorare l'audio precedente (inclusa la wakeword e il bip)
                while not self.q.empty():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        break
                return False
            
                
                
                
                
                
                """        
                print(">>> In ascolto per 5 secondi con Whisper...")
                face.set_loading(True)
                
                whisper_buffer = []
                start_time = time.time()
                
                # Ascolto per 5 secondi esatti
                while time.time() - start_time < 5:
                    try:
                        # Timeout breve per controllare il ciclo del tempo
                        d = q.get(timeout=0.5)
                        if config.SAMPLE_RATE != config.VOSK_RATE:
                            audio_data = np.frombuffer(d, dtype=np.int16)
                            num_samples = len(audio_data)
                            new_num_samples = int(num_samples * config.VOSK_RATE / config.SAMPLE_RATE)
                            resampled_audio = np.interp(
                                np.linspace(0, num_samples, new_num_samples, endpoint=False),
                                np.arange(num_samples),
                                audio_data
                            ).astype(np.int16)
                            whisper_buffer.append(resampled_audio)
                        else:
                            whisper_buffer.append(np.frombuffer(d, dtype=np.int16))
                    except queue.Empty:
                        continue
                
                if not whisper_buffer:
                    face.set_loading(False)
                    continue
                play_audio("sounds/bubblepop.mp3")    
                # Uniamo il buffer e convertiamo in float32 per Whisper
                full_audio = np.concatenate(whisper_buffer).astype(np.float32) / 32768.0
                
                # Trascrizione con Whisper
                print("--- Trascrizione in corso... ---")
                segments, info = whisper_model.transcribe(full_audio, language="it", beam_size=5)
                text = " ".join([s.text for s in segments]).strip().lower()
                
                face.set_loading(False)
                
                if not text:
                    print("DEBUG: Whisper non ha rilevato testo.")
                    continue
                    
                print(f"DEBUG: Whisper ha trascritto -> '{text}'")
                
                last_interaction_time = time.time()
                
                # Pulisce il testo dalle wakeword se presenti
                command = text
                for w in WAKE_WORDS:
                    command = command.replace(w, "")
                command = re.sub(r'^[,.!?;:\s]+|[,.!?;:\s]+$', '', command).strip()
                
                if not command:
                    print("DEBUG: Nessun comando dopo la wakeword.")
                    continue
                    
                # Procediamo con l'elaborazione del comando
                face.set_busy(True)
                try:
                    response = ask_llm(command)
                    face.send_chat_response(response)
                    speak(response)
                finally:
                    face.set_busy(False)
                    # Resetta il recognizer per il prossimo ciclo
                    rec.Reset()
                    
                # Gestione speciale per comando di addormentamento se vogliamo forzarlo via codice
                if "addormentati" in command:
                    face.set_mode("asleep")
                    is_awake = False
                
                # Svuota la coda per evitare loop di feedback o audio accumulato
                while not q.empty():
                    try: q.get_nowait()
                    except queue.Empty: break
                face.set_busy(False)
                
            else:
                # Se siamo addormentati e non sentiamo la wakeword, ignoriamo il testo
                print(f"DEBUG: Testo ignorato (nessuna wakeword): '{text}'")
                pass
                """