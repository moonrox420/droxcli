"""ASCII art banner."""

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


def print_banner() -> None:
    print(f"""
{Fore.LIGHTGREEN_EX}
  ██████╗ ██████╗  ██████╗ ██╗  ██╗ ██████╗██╗     ██╗
  ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██╔════╝██║     ██║
  ██║  ██║██████╔╝██║   ██║ ╚███╔╝ ██║     ██║     ██║
  ██║  ██║██╔══██╗██║   ██║ ██╔██╗ ██║     ██║     ██║
  ██████╔╝██║  ██║╚██████╔╝██╔╝ ██╗╚██████╗███████╗██║
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚══════╝╚═╝
{Fore.MAGENTA}
         🤖 Agentic Coding Tool — Powered by Ollama
{Style.RESET_ALL}""")
