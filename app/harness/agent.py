"""Model/tool loop shared by the CLI and the GUI."""
from . import tools

MAX_STEPS = 10


def run_agent(client, messages, root, on_text=None, on_tool=None, should_stop=lambda: False):
    """Appends assistant/tool messages until the model answers without tool calls.

    Returns False if the step limit was hit or the run was cancelled.
    """
    for _ in range(MAX_STEPS):
        if should_stop():
            return False
        msg = client.complete(messages, tools.schemas(), on_text=on_text)
        messages.append(msg)
        calls = msg.get("tool_calls")
        if not calls:
            return True
        for c in calls:
            fn = c["function"]
            if on_tool:
                on_tool(fn["name"], fn["arguments"])
            result = tools.execute(root, fn["name"], fn["arguments"])
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    return False
