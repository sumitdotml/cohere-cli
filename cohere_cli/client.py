import cohere
import os
import sys
import json
from typing import List, Dict, Any
from datetime import datetime
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

# Import configuration
from . import config


def get_workspace_context(directory: str) -> str:
    """Get context about the current workspace."""
    files = []
    # Use config for scan depth and max files
    max_depth = config.MAX_SCAN_DEPTH
    max_files = config.MAX_FILES_CONTEXT

    for root, dirs, filenames in os.walk(directory):
        # skipping hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        # checking depth
        depth = root[len(directory) :].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []  # stopping to go deeper
            continue

        # adding non-hidden files
        for filename in filenames:
            if not filename.startswith("."):
                rel_path = os.path.relpath(os.path.join(root, filename), directory)
                if not any(part.startswith(".") for part in rel_path.split(os.sep)):
                    files.append(rel_path)
                    if len(files) >= max_files:
                        break

        if len(files) >= max_files:
            break

    context = f"Current working directory: {directory}\n"
    if files:
        context += "Available files:\n"
        for file in files:
            context += f"- {file}\n"
    else:
        context += "No relevant files found in this directory.\n"

    return context


def read_file(file_path: str, workspace_dir: str) -> List[Dict[str, str]]:
    """Read a file from the workspace and return its content."""
    try:
        # resolving relative path to absolute path
        if not os.path.isabs(file_path):
            file_path = os.path.join(workspace_dir, file_path)

        # checking if file exists
        if not os.path.exists(file_path):
            return [{"content": f"Error: File not found: {file_path}"}]

        # checking if file is too big (>5MB)
        if os.path.getsize(file_path) > 5 * 1024 * 1024:
            return [
                {
                    "content": f"Error: File is too large: {file_path}. File size is limited to 5MB."
                }
            ]

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return [{"content": content, "file_path": file_path}]
    except Exception as e:
        return [{"content": f"Error reading file: {str(e)}"}]


def get_tools() -> List[Dict[str, Any]]:
    """Define tools that the Cohere model can use."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file in the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file, relative to the current workspace directory",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        }
    ]


def format_timestamp() -> str:
    """formatting current timestamp for messages."""
    # Use config for timestamp format
    return datetime.now().strftime(config.TIMESTAMP_FORMAT)


def create_chat_client() -> cohere.ClientV2:
    """creating a chat client."""

    # Get the project directory from the environment variable set by the wrapper
    project_dir_env = os.getenv("PROJECT_DIR")
    if not project_dir_env:
        raise ValueError(
            "PROJECT_DIR environment variable not set. Run using the wrapper script."
        )

    # Look for .env specifically in the project directory defined by the wrapper
    env_path = os.path.join(project_dir_env, ".env")
    if not os.path.exists(env_path):
        raise ValueError(f".env file not found in the project directory: {env_path}")

    load_dotenv(dotenv_path=env_path, override=True)

    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise ValueError("COHERE_API_KEY environment variable not set in .env file")
    return cohere.ClientV2(api_key)


def initialize_chat(console: Console) -> tuple[cohere.ClientV2, str, str, List[dict]]:
    """initializing chat components with progress indicator."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold yellow]{task.description}[/bold yellow]"),
        console=console,
        transient=True,
    ) as progress:
        # Step 1: initializing client
        task = progress.add_task("Initializing Cohere Chat...", total=3)
        co = create_chat_client()
        progress.update(task, advance=1)

        # Step 2: getting workspace context
        progress.update(task, description="Scanning workspace...")
        workspace_dir = os.getcwd()
        workspace_context = get_workspace_context(workspace_dir)
        progress.update(task, advance=1)

        # Step 3: creating conversation history
        progress.update(task, description="Setting up chat...")
        # Use config for system prompt template
        system_prompt = config.SYSTEM_PROMPT_TEMPLATE.format(
            workspace_context=workspace_context
        )
        conversation_history = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        progress.update(task, advance=1)

    return co, workspace_dir, workspace_context, conversation_history


def process_response(
    console: Console, stream, conversation_history: List[dict]
) -> None:
    """processing streaming response with clean markdown formatting."""
    COLORS = {
        "base": "#1e1e2e",  # Base
        "text": "#cdd6f4",  # Text
        "blue": "#89b4fa",  # Blue
        "lavender": "#b4befe",  # Lavender
        "overlay": "#313244",  # Overlay0
        "surface": "#45475a",  # Surface0
        "subtext": "#a6adc8",  # Subtext0
        "green": "#a6e3a1",  # Green
        "red": "#f38ba8",  # Red
        "yellow": "#f9e2af",  # Yellow
        "purple": "#cba6f7",  # Purple
    }

    # Use config for assistant label
    console.print(
        f"\n[dim]{format_timestamp()}[/dim] [bold {COLORS['blue']
                                                   }]{config.ASSISTANT_LABEL}:[/bold {COLORS['blue']}]"
    )

    # creating a panel for the streaming content
    full_response = ""

    spinner_frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
    spinner_idx = 0

    # function to render markdown or plain text based on content
    def render_content():
        nonlocal spinner_idx
        try:
            spinner = spinner_frames[spinner_idx % len(spinner_frames)]
            spinner_idx += 1

            if full_response:
                try:
                    md = Markdown(
                        full_response,
                        style=COLORS["text"],
                        code_theme="dracula",
                        justify="left",
                    )

                    # applying rich styles directly to markdown elements
                    md.style_links = COLORS["blue"]
                    md.style_bold = f"bold {COLORS['text']}"
                    md.style_italic = f"italic {COLORS['text']}"
                    md.style_code = COLORS["purple"]

                    # using a clean panel with minimal styling and light blue border
                    return Panel(
                        md,
                        style=f"on {COLORS['base']}",
                        border_style=COLORS["lavender"],
                        title=f"{spinner} Thinking...",
                        title_align="left",
                        padding=(0, 1),
                    )
                except Exception as e:
                    # fallback to plain text with basic styling
                    return Panel(
                        Text(full_response, style=COLORS["text"]),
                        style=f"on {COLORS['base']}",
                        border_style=COLORS["lavender"],
                        title=f"{spinner} Thinking...",
                        title_align="left",
                        padding=(0, 1),
                    )
            else:
                return Panel(
                    Text("", style=COLORS["text"]),
                    style=f"on {COLORS['base']}",
                    border_style=COLORS["lavender"],
                    title=f"{spinner} Thinking...",
                    title_align="left",
                    padding=(0, 1),
                )
        except Exception as e:
            return Text(f"Error rendering: {str(e)}", style=f"bold {COLORS['red']}")

    # using a live display with the custom renderer
    with Live(
        render_content(),
        console=console,
        refresh_per_second=10,
        vertical_overflow="visible",
    ) as live:
        for chunk in stream:
            if chunk and chunk.type == "content-delta":
                text_chunk = chunk.delta.message.content.text
                full_response += text_chunk
                live.update(render_content())

    # adding the final response to conversation history
    conversation_history.append({"role": "assistant", "content": full_response})


def execute_tools(tool_calls, workspace_dir):
    """Execute the tools called by the model."""
    results = []
    for tool_call in tool_calls:
        if tool_call.type == "function" and tool_call.function.name == "read_file":
            args = json.loads(tool_call.function.arguments)
            file_path = args.get("file_path", "")
            result = read_file(file_path, workspace_dir)
            results.append({"tool_call_id": tool_call.id, "result": result})
    return results


def chat_loop():
    """initializing the chat loop."""
    console = Console()

    try:
        # initializing chat components
        co, workspace_dir, workspace_context, conversation_history = initialize_chat(
            console
        )
    except Exception as e:
        error_panel = Panel(
            f"[bold red]{str(e)}[/bold red]", title="Initialization Error", style="red"
        )
        console.print(error_panel)
        return 1

    # initializing prompt session with HTML formatting
    session = PromptSession(
        history=InMemoryHistory(),
        style=Style.from_dict(
            {
                "timestamp": "#666666",  # gray
                "prompt": "#a172fc bold",  # purple
                "input": "white",
            }
        ),
    )
    header_text = Text()
    header_text.append("\nCohere CLI\n", style="bold blue")
    header_text.append(
        "A command line tool to interact with your directory, files, and folders through Cohere's API.\n",
        style="dim",
    )
    header_text.append("Built with ❤️ by ", style="dim")
    header_text.append(
        "Sumit", style="dim underline link https://github.com/sumitdotml"
    )
    header_text.append("\n", style="dim")
    header_text.append(f"Workspace: {os.path.basename(workspace_dir)}\n", style="dim")
    header_text.append(f"Model: {config.MODEL_NAME}\n", style="dim")
    header_text.append("Type 'exit' to quit, 'help' for commands\n", style="dim")

    header = Panel(
        header_text,
        border_style="bold blue",
        padding=(1, 2),
        title="👾 Cohere CLI",
        subtitle=f"v{config.VERSION}",
    )
    console.print(header)

    tools = get_tools()

    while True:
        try:
            timestamp = format_timestamp()
            prompt_text = f"<timestamp>{
                timestamp}</timestamp> <prompt>{config.USER_LABEL}:</prompt> "
            prompt = HTML(prompt_text)
            user_input = session.prompt(prompt)

            if user_input.lower() == "exit":
                console.print("\n[bold blue]Goodbye![/bold blue]")
                break

            if not user_input:
                continue

            if user_input.lower() == "help":
                help_panel = Panel(
                    "Available Commands:\n"
                    + "- exit: Exit the chat\n"
                    + "- help: Show this help message\n"
                    + "- clear: Clear the screen\n"
                    + "- rescan: Rescan current directory\n"
                    + "\nThe assistant has access to files in your current directory.",
                    title="Help",
                    style="bold #a172fc",
                )
                console.print(help_panel)
                continue

            if user_input.lower() == "clear":
                console.clear()
                console.print(header)
                continue

            if user_input.lower() == "rescan":
                workspace_context = get_workspace_context(workspace_dir)
                # Use config for system prompt template on rescan
                system_prompt = config.SYSTEM_PROMPT_TEMPLATE.format(
                    workspace_context=workspace_context
                )
                conversation_history[0]["content"] = system_prompt
                console.print("[bold #a172fc]Workspace rescanned![/bold #a172fc]")
                continue

            # adding user message to history
            conversation_history.append({"role": "user", "content": user_input})

            # first, checking if model wants to use tools
            console.print(
                f"\n[dim]{format_timestamp()
                          }[/dim] [dim]Thinking...[/dim]"
            )
            # Use config for model name
            response = co.chat(
                model=config.MODEL_NAME, messages=conversation_history, tools=tools
            )

            # checking if there are tool calls
            if response.message.tool_calls:
                console.print(
                    f"[dim]{format_timestamp()}[/dim] [dim]Reading files...[/dim]"
                )

                # executing tool calls
                tool_results = execute_tools(response.message.tool_calls, workspace_dir)

                # adding assistant message with tool calls
                conversation_history.append(
                    {
                        "role": "assistant",
                        "tool_calls": response.message.tool_calls,
                        "tool_plan": response.message.tool_plan,
                    }
                )

                # adding tool results to conversation history
                for result in tool_results:
                    tool_content = []
                    for data in result["result"]:
                        tool_content.append(
                            {"type": "document", "document": {"data": json.dumps(data)}}
                        )

                    conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": result["tool_call_id"],
                            "content": tool_content,
                        }
                    )

                # getting final response with tool results
                stream = co.chat_stream(
                    # Use config for model name
                    model=config.MODEL_NAME,
                    messages=conversation_history,
                    tools=tools,
                )
                process_response(console, stream, conversation_history)
            else:
                # if no tool calls, just stream the response
                stream = co.chat_stream(
                    # Use config for model name
                    model=config.MODEL_NAME,
                    messages=conversation_history,
                    tools=tools,
                )
                process_response(console, stream, conversation_history)

        except KeyboardInterrupt:
            console.print("\n\n[bold blue]Goodbye![/bold blue]")
            break
        except Exception as e:
            error_panel = Panel(
                f"[bold red]{str(e)}[/bold red]", title="Error", style="red"
            )
            console.print(error_panel)
            continue

    return 0


if __name__ == "__main__":
    sys.exit(chat_loop())
