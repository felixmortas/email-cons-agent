from langchain.agents.middleware.model_fallback import ModelFallbackMiddleware

fallback = ModelFallbackMiddleware(
    "google_genai:gemini-3-flash-preview",
    "google_genai:gemini-3.1-flash-lite-preview",
    "mistralai:mistral-small-latest",
    "mistralai:mistral-large-latest",
)
