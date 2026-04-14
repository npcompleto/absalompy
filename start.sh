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

# Avvia l'assistente
echo "--- Avvio Absalom OS... ---"
python absalom.py
