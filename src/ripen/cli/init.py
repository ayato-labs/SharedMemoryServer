import json
import os
from pathlib import Path
from typing import Any
import sys

from ripen.common.utils import get_logger, safe_main_executor

logger = get_logger("init")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("""
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
            print(f"\033[1;31m! Invalid choice. Please choose from: {', '.join(options)}\033[0m")
            continue
        if choice:
            return choice


def main():
    clear_screen()
    print_banner()

    print("Welcome to Ripen! Let's get your brain infrastructure set up.")

    mode = ask_question("Select installation mode:", default="hub", options=["hub", "client"])

    if mode.lower() == "client":
        # --- CLIENT MODE ---
        print("\n\033[1;33m--- Client Mode (Connect to a shared Hub) ---\033[0m")
        hub_url = ask_question(
            "Enter the Ripen Hub URL (e.g., http://192.168.1.10:8377):",
            default="http://localhost:8377",
        )

        print(f"\nRegistering with Hub at {hub_url}...")
        try:
            from ripen.cli.register import register_mcp

            register_mcp(hub_url=hub_url)
            print(
                "\n\033[1;32m🎉 Client setup complete! Ripen Hub is now connected to your IDEs.\033[0m"
            )
        except Exception as e:
            print(f"\n\033[1;31m! Registration failed: {e}\033[0m")
        return

    # --- HUB MODE (Original) ---
    print("\n\033[1;33m--- Hub Mode (Setting up a local knowledge server) ---\033[0m")
    config = {}

    # 1. Base Directory
    default_home = Path.home() / ".ripen"
    ripen_home = ask_question("Where should knowledge be stored?", default=str(default_home))
    config["ripen_home"] = str(Path(ripen_home).absolute())

    # 2. LLM Provider
    print("\n\033[1;33mStep 2: LLM Provider\033[0m (Required for knowledge distillation)")
    provider = ask_question(
        "Which LLM provider would you like to use?",
        default="gemini",
        options=["gemini", "ollama", "none"],
    )
    config["llm_provider"] = provider.lower()

    if provider.lower() == "gemini":
        print("\n\033[1;31m!!! PRIVACY WARNING !!!\033[0m")
        print(
            "Using an external LLM like Gemini will send snippets of your codebase and AI agent reasoning"
        )
        print(
            "to Google's servers for background knowledge distillation. For strict enterprise or confidential"
        )
        print("environments, we strongly recommend using a local LLM via Ollama instead.")
        proceed = ask_question(
            "Do you want to proceed with Gemini?", default="y", options=["y", "n"]
        )
        if proceed.lower() != "y":
            print("\nPlease run ripen-init again and select 'ollama' or 'none'.")
            return

        api_key = ask_question("Enter your GOOGLE_API_KEY (from https://aistudio.google.com/):")
        config["google_api_key"] = api_key
        if len(api_key) < 20:
            print("\033[1;31m! Warning: That API key looks a bit short.\033[0m")

    elif provider.lower() == "ollama":
        config["ollama_base_url"] = ask_question(
            "Ollama API URL?", default="http://localhost:11434"
        )
        config["ollama_model"] = ask_question("Ollama Model?", default="llama3.1")
        print("\n\033[1;33mNote:\033[0m Make sure Ollama is running (`ollama serve`)!")

    # 3. Transport Mode
    print("\n\033[1;33mStep 3: Transport Mode\033[0m")
    transport = ask_question("Default transport mode?", default="sse", options=["stdio", "sse"])
    config["default_transport"] = transport.lower()

    if transport.lower() == "sse":
        config["sse_port"] = int(ask_question("SSE Port?", default="8377"))

    # 4. Save Config
    ripen_home_path = Path(config["ripen_home"])
    ripen_home_path.mkdir(parents=True, exist_ok=True)

    config_file = ripen_home_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"\n\033[1;32m✅ Configuration saved to {config_file}\033[0m")

    # 5. IDE Registration
    print("\n\033[1;33mStep 4: IDE Registration\033[0m")
    register = ask_question(
        "Would you like to register this Hub with your local IDEs?", default="y", options=["y", "n"]
    )

    if register.lower() == "y":
        try:
            from ripen.cli.register import register_mcp

            register_mcp(transport=config["default_transport"], port=config.get("sse_port", 8377))
        except Exception as e:
            print(f"\033[1;31m! Failed to auto-register: {e}\033[0m")

    print("\n" + "=" * 40)
    print("\033[1;32m🎉 Hub Setup Complete!\033[0m")
    print("\nTo start your Hub server:")
    if config["default_transport"] == "sse":
        print(f"  \033[1;36mripen --sse --port {config.get('sse_port', 8377)}\033[0m")
    else:
        print("  \033[1;36mripen\033[0m")

    if config["default_transport"] == "sse":
        import socket

        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "YOUR_IP"
        print(
            f"\nClient Connection URL: \033[1;33mhttp://{local_ip}:{config.get('sse_port', 8377)}\033[0m"
        )
        print(
            f"Dashboard: \033[1;35mhttp://localhost:{config.get('sse_port', 8377)}/dashboard\033[0m"
        )

    # 6. Desktop Shortcut (Windows Only for now)
    if sys.platform == "win32":
        print("\n\033[1;33mStep 5: Desktop Shortcut\033[0m")
        create_sc = ask_question(
            "Would you like to create a Desktop shortcut for easy startup?",
            default="y",
            options=["y", "n"],
        )
        if create_sc.lower() == "y":
            try:
                from ripen.cli.shortcut import create_launcher_bat, create_windows_shortcut

                launcher_path = create_launcher_bat(ripen_home)
                args = "--sse" if config.get("default_transport") == "sse" else ""
                if create_windows_shortcut(str(launcher_path), "Ripen Hub", arguments=args):
                    print("\033[1;32m  [SUCCESS] Created Desktop Shortcut\033[0m")
                else:
                    print("\033[1;31m  ! Failed to create shortcut.\033[0m")
            except Exception as e:
                print(f"\033[1;31m! Error creating shortcut: {e}\033[0m")

    print("=" * 40)


if __name__ == "__main__":
    safe_main_executor(main)()
