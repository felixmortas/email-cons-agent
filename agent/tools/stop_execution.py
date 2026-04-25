from langchain.tools import tool

class StopExecutionError(Exception):
    """Raised by the stop_execution tool to halt the entire graph immediately."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

@tool
def stop_execution(reason: str) -> str:
    """
    Appelez cette fonction pour interrompre immédiatement l'exécution du graph.
    À utiliser lorsque la tâche est impossible à réaliser ou qu'une erreur bloquante se produit.
    
    Args :
        reason : explication compréhensible indiquant pourquoi l'exécution doit être interrompue.

    """
    print("[DEBUG] Use tool stop_execution")
    raise StopExecutionError(reason)