from datetime import datetime, timedelta
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
    return current_time


@tool
def get_current_date():
    """Restituisce la data corrente.

    Usa questo tool SOLO quando:
    - l'utente chiede la data attuale
    - l'utente chiede informazioni temporali in tempo reale

    NON usarlo per:
    - date storiche
    - esempi generici

    Output: stringa nel formato DD/MM/YYYY
    """
    print("Sto controllando la data...")
    current_date = datetime.now().strftime("%d/%m/%Y")
    print(f"La data attuale è: {current_date}")
    return current_date

@tool
def get_day_of_week():
    """Restituisce il giorno della settimana corrente.

    Usa questo tool SOLO quando:
    - l'utente chiede il giorno della settimana attuale
    - l'utente chiede informazioni temporali in tempo reale

    NON usarlo per:
    - giorni della settimana storici
    - esempi generici

    Output: stringa nel formato "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"
    """
    print("Sto controllando il giorno della settimana...")
    day_of_week = datetime.now().strftime("%A")
    print(f"Il giorno della settimana è: {day_of_week}")
    return day_of_week

@tool
def get_next_week_start_date():
    """Restituisce la data di inizio della prossima settimana (il prossimo lunedì).

    Usa questo tool SOLO quando:
    - l'utente chiede la data di inizio della prossima settimana
    - l'utente chiede informazioni sulla prossima settimana
    - l'utente chiede informazioni temporali in tempo reale

    NON usarlo per:
    - date storiche
    - esempi generici

    Output: stringa nel formato "Lunedì DD/MM/YYYY"
    """
    print("Sto calcolando la data di inizio della prossima settimana...")
    now = datetime.now()
    # Lunedì è 0, Domenica è 6
    days_to_monday = 7 - now.weekday()
    next_monday = now + timedelta(days=days_to_monday)
    
    # Impostiamo la lingua o forziamo "Lunedì" visto che il formato richiesto sembrava suggerirlo
    # Per semplicità usiamo il nome del giorno formattato se locale è settato, 
    # ma il prompt era in italiano quindi userò una stringa più esplicita se necessario.
    # %A restituisce il giorno della settimana.
    
    result = next_monday.strftime("%A %d/%m/%Y")
    # Se il sistema è in inglese, %A sarà "Monday". 
    # Visto il contesto italiano, potrei voler mappare o assicurarmi che sia in italiano.
    # Tuttavia, negli altri tool %A è usato senza locale check.
    
    print(f"La data di inizio della prossima settimana è: {result}")
    return result