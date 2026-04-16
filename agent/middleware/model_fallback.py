from langchain.agents.middleware.model_fallback import ModelFallbackMiddleware

# Free models:
# - https://ai.google.dev/gemini-api/docs/pricing?hl=fr


fallback = ModelFallbackMiddleware(
    "mistralai:mistral-large-latest",
    # "google_genai:gemini-3.1-flash-live-preview",
    "google_genai:gemini-3.1-flash-lite-preview",
    "google_genai:gemini-3-flash-preview",
    "google_genai:gemini-2.5-pro",
    "mistralai:mistral-small-latest",
    "google_genai:gemini-2.5-flash",
    "google_genai:gemini-2.5-flash-lite",
    "google_genai:gemini-2.5-flash-lite-preview-09-2025",
)
