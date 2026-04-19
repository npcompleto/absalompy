from langchain_core.tools import tool
import sqlite3
from datetime import datetime
from db import get_connection
from playwright.sync_api import sync_playwright, expect
import os
import re
from dotenv import load_dotenv

load_dotenv()

def add_school_event(event_type: str, date: str, school_class: str, description: str):
    """Aggiunge un nuovo compito o una verifica al database.
    
    Parametri:
    - event_type: 'compito' (homework) o 'verifica' (test/exam).
    - date: la data dell'evento (es. '19/04/2026').
    - school_class: la materia o la classe (es. 'Matematica', '3B').
    - description: descrizione del compito o della verifica.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if description and not description.strip().endswith('.'):
            description = description.strip() + "."
            
        cursor.execute('''
            INSERT OR IGNORE INTO school_events (type, date, class, description)
            VALUES (?, ?, ?, ?)
        ''', (event_type.lower(), date, school_class, description))
        conn.commit()
        conn.close()
        return f"Ho segnato il {event_type}: {description} per {school_class} il {date}."
    except Exception as e:
        return f"Errore durante l'inserimento: {e}"

def extract_week_data(page):
    page.wait_for_selector("#table-rcla", timeout=30000)
    table = page.locator("#table-rcla")
    # Iterazione sulle righe della tabella
    trs = table.locator("tr")
    rows_count = trs.count()
    print(f"Righe totali nella tabella: {rows_count}")
            
    for i in range(rows_count):
        row = trs.nth(i)
        cells = row.locator("td")
                
        # Verifichiamo che ci siano abbastanza celle (almeno 3)
        if cells.count() >= 3:
            data_val = cells.nth(0).inner_text().strip().replace("\n", "")
            data_val = re.sub(r"lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica", "", data_val)
            compiti_val = cells.nth(2).inner_text().strip()
            verifiche_val = cells.nth(3).inner_text().strip()
            if compiti_val:
                compiti = compiti_val.split("\n")
                #print(compiti)
                for compito in compiti:
                    row_data = compito.split(":")
                    #print(row_data)
                    if len(row_data) >= 2:
                        materia = row_data[0].strip()
                        compito = ":".join(row_data[1:]).strip()
                        if compito and not compito.endswith('.'):
                            compito += '.'
                        print("compito", data_val, materia, compito)
                        add_school_event("compito", data_val, materia, compito)
                        
            if verifiche_val:
                verifiche = verifiche_val.split("\n")
                #print(verifiche)
                for verifica in verifiche:
                    row_data = verifica.split(":")
                    #print(row_data)
                    if len(row_data) >= 2:
                        materia = row_data[0].strip()
                        verifica = ":".join(row_data[1:]).strip()
                        if verifica and not verifica.endswith('.'):
                            verifica += '.'
                        print("verifica", data_val, materia, verifica)
                        add_school_event("verifica", data_val, materia, verifica)

def axios_sync(weeks_ahead: int = 3):
    """ aggiorna i compiti e le verifiche dal registro Axios per il numero di settimane specificato , se non viene specificato il numero di settimane viene aggiornato per 3 settimane in avanti"""
    customer_id = os.getenv("AXIOS_CUSTOMER_ID")
    username = os.getenv("AXIOS_USERNAME")
    password = os.getenv("AXIOS_PASSWORD")

    if not all([customer_id, username, password]):
        return "Errore: Credenziali Axios non configurate correttamente nel file .env (AXIOS_CUSTOMER_ID, AXIOS_USERNAME, AXIOS_PASSWORD)."

    url = "https://registrofamiglie.axioscloud.it/Pages/SD/SD_Login.aspx"
    
    try:
        with sync_playwright() as p:
            # Avvio browser - Headless True per l'esecuzione in background
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            print(f"Navigazione su {url}...")
            page.goto(url)
            
            # Inserimento credenziali basato sui nomi degli input forniti
            print("Inserimento credenziali...")
            page.fill('input[name="customerid"]', customer_id)
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            
            # Click sul pulsante di login
            # L'utente specifica un pulsante di tipo submit con testo "Accedi con Axios "
            print("Esecuzione login...")
            # Usiamo un selettore che cerchi l'attribulo value o il testo
            login_button = page.locator('input[type="submit"], button[type="submit"]').filter(has_text="Accedi con Axios")
            if login_button.count() == 0:
                # Tentativo alternativo basato sul valore dell'input
                login_button = page.locator('input[value="Accedi con Axios "]')
            
            login_button.click()
            
            # Attesa del caricamento della timeline
            print("Accesso in corso... attesa del contenuto timeline...")
            page.wait_for_selector("#content-timeline", timeout=30000)
            
            print("Login completato con successo.")

            registro_di_classe = page.locator('h4').filter(has_text="Registro di Classe")
            registro_di_classe.click()
            
            extract_week_data(page)
            if weeks_ahead >= 1:
                for i in range(weeks_ahead):
                    prev_fdDataValue = page.locator("#fdData").input_value()
                    settimana_successiva = page.locator('button[title="Settimana successiva"]')
                    settimana_successiva.click()
                    page.wait_for_timeout(1000)
                    #get input element value with id fdData
                    fdData = page.locator("#fdData")
                    expect(fdData).not_to_have_value(prev_fdDataValue)
                    extract_week_data(page)
                                
            
                
            browser.close()
            return f"Sincronizzazione completata."
            
    except Exception as e:
        return f"Si è verificato un errore durante la sincronizzazione con Axios: {str(e)}"

@tool
def list_school_events(start_date: str = None, end_date: str = None):
    """Elenca i compiti e le verifiche salvate. 
    
    È possibile filtrare per un intervallo di date fornendo start_date e end_date.
    Se viene fornita solo start_date, filtra per quella singola data.
    Se non viene fornita alcuna data, elenca tutti gli eventi.
    
    Parametri:
    - start_date: opzionale, data di inizio o data singola (es. '19/04/2026').
    - end_date: opzionale, data di fine intervallo (es. '25/04/2026').
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Recuperiamo la data massima presente a DB per decidere se sincronizzare
        cursor.execute('SELECT DISTINCT date FROM school_events')
        all_dates = cursor.fetchall()
        
        max_date_db = None
        if all_dates:
            parsed_dates = []
            for d_row in all_dates:
                try:
                    parsed_dates.append(datetime.strptime(d_row[0], "%d/%m/%Y"))
                except: continue
            if parsed_dates:
                max_date_db = max(parsed_dates)
        
        # Decidiamo se serve sincronizzare
        target_date_str = end_date or start_date
        should_sync = False
        
        if not max_date_db:
            should_sync = True # Database vuoto
        elif target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%d/%m/%Y")
                if target_date > max_date_db:
                    should_sync = True
            except:
                pass # Formato non valido, ignoriamo sync
        
        if should_sync:
            print(f"Sincronizzazione necessaria (Target: {target_date_str}, Max DB: {max_date_db.strftime('%d/%m/%Y') if max_date_db else 'Nessuna'})...")
            axios_sync()
        
        # Rieseguiamo la query per includere i nuovi dati
        cursor.execute('SELECT type, date, class, description FROM school_events ORDER BY date ASC')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "Non ho trovato nulla in agenda."

        # Filtraggio in Python (per sicurezza con il formato DD/MM/YYYY)
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%d/%m/%Y")
                if end_date:
                    end_dt = datetime.strptime(end_date, "%d/%m/%Y")
                    rows = [r for r in rows if start_dt <= datetime.strptime(r[1], "%d/%m/%Y") <= end_dt]
                else:
                    rows = [r for r in rows if r[1] == start_date]
            except ValueError as e:
                return f"Formato data non valido. Usa DD/MM/YYYY. Errore: {e}"
        
        if not rows:
            return "Non ho trovato nulla in agenda per il periodo selezionato."
        
        # Ordinamento cronologico reale
        rows.sort(key=lambda x: datetime.strptime(x[1], "%d/%m/%Y"))
        
        results = []
        for row in rows:
            results.append(f"[{row[0].upper()}] {row[2]} ({row[1]}): {row[3]}")
        
        return "\n".join(results)
    except Exception as e:
        return f"Errore durante la lettura: {e}"
