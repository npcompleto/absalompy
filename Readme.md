# Absalom OS 🎙️

Un piccolo assistente vocale basato su Python e Vosk.

## Configurazione

### 1. Dipendenze di Sistema
Su Linux, è necessario installare `libportaudio2` per gestire l'input audio:
```bash
sudo apt-get install libportaudio2
```

### 2. Installazione con Virtual Environment (Consigliato)
Crea e attiva un ambiente virtuale, quindi installa le dipendenze:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Avvio Rapido
Puoi avviare l'assistente usando lo script di avvio:
```bash
./start.sh
```

Oppure manualmente attivando il venv:
```bash
source venv/bin/activate
python absalom.py
```

## Caratteristiche
- **Offline**: Funziona senza connessione internet grazie a Vosk.
- **Auto-setup**: Scarica automaticamente il modello vocale italiano al primo avvio.
- **Wake Word**: Risponde al comando "Absalom".

## Note
Al primo avvio, il programma scaricherà circa 50MB di dati per il modello linguistico. Assicurati che il tuo microfono sia configurato correttamente come dispositivo di input predefinito.
