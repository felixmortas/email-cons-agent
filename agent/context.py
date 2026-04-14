from typing import Optional, TypedDict

class Context(TypedDict):
    """Contexte d'exécution contenant la page Playwright"""
    page: Optional[object]
