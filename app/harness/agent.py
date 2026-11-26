"""Model/tool loop shared by the CLI and the GUI."""
from . import tools

MAX_STEPS = 10


def run_agent(client, messages, root, on_text=None, on_tool=None, should_stop=lambda: False,
              mode="chat", confirm=None):
    """Appends assistant/tool messages until the model answers without tool calls.

    Returns False if the step limit was hit or the run was cancelled.
    """
    if mode not in ("chat", "manual", "auto"):
        raise ValueError("Modo de permissao invalido: %s" % mode)
    for _ in range(MAX_STEPS):
        if should_stop():
            return False
        msg = client.complete(messages, tools.schemas(mode != "chat"), on_text=on_text)
        if should_stop():
            return False
        messages.append(msg)
        calls = msg.get("tool_calls")
        if not calls:
            return True
        for c in calls:
            if should_stop():
                return False
            fn = c["function"]
            if on_tool:
                on_tool(fn["name"], fn["arguments"])
            allowed = mode == "auto"
            if mode == "manual" and tools.is_mutating(fn["name"]):
                allowed = bool(confirm and confirm(fn["name"], fn["arguments"]))
            if should_stop():
                return False
            result = tools.execute(root, fn["name"], fn["arguments"], allow_mutating=allowed)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    return False
