import json
import os
from pathlib import Path
from typing import Any

from ripen.common.utils import get_logger, safe_main_executor

logger = get_logger("init")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    logger.info("""
    \033[1;32m      
    ██████╗ ██╗██████╗ ███████╗███╗   ██╗
    ██╔══██╗██║██╔══██╗██╔════╝████╗  ██║
    ██████╔╝██║██████╔╝█████╗  ██╔██╗ ██║
    ██╔══██╗██║██╔═══╝ ██╔══╝  ██║╚██╗██║
    ██║  ██║██║██║     ███████╗██║ ╚████║
    ╚═╝  ╚═╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═══╝
    \033[0m
    \033[1;36m🧠 Knowledge Hub for AI Agents\033[0m
    ====================================
    """)


def ask_question(question: str, default: Any = None, options: list[str] | None = None) -> str:
    prompt = f"\n\033[1;34m? \033[0m{question}"
    if options:
        prompt += f" ({'/'.join(options)})"
    if default:
        prompt += f" [\033[1;37m{default}\033[0m]"
    prompt += ": "

    while True:
        choice = input(prompt).strip()
        if not choice and default:
            return str(default)
        if options and choice.lower() not in [o.lower() for o in options]:
            logger.info(
                f"\033[1;31m! Invalid choice. Please choose from: {', '.join(options)}\033[0m"
            )
            continue
        if choice:
            return choice


def main():
    clear_screen()
    print_banner()

    logger.info("Welcome to Ripen! Let's get your brain infrastructure set up.")
    logger.info("\n\033[1;33m--- Hub Mode (Setting up a local knowledge server) ---\033[0m")
    
    config = {}

    # 1. Base Directory
    default_home = Path.home() / ".ripen"
    ripen_home = ask_question("Where should knowledge be stored?", default=str(default_home))
    config["ripen_home"] = str(Path(ripen_home).absolute())

    # 2. LLM Provider
    logger.info("\n\033[1;33mStep 2: LLM Provider\033[0m (Required for knowledge distillation)")
    provider = ask_question(
        "Which LLM provider would you like to use?",
        default="ollama",
        options=["gemini", "ollama", "none"],
    )
    config["llm_provider"] = provider.lower()

    if provider.lower() == "gemini":
        logger.info("\n\033[1;31m!!! PRIVACY WARNING !!!\033[0m")
        logger.info(
            "Using an external LLM like Gemini will send snippets of your codebase and AI agent "
            "reasoning"
        )
        logger.info(
            "to Google's servers for background knowledge distillation. For strict enterprise "
            "or confidential"
        )
        logger.info("environments, we strongly recommend using a local LLM via Ollama instead.")
        
        api_key = ask_question("Enter your GOOGLE_API_KEY (from https://aistudio.google.com/):")
        config["google_api_key"] = api_key
        if len(api_key) < 20:
            logger.info("\033[1;31m! Warning: That API key looks a bit short.\033[0m")

    elif provider.lower() == "ollama":
        config["ollama_base_url"] = ask_question(
            "Ollama API URL?", default="http://localhost:11434"
        )
        config["ollama_model"] = ask_question("Ollama Model?", default="gemma4:e2b")
        logger.info("\n\033[1;33mNote:\033[0m Make sure Ollama is running (`ollama serve`)!")

    # 3. Port (Fixed to Streamable HTTP)
    config["sse_port"] = 8377
    config["default_transport"] = "sse" # Keep for compatibility in config.py

    # 4. Save Config
    ripen_home_path = Path(config["ripen_home"])
    ripen_home_path.mkdir(parents=True, exist_ok=True)

    config_file = ripen_home_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info(f"\n\033[1;32m✅ Configuration saved to {config_file}\033[0m")

    logger.info("\n" + "=" * 40)
    logger.info("\033[1;32m🎉 Hub Setup Complete!\033[0m")
    logger.info("\nTo start your Hub server:")
    logger.info("  \033[1;36mripen\033[0m (or run ripen-hub.exe)")
    
    logger.info("\nClient Connection URL: \033[1;33mhttp://localhost:8377/mcp\033[0m")
    
    logger.info("\nTo connect your agents, add this to your client config (e.g., mcp_config.json):")
    logger.info("""
    "ripen": {
      "command": "npx",
      "args": ["-y", "@sammacbeth/mcp-remote", "http://localhost:8377/mcp"]
    }
    """)
    logger.info("=" * 40)


if __name__ == "__main__":
    safe_main_executor(main)()
