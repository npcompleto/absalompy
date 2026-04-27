from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import create_agent
from dotenv import load_dotenv
import config
from utils import write_today_memory

load_dotenv()
RESEARCHER_PROMPT="""
        Il Ricercatore (Search Agent)

        Sei il ricercatore di Absalom. 
        Il tuo compito è:
        - Cercare informazioni recenti nel web e fornire risposte precise e sintetizzate. Adatte ad una ragazza delle medie.
        - Intervenire se l'utente richiede informazioni recenti che non conosci già, come notizie, gossip, eventi sportivi, ecc.
        - Intervieni se l'utente richiede informazioni dettagliate su un argomento specifico.

        ## Ricerca e Recupero
        Se il contenuto non è adatto ad una ragazza delle medie, riscrivilo in modo che lo sia.
        Non permettere ricerche su argomenti non adatti ad una ragazza delle medie.

        ## Strumenti
        - DuckDuckGoSearchRun: Cerca informazioni nel web. Usalo solo quando l'utente richiede informazioni recenti che non conosci già.

    """
subagent = create_agent(model=config.MAIN_LLM_MODEL, tools=[DuckDuckGoSearchRun()])
@tool
def research(query: str) -> str:
    """
        Il Ricercatore (Search Agent)

        Sei il ricercatore di Absalom. 
        Il tuo compito è:
        - Cercare informazioni recenti nel web e fornire risposte precise e sintetizzate. Adatte ad una ragazza delle medie.
        - Intervenire se l'utente richiede informazioni recenti che non conosci già, come notizie, gossip, eventi sportivi, ecc.
        - Intervieni se l'utente richiede informazioni dettagliate su un argomento specifico.

    """
    result = subagent.invoke({"messages": [{"role": "user", "content": query}]})
    response = result['messages'][-1].content
    write_today_memory(f"Researcher: {response}")
    return response
    