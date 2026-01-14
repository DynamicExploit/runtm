"""Claude Code CLI adapter.

Wraps the `claude` CLI tool to provide programmatic access to Claude Code.
Uses the stream-json output format for real-time event streaming.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path

import structlog

from .base import AgentAdapter, AgentOutput, AgentResult

logger = structlog.get_logger()


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI.

    Executes prompts via `claude -p "prompt" --output-format stream-json`
    and parses the streaming JSON output.
    """

    def __init__(self):
        """Initialize the adapter."""
        self._last_session_id: str | None = None
        self._last_result: AgentResult | None = None
        self._start_time: float = 0.0

    @property
    def name(self) -> str:
        """Agent name."""
        return "claude-code"

    def check_installed(self) -> bool:
        """Check if Claude Code CLI is installed."""
        return shutil.which("claude") is not None

    def check_auth(self) -> bool:
        """Check if Claude Code is authenticated.

        Claude Code stores auth in ~/.claude/. We do a simple check
        for the CLI being available - actual auth happens on first use.
        """
        return self.check_installed()

    async def prompt(
        self,
        prompt: str,
        workspace: Path,
        *,
        continue_session: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[AgentOutput]:
        """Execute prompt via Claude Code CLI.

        Args:
            prompt: The prompt to send to Claude
            workspace: Working directory for the agent
            continue_session: Claude session ID to continue
            stream: Whether to stream output (always True for now)

        Yields:
            AgentOutput events as they occur
        """
        self._start_time = time.time()

        # Build command
        # Note: --verbose is required when using -p with --output-format=stream-json
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",  # Autopilot mode
        ]

        if continue_session:
            cmd.extend(["--resume", continue_session])

        logger.debug("Running claude command", cmd=cmd, workspace=str(workspace))

        # Track results
        files_created: list[str] = []
        files_modified: list[str] = []
        commands_run: list[str] = []
        error_msg: str | None = None

        # Run process
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Stream stdout (newline-delimited JSON)
            if process.stdout:
                async for line in process.stdout:
                    if not line:
                        continue

                    line_str = line.decode().strip()
                    if not line_str:
                        continue

                    try:
                        event = json.loads(line_str)
                    except json.JSONDecodeError:
                        # Plain text output (shouldn't happen with stream-json)
                        yield AgentOutput(type="text", content=line_str)
                        continue

                    # Parse Claude Code stream-json format
                    event_type = event.get("type", "unknown")

                    if event_type == "assistant":
                        # Assistant message with content blocks
                        message = event.get("message", {})
                        content_blocks = message.get("content", [])

                        for block in content_blocks:
                            block_type = block.get("type", "")

                            if block_type == "text":
                                text = block.get("text", "")
                                if text:
                                    yield AgentOutput(type="text", content=text)

                            elif block_type == "tool_use":
                                tool_name = block.get("name", "")
                                tool_input = block.get("input", {})

                                # Create a readable summary
                                if tool_name == "Write":
                                    file_path = tool_input.get("file_path", "")
                                    summary = f"Writing {file_path}"
                                    if file_path and file_path not in files_modified:
                                        files_modified.append(file_path)
                                elif tool_name == "Edit":
                                    file_path = tool_input.get("file_path", "")
                                    summary = f"Editing {file_path}"
                                    if file_path and file_path not in files_modified:
                                        files_modified.append(file_path)
                                elif tool_name == "Bash":
                                    cmd_str = tool_input.get("command", "")
                                    summary = f"Running: {cmd_str[:80]}..."
                                    commands_run.append(cmd_str)
                                elif tool_name == "Read":
                                    file_path = tool_input.get("file_path", "")
                                    summary = f"Reading {file_path}"
                                else:
                                    summary = f"{tool_name}"

                                yield AgentOutput(
                                    type="tool_use",
                                    content=summary,
                                    metadata={"tool": tool_name, "input": tool_input},
                                )

                    elif event_type == "result":
                        # Final result with session info
                        self._last_session_id = event.get("session_id")
                        cost_usd = event.get("cost_usd", 0)
                        yield AgentOutput(
                            type="result",
                            content=f"Completed (cost: ${cost_usd:.4f})",
                            metadata={"session_id": self._last_session_id, "cost_usd": cost_usd},
                        )

                    elif event_type == "error":
                        error_info = event.get("error", {})
                        error_msg = error_info.get("message", "Unknown error")
                        yield AgentOutput(
                            type="error",
                            content=error_msg,
                            metadata={"error": error_info},
                        )

                    elif event_type == "system":
                        # System messages (like subagent output)
                        subtype = event.get("subtype", "")
                        message = event.get("message", "")
                        if message:
                            yield AgentOutput(
                                type="system",
                                content=message,
                                metadata={"subtype": subtype},
                            )

            # Wait for process
            await process.wait()

            # Capture any stderr
            if process.stderr:
                stderr = await process.stderr.read()
                if stderr:
                    stderr_str = stderr.decode().strip()
                    if stderr_str and not error_msg:
                        error_msg = stderr_str
                        # Yield the stderr error so it's visible to the user
                        yield AgentOutput(type="error", content=stderr_str)

            # If process failed with no output, provide a helpful error
            if process.returncode != 0 and not error_msg:
                error_msg = f"Claude exited with code {process.returncode}"
                yield AgentOutput(type="error", content=error_msg)

            # Store result
            duration = time.time() - self._start_time
            self._last_result = AgentResult(
                session_id=self._last_session_id or "",
                success=process.returncode == 0 and error_msg is None,
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
                error=error_msg if process.returncode != 0 else None,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            error_msg = "Claude Code CLI not found. Install from https://claude.ai/code"
            yield AgentOutput(type="error", content=error_msg)
            self._last_result = AgentResult(
                session_id="",
                success=False,
                error=error_msg,
                duration_seconds=time.time() - self._start_time,
            )

        except Exception as e:
            error_msg = f"Error running Claude Code: {e}"
            logger.exception("Claude Code execution failed", error=str(e))
            yield AgentOutput(type="error", content=error_msg)
            self._last_result = AgentResult(
                session_id="",
                success=False,
                error=error_msg,
                duration_seconds=time.time() - self._start_time,
            )

    def get_result(self) -> AgentResult:
        """Get result from last prompt."""
        if not self._last_result:
            return AgentResult(
                session_id="",
                success=False,
                error="No prompt executed",
            )
        return self._last_result
