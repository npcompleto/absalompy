from datetime import datetime
from langchain_core.tools import tool

@tool
def get_current_time():
    """Restituisce l'orario corrente.

    Usa questo tool SOLO quando:
    - l'utente chiede l'ora attuale
    - l'utente chiede informazioni temporali in tempo reale

    NON usarlo per:
    - orari storici
    - esempi generici

    Output: stringa nel formato HH:MM:SS
    """
    print("Sto controllando l'ora...")
    current_time = datetime.now().strftime("%H:%M")
    print(f"L'ora attuale è: {current_time}")
    return f"L'ora attuale è: {current_time}"
