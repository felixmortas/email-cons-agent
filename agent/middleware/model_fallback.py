from langchain.agents.middleware.model_fallback import ModelFallbackMiddleware

fallback = ModelFallbackMiddleware(
    "mistralai:mistral-small-latest",
    "google_genai:gemini-3.1-flash-lite-preview",
    "google_genai:gemini-3-flash-preview",
    "mistralai:mistral-large-latest",
)
