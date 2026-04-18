import subprocess
import os
import anthropic
from typing import Callable

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a helpful PC agent. You can perform multi-step tasks on the user's computer.
Use tools step by step to complete tasks. Think before each action.
Always reply in the same language the user writes in.
Be concise when reporting results."""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command and return the output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text content to a file (creates or overwrites).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: current)"},
            },
            "required": [],
        },
    },
]

DANGER_KEYWORDS = ("rm -rf", "format", "mkfs", "dd if=", ":(){", "shutdown", "reboot")


def _execute_tool(name: str, inputs: dict) -> str:
    if name == "bash":
        cmd = inputs["command"]
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            return output.strip() or "(нет вывода)"
        except subprocess.TimeoutExpired:
            return "Ошибка: превышено время ожидания (30с)"
        except Exception as e:
            return f"Ошибка: {e}"

    elif name == "read_file":
        try:
            with open(inputs["path"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Ошибка чтения: {e}"

    elif name == "write_file":
        try:
            path = inputs["path"]
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(inputs["content"])
            return f"Файл записан: {path}"
        except Exception as e:
            return f"Ошибка записи: {e}"

    elif name == "list_dir":
        path = inputs.get("path", ".")
        try:
            entries = sorted(os.listdir(path))
            return "\n".join(entries) or "(пусто)"
        except Exception as e:
            return f"Ошибка: {e}"

    return f"Неизвестный инструмент: {name}"


def run_agent(
    task: str,
    on_update: Callable[[str, str], None] | None = None,
) -> None:
    """
    Run the PC agent on a task.
    on_update(type, content) is called for each event:
      type = "text"   — agent text output
      type = "tool"   — tool call (name + input)
      type = "result" — tool result
      type = "done"   — agent finished
    """
    def notify(type_: str, content: str) -> None:
        if on_update:
            on_update(type_, content)
        else:
            # CLI fallback
            if type_ == "text":
                print(f"Агент: {content}")
            elif type_ == "tool":
                print(f"🔧 {content}")
            elif type_ == "result":
                print(f"   → {content[:300]}")

    messages = [{"role": "user", "content": task}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=16000,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                notify("text", block.text.strip())

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            notify("done", "")
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    is_dangerous = any(k in str(block.input) for k in DANGER_KEYWORDS)
                    label = "⚠️ " if is_dangerous else ""
                    notify("tool", f"{label}{block.name}: {block.input}")

                    result = _execute_tool(block.name, block.input)
                    notify("result", result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})


# ── CLI mode ──────────────────────────────────────────────────────────────────

def run() -> None:
    print("PC Агент запущен. Введите задачу или 'exit' для выхода.\n")
    while True:
        try:
            task = input("Задача: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        if task.lower() in ("exit", "quit", "q"):
            break
        if task:
            run_agent(task)
            print()
