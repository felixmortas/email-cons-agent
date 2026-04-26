"""
Search Engine Module

A module providing web search capabilities via pluggable providers. 
It supports live search using the Brave Search API and includes a mock provider for testing environments.
"""

import requests
import os

# Load environment variables: Brave API key
from dotenv import load_dotenv
load_dotenv()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

# --- PROVIDERS CONFIGURATION ---

class BraveProvider:
    """Brave Search API provider"""
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.search.brave.com/res/v1/web/search"
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }

    def search(self, query, num_results=5, debug_mode=False):
        params = {"q": query}
        response = requests.get(self.url, headers=self.headers, params=params)
        
        # Check if response is successful
        if response.status_code != 200:
            return []

        results = response.json()
        web_results = results.get("web", {}).get("results", [])
        
        if debug_mode:
            return ['https://www.agrosemens.com/', 'https://graines-biologiques.com/', 'https://www.facebook.com/agrosemens.semencesbio/?locale=fr_FR', 'https://www.instagram.com/agrosemens_bio/', 'https://fr.linkedin.com/company/agrosemens']
        
        return [item['url'] for item in web_results[:num_results]]        
    
search_engine = BraveProvider(BRAVE_API_KEY)