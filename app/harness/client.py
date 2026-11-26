"""Copilot chat completions client with SSE streaming and tool-call assembly."""
import json
import urllib.request
import urllib.error

from .auth import EDITOR_HEADERS


class ChatClient:
    def __init__(self, session, model="gpt-4o"):
        self.session = session
        self.model = model

    def complete(self, messages, tools=None, on_text=None):
        """Returns the assistant message dict (content and/or tool_calls)."""
        body = {"model": self.model, "messages": messages, "stream": True, "temperature": 0.1}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        token = self.session.token()
        headers = dict(EDITOR_HEADERS)
        headers.update({"Authorization": "Bearer " + token, "Content-Type": "application/json",
                        "Accept": "text/event-stream", "Openai-Intent": "conversation-panel"})
        req = urllib.request.Request(self.session.api_base + "/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            raise RuntimeError("API %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:500]))
        with resp:
            return parse_stream(resp, on_text)


def parse_stream(lines, on_text=None):
    content = []
    calls = {}
    for raw in lines:
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            choices = json.loads(data).get("choices") or []
        except ValueError:
            continue
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            content.append(delta["content"])
            if on_text:
                on_text(delta["content"])
        for tc in delta.get("tool_calls") or []:
            c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function",
                                                      "function": {"name": "", "arguments": ""}})
            if tc.get("id"):
                c["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                c["function"]["name"] += fn["name"]
            if fn.get("arguments"):
                c["function"]["arguments"] += fn["arguments"]
    msg = {"role": "assistant", "content": "".join(content) or None}
    if calls:
        msg["tool_calls"] = [calls[k] for k in sorted(calls)]
    return msg
