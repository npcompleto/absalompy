#!/bin/bash

# Vai nella directory dello script
cd "$(dirname "$0")"

# Attiva l'ambiente virtuale
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Errore: Ambiente virtuale 'venv' non trovato."
    echo "Per favore crea il venv prima con: python3 -m venv venv"
    exit 1
fi

# Avvia l'assistente
python absalom.py
