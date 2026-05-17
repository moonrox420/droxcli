"""Colorised terminal output helpers."""

from __future__ import annotations

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


def success(msg: str) -> str:
    return f"{Fore.LIGHTGREEN_EX}✓  {msg}{Style.RESET_ALL}"


def warning(msg: str) -> str:
    return f"{Fore.YELLOW}⚠  {msg}{Style.RESET_ALL}"


def error(msg: str) -> str:
    return f"{Fore.RED}✗  {msg}{Style.RESET_ALL}"


def info(msg: str) -> str:
    return f"{Fore.CYAN}ℹ  {msg}{Style.RESET_ALL}"


def step(n: int, total: int, msg: str) -> str:
    return f"{Fore.MAGENTA}[{n}/{total}]{Style.RESET_ALL} {msg}"


def divider(char: str = "─", width: int = 60) -> str:
    return f"{Fore.WHITE}{char * width}{Style.RESET_ALL}"


def dim(msg: str) -> str:
    return f"{Fore.WHITE}{msg}{Style.RESET_ALL}"


def bold(msg: str) -> str:
    return f"{Style.BRIGHT}{msg}{Style.RESET_ALL}"


def print_patch_preview(file: str, new_content: str, max_lines: int = 10) -> None:
    """Show a truncated preview of generated file content."""
    lines = new_content.splitlines()
    print(f"\n{Fore.LIGHTGREEN_EX}┌─ {file}{Style.RESET_ALL}")
    for i, line in enumerate(lines[:max_lines], 1):
        print(f"{Fore.WHITE}{i:4d}{Style.RESET_ALL}  {line}")
    if len(lines) > max_lines:
        remaining = len(lines) - max_lines
        print(f"      {Fore.CYAN}… +{remaining} more lines{Style.RESET_ALL}")
    print(f"{Fore.LIGHTGREEN_EX}└{'─' * 40}{Style.RESET_ALL}")
