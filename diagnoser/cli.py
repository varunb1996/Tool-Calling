"""
Talk to the diagnoser interactively.

Run: python -m diagnoser.cli
Type 'quit' to exit.
"""

from diagnoser.agent import chat


def main():
    print("Diagnoser ready. Describe the AI idea or workflow you're stuck on.")
    print("(type 'quit' to exit)\n")
    messages = []
    while True:
        user_input = input("you> ").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        messages.append({"role": "user", "content": user_input})
        reply, full_messages = chat(messages)
        print(f"\ndiagnoser> {reply}\n")
        # Keep just the conversational turns for the next call - the
        # system prompt gets re-added by chat() every time, and tool-call
        # bookkeeping messages are internal to a single chat() invocation.
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
