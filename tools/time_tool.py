from datetime import datetime
from langchain_core.tools import tool

@tool
def get_current_time():
    """Restituisce l'ora attuale locale in formato HH:MM."""
    print("Sto controllando l'ora...")
    current_time = datetime.now().strftime("%H:%M")
    print(f"L'ora attuale è: {current_time}")
    return f"L'ora attuale è: {current_time}"
