"""Simple local routing; this is not GitHub Copilot Fusion."""
import re

AUTO_MODEL = "Automático (GHC)"
DEFAULT_MODEL = "gpt-4o"
COMPLEX_MODEL = "gpt-4.1"
MAX_FALLBACK_MODELS = 8

COMPLEX_TERMS = re.compile(
    r"\b(arquitetura|architecture|refator\w*|refactor\w*|depura\w*|debug\w*|"
    r"investig\w*|migra\w*|integra\w*|implement\w*|algoritm\w*|"
    r"seguran[çc]a|security|concorr\w*|concurr\w*|complex\w*|"
    r"c[oó]digo|source code|stack trace|traceback|exception)\b", re.IGNORECASE)


def _has_images(messages):
    return any(
        message.get("role") in ("user", "assistant") and isinstance(message.get("content"), list) and
        any(isinstance(block, dict) and block.get("type") == "image_url"
            for block in message["content"])
        for message in messages)


def choose_model(messages, available=None):
    """Prefer a multimodal model for images, or a coding model for complex context."""
    parts = []
    image = _has_images(messages)
    for msg in messages[-12:]:
        if msg.get("role") not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
    context = "\n".join(parts)
    complex_task = len(context) > 4000 or bool(COMPLEX_TERMS.search(context))
    if available is None:
        return DEFAULT_MODEL if image or not complex_task else COMPLEX_MODEL
    candidates = available
    if image:
        candidates = [m for m in candidates
                      if isinstance(m.get("capabilities"), dict)
                      and isinstance(m["capabilities"].get("supports"), dict)
                      and m["capabilities"]["supports"].get("vision") is True]
    if not candidates:
        raise ValueError("Não há modelo compatível no catálogo; escolha um modelo manualmente ou atualize.")
    ids = {m["id"] for m in candidates}
    preferred = (["gpt-4o", "gpt-4.1"] if image or not complex_task else
                 ["gpt-5.3-codex", "gpt-4.1", "gpt-4o"])
    return next((model for model in preferred if model in ids), candidates[0]["id"])


def fallback_models(messages, available, excluded=()):
    """Rank fallback candidates without claiming that their versions prove release dates."""
    excluded = set(excluded)
    has_image = _has_images(messages)
    if available is None:
        defaults = [DEFAULT_MODEL] if has_image else [COMPLEX_MODEL, DEFAULT_MODEL]
        return [model for model in defaults if model not in excluded]
    candidates = []
    for model in available:
        model_id = model["id"]
        if model_id in excluded:
            continue
        capabilities = model.get("capabilities")
        supports = capabilities.get("supports") if isinstance(capabilities, dict) else None
        supports = supports if isinstance(supports, dict) else {}
        if has_image and supports.get("vision") is not True:
            continue
        if supports.get("tool_calls") is False:
            continue
        endpoints = model.get("supported_endpoints")
        if isinstance(endpoints, list) and endpoints and "/chat/completions" not in endpoints:
            continue
        if model_id not in candidates:
            candidates.append(model_id)
    def version(model_id):
        match = re.match(r"^gpt-(\d+)(?:\.(\d+))?(?:\.(\d+))?", model_id, re.IGNORECASE)
        return tuple(int(part or 0) for part in match.groups()) if match else (0, 0, 0)
    newest = sorted(candidates, key=version, reverse=True)
    ordered = newest[:3] + [name for name in (COMPLEX_MODEL, DEFAULT_MODEL) if name in candidates] + newest[3:]
    return list(dict.fromkeys(ordered))[:MAX_FALLBACK_MODELS]
