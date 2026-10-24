"""Split optional `<think>` tags out of streamed text.

Qwen3 can emit thinking either as a separate field or as tags inside the
answer. When thinking mode is off, tagged text is discarded instead of shown.
"""


class ThinkSplitter:
    def __init__(self) -> None:
        self._pending = ""
        self._inside = False

    def feed(self, text: str) -> tuple[str, str]:
        self._pending += text
        visible: list[str] = []
        thinking: list[str] = []
        while self._pending:
            if self._inside:
                end = self._pending.lower().find("</think>")
                if end == -1:
                    keep = _partial_tag(self._pending, "</think>")
                    thinking.append(self._pending[:-keep] if keep else self._pending)
                    self._pending = self._pending[-keep:] if keep else ""
                    break
                thinking.append(self._pending[:end])
                self._pending = self._pending[end + len("</think>") :]
                self._inside = False
                continue
            start = self._pending.lower().find("<think>")
            if start == -1:
                keep = _partial_tag(self._pending, "<think>")
                visible.append(self._pending[:-keep] if keep else self._pending)
                self._pending = self._pending[-keep:] if keep else ""
                break
            visible.append(self._pending[:start])
            self._pending = self._pending[start + len("<think>") :]
            self._inside = True
        return "".join(visible), "".join(thinking)

    def flush(self) -> tuple[str, str]:
        leftover = self._pending
        self._pending = ""
        if self._inside:
            return "", leftover
        return leftover, ""


def _partial_tag(text: str, tag: str) -> int:
    lowered = text.lower()
    for size in range(min(len(lowered), len(tag) - 1), 0, -1):
        if tag.startswith(lowered[-size:]):
            return size
    return 0
