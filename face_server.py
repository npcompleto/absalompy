from flask import Flask, render_template, jsonify, request
import time
import threading
import random
import os
import subprocess
import glob
import platform
from dotenv import set_key, find_dotenv

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
    "last_interaction": {
        "user": "",
        "bot": ""
    },
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

@app.route('/admin')
def admin():
    return render_template('admin.html')

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

    if 'last_interaction' in data:
        face_state['last_interaction'] = data['last_interaction']
        updated = True
            
    if updated:
        face_state['last_update'] = time.time()
        return jsonify({"status": "success", "state": face_state})
        
    return jsonify({"status": "error", "message": "Invalid parameters"}), 400

# --- Admin API for Persona & Memory ---

@app.route('/api/identity', methods=['GET', 'POST'])
def handle_identity():
    id_path = os.path.join("persona", "Identity.md")
    if request.method == 'POST':
        data = request.get_json()
        if 'content' in data:
            with open(id_path, "w", encoding="utf-8") as f:
                f.write(data['content'])
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "No content provided"}), 400
    
    if os.path.exists(id_path):
        with open(id_path, "r", encoding="utf-8") as f:
            return jsonify({"content": f.read()})
    return jsonify({"content": ""})

@app.route('/api/memory', methods=['GET'])
def list_memory_files():
    memory_dir = os.path.join("persona", "memory")
    if not os.path.exists(memory_dir):
        return jsonify({"dates": []})
    
    files = glob.glob(os.path.join(memory_dir, "*.txt"))
    dates = [os.path.basename(f).replace(".txt", "") for f in files]
    return jsonify({"dates": sorted(dates, reverse=True)})

@app.route('/api/memory/<date>', methods=['GET', 'POST'])
def handle_memory(date):
    mem_path = os.path.join("persona", "memory", f"{date}.txt")
    if request.method == 'POST':
        data = request.get_json()
        if 'content' in data:
            os.makedirs(os.path.dirname(mem_path), exist_ok=True)
            with open(mem_path, "w", encoding="utf-8") as f:
                f.write(data['content'])
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "No content provided"}), 400
    
    if os.path.exists(mem_path):
        with open(mem_path, "r", encoding="utf-8") as f:
            return jsonify({"content": f.read()})
    return jsonify({"error": "File not found"}), 404

@app.route('/api/env', methods=['POST'])
def update_env():
    """Sovrascrive una variabile d'ambiente nel file .env senza mostrarne il contenuto esistente."""
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    
    if not key or value is None:
        return jsonify({"status": "error", "message": "Chiave e valore richiesti"}), 400
    
    try:
        env_file = find_dotenv()
        if not env_file:
            env_file = os.path.join(os.getcwd(), ".env")
            # Crea il file se non esiste
            if not os.path.exists(env_file):
                with open(env_file, "w") as f: f.write("")
        
        set_key(env_file, key.upper(), value)
        return jsonify({"status": "success", "message": f"Variabile {key} aggiornata"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_audio', methods=['POST'])
def stop_audio():
    """Interrompe la riproduzione audio uccidendo il processo ffplay."""
    try:
        if platform.system() == "Windows":
            # Su Windows usiamo taskkill. /F forza la chiusura, /IM specifica il nome immagine, /T chiude i processi figli
            subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe", "/T"], 
                           stderr=subprocess.DEVNULL, 
                           stdout=subprocess.DEVNULL)
        else:
            # Su Linux/Unix usiamo pkill
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
