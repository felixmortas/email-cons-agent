"""
Langfuse Integration Setup

Utility for initializing the Langfuse client and establishing a tracing callback handler 
to monitor LangChain executions.
"""

from langfuse import get_client
from langfuse.langchain import CallbackHandler
 
# Initialize Langfuse client
langfuse = get_client()

# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")
     
# Initialize Langfuse CallbackHandler for Langchain (tracing)
langfuse_handler = CallbackHandler()
