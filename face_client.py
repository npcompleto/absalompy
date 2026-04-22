import requests
import threading

busy_lock = threading.Lock()

class FaceClient:
    """Client per la comunicazione con il server della faccia del robot (face_server.py)."""
    
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url

    def _post_control(self, data):
        """Metodo helper per inviare comandi al server."""
        try:
            r = requests.post(f"{self.base_url}/control", json=data, timeout=2)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"FaceClient Error (control): {e}")
        return None

    def blink(self):
        """Invia un comando di sbattimento ciglia."""
        try:
            requests.post(f"{self.base_url}/blink", timeout=2)
        except Exception as e:
            print(f"FaceClient Error (blink): {e}")

    def set_mode(self, mode):
        """Imposta la modalità (awake/asleep)."""
        return self._post_control({"mode": mode})

    def set_busy(self, status):
        
        with busy_lock:
            """Imposta lo stato di occupato."""
            self._post_control({"busy": bool(status)})

    def set_speaking(self, status):
        """Imposta lo stato di sintesi vocale in corso."""
        self._post_control({"speaking": bool(status)})

    def set_loading(self, status):
        """Imposta lo stato di caricamento/elaborazione."""
        self._post_control({"loading": bool(status)})

    def set_angry(self, status):
        """Imposta lo stato arrabbiato."""
        self._post_control({"angry": bool(status)})

    def set_sad(self, status):
        """Imposta lo stato triste."""
        self._post_control({"sad": bool(status)})

    def set_last_interaction(self, user_text, bot_text):
        """Invia l'ultima interazione tra utente e bot per la visualizzazione nella UI."""
        self._post_control({
            "last_interaction": {
                "user": user_text,
                "bot": bot_text
            }
        })

    def reset_ingest_trigger(self):
        """Resetta il flag di richiesta ingestione sul server."""
        self._post_control({"ingest_requested": False})

    def reset_pending_chat(self):
        """Resetta il messaggio chat pendente sul server."""
        self._post_control({"pending_chat_msg": None})

    def send_chat_response(self, response):
        """Invia la risposta della chat al server per la visualizzazione nella UI."""
        self._post_control({"chat_response": response})

    def get_full_status(self):
        """Recupera l'intero stato dal server."""
        try:
            r = requests.get(f"{self.base_url}/status", timeout=2)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"FaceClient Error (get_status): {e}")
        return None

    def get_robot_status(self):
        """Recupera lo stato semplificato (awake e busy)."""
        state = self.get_full_status()
        if state:
            return {
                "is_awake": state.get("mode") == "awake",
                "is_busy": state.get("busy", False)
            }
        return None

    def is_speaking(self):
        state = self.get_full_status()
        if state:
            return state.get("speaking", False)
        return False
    
    def reset_face(self):
        self.set_sad(False)
        self.set_angry(False)
        self.set_loading(False)
        self.set_busy(False)
        self.set_speaking(False)
        self.set_mode("awake")
