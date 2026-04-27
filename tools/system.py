import os
from langchain_core.tools import tool
@tool
def shutdown():
    """
    Spegne il sistema. Usalo quando l'utente ti da la buonanotte o ti dice di spegnerti.
    """
    os.system("sudo shutdown now")