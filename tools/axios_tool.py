from playwright.sync_api import sync_playwright
from langchain_core.tools import tool
import os
from dotenv import load_dotenv

load_dotenv()

#@tool
def axios_sync():
    """Effettua il login sul Registro Famiglie Axios per sincronizzare i dati e visualizzare la timeline."""
    customer_id = os.getenv("AXIOS_CUSTOMER_ID")
    username = os.getenv("AXIOS_USERNAME")
    password = os.getenv("AXIOS_PASSWORD")

    if not all([customer_id, username, password]):
        return "Errore: Credenziali Axios non configurate correttamente nel file .env (AXIOS_CUSTOMER_ID, AXIOS_USERNAME, AXIOS_PASSWORD)."

    url = "https://registrofamiglie.axioscloud.it/Pages/SD/SD_Login.aspx"
    
    try:
        with sync_playwright() as p:
            # Avvio browser - Headless True per l'esecuzione in background
            browser = p.chromium.launch(headless=False)
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
            
            page.wait_for_selector("#table-rcla", timeout=30000)
            table = page.locator("#table-rcla")
            # Iterazione sulle righe della tabella
            trs = table.locator("tr")
            rows_count = trs.count()
            print(f"Righe totali nella tabella: {rows_count}")
            
            extracted_data = []
            for i in range(rows_count):
                row = trs.nth(i)
                cells = row.locator("td")
                
                # Verifichiamo che ci siano abbastanza celle (almeno 3)
                if cells.count() >= 3:
                    data_val = cells.nth(0).inner_text().strip()
                    compiti_val = cells.nth(2).inner_text().strip()
                    
                    if data_val or compiti_val:
                        extracted_data.append(f"[{data_val}] {compiti_val}")
                        print(f"Riga {i}: Data={data_val}, Compiti={compiti_val}")
            
            summary = "\n".join(extracted_data)
            print("\n Riepilogo Compiti:\n" + summary)
                
            browser.close()
            return f"Sincronizzazione completata. Ecco i compiti trovati:\n{summary}"
            
    except Exception as e:
        return f"Si è verificato un errore durante la sincronizzazione con Axios: {str(e)}"

if __name__ == "__main__":
    print(axios_sync())