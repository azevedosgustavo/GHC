"""Model/tool loop shared by the CLI and the GUI."""
from . import tools
from .skills import LOAD_SKILL_SCHEMA, load_skill

MAX_STEPS = 10


def run_agent(client, messages, root, on_text=None, on_tool=None, should_stop=lambda: False,
              mode="chat", confirm=None):
    """Appends assistant/tool messages until the model answers without tool calls.

    Returns False if the step limit was hit or the run was cancelled.
    """
    if mode not in ("chat", "manual", "auto"):
        raise ValueError("Modo de permissao invalido: %s" % mode)
    catalog = getattr(client, "skill_catalog", None)
    if not isinstance(catalog, dict):
        catalog = {}
    loaded_results = []
    try:
        for _ in range(MAX_STEPS):
            if should_stop():
                return False
            schemas = tools.schemas(mode != "chat")
            if catalog:
                schemas.append(LOAD_SKILL_SCHEMA)
            msg = client.complete(messages, schemas, on_text=on_text)
            if should_stop():
                return False
            messages.append(msg)
            calls = msg.get("tool_calls")
            if not calls:
                return True
            loading = any(c["function"]["name"] == "load_skill" for c in calls)
            for c in calls:
                if should_stop():
                    return False
                fn = c["function"]
                name = fn["name"]
                if on_tool and name != "load_skill":
                    on_tool(name, fn["arguments"])
                if name == "load_skill":
                    result = load_skill(catalog, fn["arguments"])
                elif loading and tools.is_mutating(name):
                    result = "Erro: aguarde o carregamento da skill antes de executar comandos."
                else:
                    allowed = mode == "auto"
                    if mode == "manual" and tools.is_mutating(name):
                        allowed = bool(confirm and confirm(name, fn["arguments"]))
                    if should_stop():
                        return False
                    result = tools.execute(root, name, fn["arguments"], allow_mutating=allowed)
                response = {"role": "tool", "tool_call_id": c["id"], "content": result}
                messages.append(response)
                if name == "load_skill" and not result.startswith("Erro ao carregar skill:"):
                    loaded_results.append(response)
        return False
    finally:
        for response in loaded_results:
            response["content"] = "Skill carregada no turno anterior; consulte o catálogo para carregá-la novamente."
