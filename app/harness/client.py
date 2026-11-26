"""Copilot chat completions client with SSE streaming and tool-call assembly."""
import json
import os
import urllib.request
import urllib.error

from .auth import EDITOR_HEADERS
from .resources import installation_dir
from .skills import automatic_skill_context


def limit_context(messages, max_chars):
    if not max_chars:
        return messages
    systems = [m for m in messages if m.get("role") == "system"]
    groups = []
    for msg in messages:
        if msg.get("role") == "system":
            continue
        if msg.get("role") == "user":
            groups.append([])
        if not groups:
            raise ValueError("Histórico inválido: mensagens anteriores ao primeiro usuário.")
        groups[-1].append(msg)
    if not groups:
        raise ValueError("Não há mensagem de usuário para enviar.")
    selected = list(systems)
    newest = groups[-1]
    if len(json.dumps(selected + newest, ensure_ascii=False)) > max_chars:
        raise ValueError("A conversa atual excede o limite de contexto; aumente-o nas configurações.")
    chosen = [newest]
    for group in reversed(groups[:-1]):
        trial = [group] + chosen
        if len(json.dumps(selected + [m for g in trial for m in g], ensure_ascii=False)) > max_chars:
            break
        chosen = trial
    return selected + [m for group in chosen for m in group]


class ChatClient:
    def __init__(self, session, model="gpt-4o"):
        self.session = session
        self.model = model
        self.max_context_chars = 0
        self.files_dir = ""
        self.skill_instructions = ""
        self.canvas_instructions = ""
        self.fallback_models = []
        self.on_model_change = None
        self.on_model_unavailable = None
        self.should_retry_model = lambda: True

    def list_models(self):
        token = self.session.token()
        headers = dict(EDITOR_HEADERS, Authorization="Bearer " + token, Accept="application/json")
        req = urllib.request.Request(self.session.api_base + "/models", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError("Não foi possível consultar modelos (%s)." % e.code)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("Resposta inválida ao consultar modelos.")
        models = []
        seen = set()
        for item in data["data"]:
            if not isinstance(item, dict):
                raise ValueError("Catálogo de modelos contém um item inválido.")
            model_id = item.get("id")
            capabilities = item.get("capabilities") or {}
            if not isinstance(capabilities, dict):
                raise ValueError("Capacidades de modelo inválidas.")
            if capabilities.get("type") not in (None, "chat"):
                continue
            if not isinstance(model_id, str) or not model_id:
                raise ValueError("Catálogo contém um modelo sem identificador.")
            policy = item.get("policy")
            endpoints = item.get("supported_endpoints")
            supports = capabilities.get("supports")
            if (item.get("model_picker_enabled") is False or
                    (isinstance(policy, dict) and policy.get("state") == "disabled") or
                    not isinstance(endpoints, list) or "/chat/completions" not in endpoints or
                    (isinstance(supports, dict) and supports.get("tool_calls") is False)):
                continue
            if model_id in seen:
                continue
            seen.add(model_id)
            name = item.get("name")
            model = {"id": model_id, "name": name if isinstance(name, str) and name else model_id,
                     "capabilities": capabilities}
            model["supported_endpoints"] = endpoints
            models.append(model)
        if not models:
            raise ValueError("A conta não retornou modelos compatíveis com a API de chat do GHC.")
        return models

    def complete(self, messages, tools=None, on_text=None):
        """Returns the assistant message dict (content and/or tool_calls)."""
        request_messages = [{key: value for key, value in message.items()
                             if key not in ("_ghc_model", "_ghc_auto", "_ghc_fallbacks")} for message in messages]
        if self.files_dir:
            instruction = ("\n\nA pasta padrão de arquivos produzidos e downloads do GHC é: " +
                           self.files_dir + ". Use-a quando o usuário solicitar esses arquivos, "
                           "salvo instrução diferente.")
            if request_messages and request_messages[0].get("role") == "system":
                first = dict(request_messages[0])
                first["content"] += instruction
                request_messages[0] = first
            else:
                request_messages.insert(0, {"role": "system", "content": instruction.strip()})
        skills_dir = os.path.join(installation_dir(), "skill")
        skill_location = "A pasta de skills do GHC é: " + skills_dir
        extra = "\n\n".join(value for value in
                            (self.canvas_instructions, self.skill_instructions, skill_location,
                             automatic_skill_context(skills_dir)) if value)
        if extra:
            if request_messages and request_messages[0].get("role") == "system":
                first = dict(request_messages[0])
                first["content"] += "\n\n" + extra
                request_messages[0] = first
            else:
                request_messages.insert(0, {"role": "system", "content": extra})
        body = {"model": self.model, "messages": limit_context(request_messages, self.max_context_chars),
                "stream": True, "temperature": 0.1}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        token = self.session.token()
        headers = dict(EDITOR_HEADERS)
        headers.update({"Authorization": "Bearer " + token, "Content-Type": "application/json",
                        "Accept": "text/event-stream", "Openai-Intent": "conversation-panel"})
        candidates = list(dict.fromkeys([self.model] + self.fallback_models))
        attempted = []
        for index, model in enumerate(candidates):
            body["model"] = model
            req = urllib.request.Request(self.session.api_base + "/chat/completions",
                                         data=json.dumps(body).encode("utf-8"), headers=headers)
            attempted.append(model)
            try:
                resp = urllib.request.urlopen(req, timeout=120)
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", "replace")
                finally:
                    e.close()
                try:
                    error = json.loads(detail).get("error")
                    code = error.get("code") if isinstance(error, dict) else None
                except (ValueError, AttributeError):
                    code = None
                model_error = e.code in (400, 403, 404) and code in {
                    "unsupported_api_for_model", "model_not_found", "model_not_available",
                    "model_not_available_for_integrator", "model_not_supported", "unsupported_model"}
                if model_error and self.on_model_unavailable:
                    self.on_model_unavailable(model)
                if model_error and index + 1 < len(candidates) and self.should_retry_model():
                    next_model = candidates[index + 1]
                    self.model = next_model
                    if self.on_model_change:
                        self.on_model_change(model, next_model)
                    continue
                tried = " Modelos tentados: %s." % ", ".join(attempted) if len(attempted) > 1 else ""
                raise RuntimeError("API %s: %s%s" % (e.code, detail[:500], tried)) from e
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
