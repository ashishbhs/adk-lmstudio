# Local ADK

A powerful, local Agent Development Kit (ADK) that interfaces seamlessly with local LLM providers like [LM Studio](https://lmstudio.ai/) and [LiteLLM](https://docs.litellm.ai/docs/). 

Local ADK is designed to build and orchestrate production-ready AI agents on your local machine, complete with web search capabilities, a robust multi-agent research pipeline, and a FastAPI-based modern web interface.

## Features

- 🤖 **Local LLM Integration**: Built to work natively with LM Studio and LiteLLM. No cloud API keys required if running local models.
- 🕵️ **Multi-Agent Research Pipeline**: Implement complex tasks using a coordinated team of specialized agents:
  - **Planner Agent**: Breaks down queries into actionable research steps.
  - **Executor Agent**: Gathers evidence from the web.
  - **Synthesizer Agent**: Compiles findings into comprehensive reports.
- 🔎 **Robust Web Search Tools**: Built-in DuckDuckGo Lite web scraping using robust `BeautifulSoup` parsing to fetch titles, URLs, and snippets securely and effectively.
- ⚡ **FastAPI Server & UI**: A modern, streaming-enabled backend with an integrated HTML/JS frontend to visualize agent progress and pipeline stages in real-time.
- 🛠️ **Production Ready**: Modular structure, structured logging, custom exception handling, and robust Poetry dependency management.

## Prerequisites

- Python 3.10 to 3.13
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- A running instance of LM Studio or LiteLLM serving an OpenAI-compatible local API (usually at `http://localhost:1234/v1` or `http://localhost:4000`).

## Installation

1. **Clone or download the repository.**
2. **Install dependencies** using Poetry:
   ```bash
   poetry install
   ```
3. **Configure your environment**:
   If needed, create a `.env` file in the root directory and specify any local model ports or configuration details expected by the application.

## Usage

### Running the Server

Start the Local ADK application, which spins up the FastAPI web server:

```bash
poetry run local-adk
```

Navigate to `http://127.0.0.1:8000` (or the port specified by the server) to access the interactive web interface, view the multi-agent orchestration, and submit tasks.

### Running Tests

The project includes a suite of unit tests. Run them using:

```bash
poetry run pytest
```

## Architecture Overview

- **`src/local_adk/agent.py`**: Defines agent creation and behaviors, leveraging the ADK framework.
- **`src/local_adk/llm.py`**: Manages the connection and integration with the local LLM providers.
- **`src/local_adk/tools/search_tools.py`**: Contains web interaction tools, including asynchronous search execution and webpage text extraction.
- **`src/local_adk/ui/`**: Houses the frontend application (HTML, CSS, JS).
- **`src/local_adk/main.py`**: The main FastAPI application entry point.

## Contributing

Contributions are welcome! Please make sure to add tests for new features and ensure `pytest` passes before submitting PRs.

## License

This project is licensed under the MIT License.
