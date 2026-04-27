"""
Agente principale di Absalom
"""

import os
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from tools.memory import remember
from subagents.researcher import research
from subagents.librarian import librarian
from tools.school_tool import add_school_event, list_school_events
from tools.time_tool import get_next_week_start_date, set_alarm
from tools.system import shutdown
from config import LLM_PROVIDER, MAIN_LLM_MODEL
import logging
from datetime import datetime


def get_today_memory():
        """Recupera la memoria della giornata corrente se esistente."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filepath = os.path.join("persona", "memory", f"{date_str}.txt")
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logging.error(f"Errore nel recupero della memoria: {e}")
        return ""

def get_long_term_memory():
    try:
        with open("persona/memory/long_term_memory.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Errore nel recupero della memoria: {e}")
    return ""

def get_persona():
        """Carica e concatena i file della personalità."""
        persona = ""
        try:
            # Carichiamo sia l'identità principale che quella del Bibliotecario/Wiki
            for filename in ["Identity.md", "Librarian.md"]:
                path = os.path.join("persona", filename)
                if os.path.exists(path):
                    with open(path, "r") as f:
                        persona += f.read() + "\n\n"
        except Exception as e:
            logging.error(f"Errore nel caricamento della persona: {e}")
        return persona

@dynamic_prompt
def today_system_prompt(request: ModelRequest) -> str:
    system_prompt = get_persona()
    # Aggiunge la memoria odierna al prompt di sistema come contesto
    today_memory = get_today_memory()
    if today_memory:
        system_prompt += "\n Oggi è il " + datetime.now().strftime("%Y-%m-%d") + " ed è " + datetime.now().strftime("%A") + ".\n"
        system_prompt += f"\nQui trovi la cronologia della conversazione di oggi per darti contesto:\n{today_memory}\n"
    
    long_term_memory = get_long_term_memory()
    if long_term_memory:
        system_prompt += f"\nQui trovi la memoria a lungo termine:\n{long_term_memory}\n"
    return system_prompt

class Agent:
    _instance = None  # Memorizza l'unica istanza della classe

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logging.info("Creazione istanza Singleton di Agent")
            cls._instance = super(Agent, cls).__new__(cls)
            # Inizializziamo gli attributi solo la prima volta
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.agent = create_agent(
            model=MAIN_LLM_MODEL,
            tools=[
                list_school_events, 
                get_next_week_start_date, 
                set_alarm,
                librarian,
                remember,
                research,
                shutdown
            ],
            middleware=[today_system_prompt]
        )
        self._initialized = True
    
    def ask(self, question):
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": question}]}
        )
        return result["messages"][-1].content

    

    def save_to_memory(self, user_input, absalom_response):
        """Salva l'interazione nella memoria persistente in formato yyyy-MM-DD.txt."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            folder = os.path.join("persona", "memory")
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, f"{date_str}.txt")
            
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"Utente: {user_input}\n")
                f.write(f"Absalom: {absalom_response}\n\n")
        except Exception as e:
            logging.error(f"Errore durante il salvataggio della memoria: {e}")

    