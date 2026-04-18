import subprocess
import os
import anthropic

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a helpful PC agent. You can perform multi-step tasks on the user's computer.
Use tools step by step to complete tasks. Think before each action.
Always explain what you are doing and why. Be careful with destructive operations."""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command and return the output. Use for any system operations.",
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
                "path": {"type": "string", "description": "Absolute or relative file path"},
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
                "path": {"type": "string", "description": "Directory path (default: current dir)"},
            },
            "required": [],
        },
    },
]

DANGER_KEYWORDS = ("rm -rf", "format", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "del /f")


def _confirm(action: str, detail: str) -> bool:
    print(f"\n⚡ {action}: {detail}")
    answer = input("   Разрешить? [y/N]: ").strip().lower()
    return answer == "y"


def _run_tool(name: str, inputs: dict) -> str:
    if name == "bash":
        cmd = inputs["command"]
        if any(kw in cmd for kw in DANGER_KEYWORDS):
            if not _confirm("ОПАСНАЯ команда", cmd):
                return "Отменено пользователем."
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            return output.strip() or "(нет вывода)"
        except subprocess.TimeoutExpired:
            return "Ошибка: команда выполнялась дольше 30 секунд."
        except Exception as e:
            return f"Ошибка: {e}"

    elif name == "read_file":
        try:
            with open(inputs["path"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Ошибка чтения: {e}"

    elif name == "write_file":
        path = inputs["path"]
        if not _confirm("Запись файла", path):
            return "Отменено пользователем."
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(inputs["content"])
            return f"Файл записан: {path}"
        except Exception as e:
            return f"Ошибка записи: {e}"

    elif name == "list_dir":
        path = inputs.get("path", ".")
        try:
            entries = os.listdir(path)
            return "\n".join(sorted(entries)) or "(пусто)"
        except Exception as e:
            return f"Ошибка: {e}"

    return f"Неизвестный инструмент: {name}"


def run_task(task: str) -> None:
    messages = [{"role": "user", "content": task}]
    print()

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

        # Print text blocks as they appear
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"Агент: {block.text}\n")

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"🔧 Инструмент: {block.name}({block.input})")
                    result = _run_tool(block.name, block.input)
                    print(f"   → {result[:200]}{'...' if len(result) > 200 else ''}\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})


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
        if not task:
            continue
        run_task(task)
