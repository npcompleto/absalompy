import requests
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

def set_mode(mode):
    print(f"Impostando modalità a: {mode}")
    try:
        r = requests.post(f"{BASE_URL}/control", json={"mode": mode})
        return r.json()
    except Exception as e:
        print(f"Errore: {e}")

def blink():
    print("Inviando comando blink manuale...")
    requests.post(f"{BASE_URL}/blink")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "awake":
            set_mode("awake")
        elif cmd == "asleep":
            set_mode("asleep")
        elif cmd == "blink":
            blink()
        else:
            print("Comando non riconosciuto. Usa: awake, asleep, blink")
    else:
        print("Test API Robot Face")
        print("1. Sveglia il robot")
        set_mode("awake")
        time.sleep(2)
        
        print("2. Forza un blink")
        blink()
        time.sleep(5) # Osserva il blink automatico nel frattempo
        
        print("3. Metti a dormire")
        set_mode("asleep")
        time.sleep(3)
        
        print("4. Riattiva")
        set_mode("awake")
