from langchain_core.tools import tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain.agents import create_agent
from dotenv import load_dotenv
import config
import logging
from utils import write_today_memory
import os

load_dotenv()

LIBRARIAN_PROMPT = """
Sei l'archivista di Absalom. 
quando ti chiedo "aggiorna knowledge raw_documents" devi eseguire i seguenti passaggi in ordine:
1. Esegui 'list_directory' sulla cartella 'raw_documents'. Se è vuota, fermati e dillo.
2. Per ogni file trovato, DEVI:
    a. Leggere il contenuto con 'read_file'.
    b. Estrarre dal nome file la categoria, il nome del libro e le pagine Es. geografia_ilgirodelmondo_pp_136_137.md avrà Categoria=geografia, Libro=ilgirodelmondo, Pagine=136,137
    c. Elaborare il testo (correzioni e metadati).
    d. Scrivi il nuovo file corretto in 'documents/' con 'write_file'.
3. Crea un file index.md che contenga un indice di tutti i file in 'documents/'. Linka i file originali usando [[filename]]
4. Se il file index.md è già presente, aggiornalo con 'write_file'.
5. Non inventare i risultati. Se non usi i tool 'read_file' e 'write_file', non stai davvero lavorando.
6. Al termine cancella i file da 'raw_documents' usando 'file_delete'.

Se ti chiedo di darmi informazioni su un argomento, fai prima una ricerca su index.md e capisci quali file .md potrebbero 
contenere l'informazioni. Estrai poi il contenuto di questi file e passali in risposta.

"""

# 1. Crea il toolkit del filesystem (permette all'agente di leggere/scrivere)
working_directory = os.path.abspath("./persona/knowledge") # O la root del tuo progetto
fs_toolkit = FileManagementToolkit(
    root_dir=working_directory,
    selected_tools=["list_directory", "read_file", "write_file", "move_file", "file_delete"]
)
fs_tools = fs_toolkit.get_tools()
print(fs_tools)
subagent = create_agent(
    model=config.MAIN_LLM_MODEL, 
    tools=fs_tools,
)
@tool
def librarian(query: str) -> str:
    """
    Esegue la gestione dei documenti di Absalom: correzione, archiviazione e indicizzazione.
    Query accettate: 
        - 'aggiorna knowledge raw_documents'
        - ricerca informazioni su un argomento.
        - aiuto per studiare un argomanto: esempio: aiutami a studiare geografia pagina 187
    """
    logging.info(f"Librarian: {query}")

    # Costruiamo il prompt completo per il sub-agente
    prompt = f"{LIBRARIAN_PROMPT}\n\nRichiesta utente: {query}"

    result = subagent.invoke({"messages": [{"role": "user", "content": prompt}]})
    response = result['messages'][-1].content
    write_today_memory(f"Librarian: {response}")
    return response
    