from flask import Flask, render_template, jsonify, request
import time
import threading
import random
import os
import subprocess

app = Flask(__name__)

# Global state
face_state = {
    "eyes": "open",
    "mode": "asleep",  # "awake" o "asleep"
    "busy": False,
    "speaking": False,
    "loading": False,
    "angry": False,
    "sad": False,
    "last_update": time.time()
}

def auto_blink_loop():
    """Loop di background per lo sbattimento automatico delle ciglia quando sveglio."""
    while True:
        if face_state["mode"] == "awake":
            # Attende un intervallo casuale tra 3 e 8 secondi
            time.sleep(random.uniform(3.0, 8.0))
            if face_state["mode"] == "awake":
                face_state['eyes'] = 'closed'
                # Durata del blink
                time.sleep(0.15)
                # Riaccende solo se siamo ancora in modalità awake
                if face_state["mode"] == "awake":
                    face_state['eyes'] = 'open'
        else:
            # Se sta dormendo, assicuriamoci che gli occhi restino chiusi
            if face_state['eyes'] != 'closed':
                face_state['eyes'] = 'closed'
            time.sleep(1)

# Avvio del thread di background
threading.Thread(target=auto_blink_loop, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def get_status():
    return jsonify(face_state)

@app.route('/control', methods=['POST'])
def control():
    """API per controllare occhi e modalità."""
    data = request.get_json()
    updated = False
    
    if 'eyes' in data:
        face_state['eyes'] = data['eyes']
        updated = True
        
    if 'mode' in data:
        new_mode = data['mode']
        if new_mode in ["awake", "asleep"]:
            face_state['mode'] = new_mode
            if new_mode == "asleep":
                face_state['eyes'] = "closed"
            else:
                face_state['eyes'] = "open"
            updated = True

    if 'busy' in data:
        face_state['busy'] = bool(data['busy'])
        updated = True

    if 'speaking' in data:
        face_state['speaking'] = bool(data['speaking'])
        updated = True

    if 'loading' in data:
        face_state['loading'] = bool(data['loading'])
        updated = True

    if 'angry' in data:
        face_state['angry'] = bool(data['angry'])
        updated = True

    if 'sad' in data:
        face_state['sad'] = bool(data['sad'])
        updated = True
            
    if updated:
        face_state['last_update'] = time.time()
        return jsonify({"status": "success", "state": face_state})
        
    return jsonify({"status": "error", "message": "Invalid parameters"}), 400

@app.route('/stop_audio', methods=['POST'])
def stop_audio():
    """Interrompe la riproduzione audio uccidendo il processo ffplay."""
    try:
        # pkill restituisce 0 se ha trovato processi da uccidere, 1 altrimenti.
        # Entrambi sono accettabili per noi.
        subprocess.run(["pkill", "ffplay"], stderr=subprocess.DEVNULL)
        return jsonify({"status": "success", "message": "Audio stop signal sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/blink', methods=['POST'])
def blink():
    """Forza uno sbattimento di ciglia manuale (solo se sveglio)."""
    if face_state['mode'] == 'asleep':
        return jsonify({"status": "ignored", "reason": "sleeping"}), 200
        
    def execute_blink():
        face_state['eyes'] = 'closed'
        time.sleep(0.2)
        face_state['eyes'] = 'open'
    
    threading.Thread(target=execute_blink).start()
    return jsonify({"status": "blinking"})

if __name__ == '__main__':
    print("Robot Face API starting at http://127.0.0.1:5000")
    # Disabilito debug=True perché causa il riavvio del thread di background (doppia istanza)
    app.run(host='0.0.0.0', port=5000, debug=False)
