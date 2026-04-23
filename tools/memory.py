from langchain_core.tools import tool
from datetime import datetime

@tool
def remember(content: str):
    """Ricorda un'informazione per il futuro.

    Usa questo tool quando l'utente chiede di ricordare un'informazione.
    
    Esempio: Ricordati che mi chiamo Barbara, Ricordati che vivo a Milano, Ricordati che mi piace la pizza.
    
    Output: Messaggio di conferma.
    """
    #append contet to persona/long_term_memory.txt
    with open("persona/memory/long_term_memory.txt", "a", encoding="utf-8") as f:
        f.write(content + "\n")
    return "Informazione memorizzata con successo."
    