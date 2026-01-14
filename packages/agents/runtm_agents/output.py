"""Output formatting utilities for agent output.

Provides functions to format and display agent output in the terminal.
"""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from runtm_agents.adapters.base import AgentOutput

console = Console()


def format_output(output: AgentOutput, verbose: bool = True) -> str | None:
    """Format an AgentOutput for display.

    Args:
        output: The output event to format
        verbose: Whether to show detailed output

    Returns:
        Formatted string, or None if output should be hidden
    """
    if output.type == "text":
        return output.content

    elif output.type == "tool_use":
        if verbose:
            return f"  [dim]{output.content}[/dim]"
        return None

    elif output.type == "error":
        return f"  [red]Error: {output.content}[/red]"

    elif output.type == "result":
        return f"  [dim]{output.content}[/dim]"

    elif output.type == "system":
        if verbose:
            return f"  [cyan]{output.content}[/cyan]"
        return None

    return None


class StreamingOutputHandler:
    """Handler for streaming agent output to the terminal.

    Provides a context manager for displaying agent output with
    a spinner and progress updates.
    """

    def __init__(self, message: str = "Claude is working...", verbose: bool = True):
        """Initialize the handler.

        Args:
            message: Initial spinner message
            verbose: Whether to show detailed output
        """
        self.message = message
        self.verbose = verbose
        self._live: Live | None = None
        self._spinner = Spinner("dots", text=message)
        self._outputs: list[str] = []

    def __enter__(self) -> StreamingOutputHandler:
        """Start the live display."""
        self._live = Live(self._spinner, console=console, refresh_per_second=10)
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop the live display."""
        if self._live:
            self._live.__exit__(exc_type, exc_val, exc_tb)

    def update(self, output: AgentOutput) -> None:
        """Update the display with new output.

        Args:
            output: The output event to display
        """
        formatted = format_output(output, self.verbose)
        if formatted:
            self._outputs.append(formatted)

            # Update spinner with latest output
            if self._live:
                text = Text()
                text.append(self._spinner.text)
                if self._outputs:
                    text.append("\n")
                    # Show last few outputs
                    for line in self._outputs[-5:]:
                        text.append(f"{line}\n")
                self._live.update(text)

    def set_message(self, message: str) -> None:
        """Update the spinner message.

        Args:
            message: New message to display
        """
        self._spinner = Spinner("dots", text=message)
        if self._live:
            self._live.update(self._spinner)
