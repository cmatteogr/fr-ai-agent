"""Console adapter for MessagingPort — used by the CLI simulator and tests."""


class ConsoleMessenger:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, *, to: str, text: str) -> None:
        self.sent.append((to, text))
        print(f"\n[agent -> {to}]\n{text}\n")
