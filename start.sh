#!/bin/bash

# Vai nella directory dello script
cd "$(dirname "$0")"

# Crea l'ambiente virtuale se non esiste
if [ ! -d "venv" ]; then
    echo "--- Creazione ambiente virtuale... ---"
    python3 -m venv venv
fi

# Attiva l'ambiente virtuale
source venv/bin/activate

# Installa/Aggiorna le dipendenze
echo "--- Verifica dipendenze... ---"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt


# Analisi parametri
DEBUG_MODE=false
USE_HAILO=false
for arg in "$@"; do
    if [ "$arg" == "debug" ]; then
        DEBUG_MODE=true
    elif [ "$arg" == "hailo" ]; then
        USE_HAILO=true
    fi
done

HAILO_FLAG=""
if [ "$USE_HAILO" = true ]; then
    HAILO_FLAG="--hailo"
fi

# Funzione per pulire i processi all'uscita (CTRL+C)
cleanup() {
    echo -e "\n--- Spegnimento Absalom OS in corso... ---"
    kill $FACE_PID $ABSALOM_PID 2>/dev/null
    wait $FACE_PID $ABSALOM_PID 2>/dev/null
    echo "--- Sistemi spenti. ---"
    exit
}

# Cattura il segnale CTRL+C (SIGINT)
trap cleanup SIGINT

echo "--- Avvio Robot Face Server... ---"
python face_server.py > /dev/null 2>&1 &
FACE_PID=$!

export DISPLAY=:0

echo "--- Avvio Absalom Assistant... ---"
python absalom.py $HAILO_FLAG "$@"
ABSALOM_PID=$!
echo "--- Absalom OS è attivo. Premi CTRL+C per terminare. ---"
# Attende la fine dei processi
wait $ABSALOM_PID
wait $FACE_PID
