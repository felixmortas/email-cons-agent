# Executive summary

### 📧 Automated Multi-Platform Account Migration Agent

Updating account emails across dozens of platforms is a manual nightmare. I built an advanced AI agent that automates this entire process—login to navigation to settings, bypassing some security loops, and handling multi-step verifications autonomously.

**The concept:** A Graph-based agentic system invoking ReAct agents that logs into web platforms, locates account settings via intelligent browsing, and manages the dual-email verification dance (old vs. new) using API integrations.

**Technical highlights:**

- **Advanced Agentic Orchestration:** Developed a sophisticated state machine using **LangGraph** to break down complex migrations into deterministic steps completed with LangChain ReAct agent (URL discovery, login, email change, verification).
- **Intelligent Browser Interaction:** Built a custom "Dynamic Page Snapshot" middleware that translates live DOM states into LLM-readable indexed buttons and text, allowing **Playwright** to navigate modern, JavaScript-heavy web apps with high precision.
- **Automated Verification Loop:** Integrated **Microsoft Graph API** to programmatically intercept verification codes and confirmation links from Outlook, closing the loop without human intervention.
- **Resilient & Scalable Architecture:** Implemented a **Model Fallback** mechanism (switching between Gemini and Mistral) and automated retry logic (3 times max) to ensure 24/7 reliability even when hitting API rate limits.
- **Production-Grade Monitoring:** Integrated **Langfuse** for full-trace observability, allowing for deep debugging of agent reasoning and cost optimization.
- **Batch Processing Power:** Includes a **Tkinter-based GUI** to filter and process **Bitwarden** vault exports, enabling mass account updates in a single execution.

**Results:** A highly autonomous system capable of handling the "dirty work" of account management, reducing a multiple-hour manual task to a few clicks with 100% data persistence and security.

# 📧 Automated Email Update Agent

An advanced, ReAct-based AI agent designed to automate the tedious process of changing account email addresses across various web platforms. By leveraging **LangGraph** for orchestration, **Playwright** for browser interaction, and **LangChain** for navigation decisions, this agent can navigate complex security settings, handle authentication, and solve verification loops autonomously.

## 🌟 Key Features

* **Agentic Workflow**: Uses LangGraph to manage each step of the process independently, enabling the agent to handle complexe tasks by breaking them down into subtasks.
* **Intelligent Browsing**: Powered by Playwright with stealth capabilities to try to handle some CAPTCHA verifications. A custom "Dynamic Page Snapshot" middleware keeps the LLM updated with the current DOM state.
* **Dual Operating Modes**:
    * **Single-Site**: Target a specific URL for an immediate update.
    * **Batch Mode**: Process a Bitwarden JSON export (saved as `./data/bitwarden_export.json`), complete with a Tkinter GUI for site filtering and real-time disk persistence.
* **Robust Verification**: Automated Outlook integration via Microsoft Graph API to retrieve verification codes on the old email adress and click confirmation links in the new one.
* **Resilient Architecture**: Includes model fallback logic (switching between Gemini and Mistral) and automated retry mechanisms up to 3 times on each step for high reliability.
* **Observability**: Full tracing and monitoring integrated via Langfuse.

---

## 🏗️ Project Architecture

The system is divided into several specialized layers:

### 1. Core Logic & Orchestration
* `main.py`: The central entry point handling CLI arguments and mode selection.
* `graph.py`: Defines the LangGraph state machine and the high-level workflow (deterministic).
* `nodes.py` & `nodes_utils.py`: Contains the operational logic for each step in the graph (e.g., URL finding, page initialization, login, email change).
* `state.py` & `context.py`: Define the schemas for data persistence and the runtime execution environment.

### 2. The Agent Layer (`/agent`)
* `agent.py`: A factory that initializes the LangChain ReAct agent with specific LLM configurations in each node to complete the step by itself.
* **Middleware**:
    * `dynamic_page_snapshot.py`: Constantly injects live HTML converted into indexed text snapshots into the system prompt.
    * `model_fallback.py`: Manages the hierarchy of LLMs to ensure service continuity in case of free plan limits reached.

### 3. Toolset (`/agent/tools`)
The agent utilizes a suite of LangChain-compatible tools to interact with the world:
* **Browser Tools**: `click_element.py`, `fill_text_field.py`, `refresh_page_representation.py`.
* **Verification Tools**: `get_verification_code.py`, `verify_new_email.py`.
* **Control Tools**: `complete_step.py`, `stop_execution.py`.

### 4. Services & Utilities (`/services`)
* **Browser**: `playwright_session.py` (Session & Context management).
* **Email**: `outlook_service.py` (MS Graph API integration).
* **UI/UX**: `gui_exclusion.py` (Tkinter-based site selector).
* **Search**: `search_engine.py` (Brave Search API integration for URL discovery).

---

## 🚀 Getting Started

### Prerequisites
* Miniconda environment manager 
* Playwright browsers installed (`playwright install chromium`)
* Microsoft Graph API credentials (for Outlook/Verification)
* LLM API Keys (Gemini and/or Mistral)

### Installation
```bash
conda create --file environment.yml
```

### Usage
**Single Site Mode:**
```bash
python -m main --website "example.com" --url "https://example.com/settings" --model "gemini-1.5-pro" --no-headless
```
_Only the --website argument is mandatory._
_--url will be found and --model is set to `mistral-small-latest` by default_

**Batch Mode (Bitwarden Export):**
```bash
python -m main --model "gemini-1.5-pro" --no-headless
```
_if --website argument is missing, the batch mode will be executed._
_Don't forget to save the Bitwarden export as `./data/bitwarden_export.json`_


---

## 📊 Data Flow & Safety
* **State Persistence**: In batch mode, the agent creates a timestamped working copy of your data to ensure the original export remains untouched.
* **Credential Safety**: Sensitive fields are handled through secure environment variables and injected into forms via specific automation tools.
* **Human-in-the-Loop**: Includes fallback mechanisms where the agent can prompt for human intervention if automated verification retrieval fails.

---

## 🛠️ Tech Stack
* **Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph)
* **Step completion**: [LangChain ReAct Agent](https://github.com/langchain-ai/langchain)
* **LLMs**: Google Gemini, Mistral AI
* **Browser automation**: [Playwright](https://playwright.dev/)
* **Monitoring**: [Langfuse](https://langfuse.com/)
