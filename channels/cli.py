from agent import stream_response


def run() -> None:
    """Interactive CLI channel."""
    messages: list[dict] = []
    print("Assistant ready. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        print("Assistant: ", end="", flush=True)
        response_text = ""
        for chunk in stream_response(messages):
            print(chunk, end="", flush=True)
            response_text += chunk
        print("\n")

        messages.append({"role": "assistant", "content": response_text})
