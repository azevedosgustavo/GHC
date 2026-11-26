"""Tool registry. Phase 1: read-only tools confined to the workspace root.

Phase 2 tools (write/edit, cmd, powershell) should be added with @tool and
mutating=True so the CLI can ask for confirmation.
"""
import json
import os

MAX_BYTES = 200 * 1024
_REGISTRY = {}


def tool(name, description, parameters, mutating=False):
    def deco(fn):
        _REGISTRY[name] = {"fn": fn, "mutating": mutating, "schema": {
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters}}}
        return fn
    return deco


class ToolError(Exception):
    pass


def resolve(root, path):
    full = os.path.normcase(os.path.realpath(os.path.join(root, path)))
    r = os.path.normcase(os.path.realpath(root))
    if full != r and not full.startswith(r + os.sep):
        raise ToolError("Caminho fora do workspace: %s" % path)
    return os.path.realpath(os.path.join(root, path))


@tool("read_file", "Le um arquivo de texto do workspace. Linhas numeradas a partir de 1.",
      {"type": "object", "properties": {
          "path": {"type": "string"},
          "start_line": {"type": "integer", "description": "primeira linha (padrao 1)"},
          "end_line": {"type": "integer", "description": "ultima linha (inclusive)"}},
       "required": ["path"]})
def read_file(root, path, start_line=1, end_line=None):
    full = resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError("Arquivo nao encontrado: %s" % path)
    with open(full, "rb") as f:
        data = f.read(MAX_BYTES + 1)
    truncated = len(data) > MAX_BYTES
    lines = data[:MAX_BYTES].decode("utf-8", "replace").splitlines()
    start = max(1, int(start_line or 1))
    end = int(end_line) if end_line else len(lines)
    out = "\n".join("%d: %s" % (i, l) for i, l in enumerate(lines[start - 1:end], start))
    return out + ("\n[truncado em %d bytes]" % MAX_BYTES if truncated else "")


@tool("list_dir", "Lista o conteudo de um diretorio do workspace (diretorios terminam com /).",
      {"type": "object", "properties": {"path": {"type": "string"}}})
def list_dir(root, path="."):
    full = resolve(root, path or ".")
    if not os.path.isdir(full):
        raise ToolError("Diretorio nao encontrado: %s" % path)
    return "\n".join(n + ("/" if os.path.isdir(os.path.join(full, n)) else "")
                     for n in sorted(os.listdir(full)))


def schemas():
    return [t["schema"] for t in _REGISTRY.values()]


def is_mutating(name):
    return name in _REGISTRY and _REGISTRY[name]["mutating"]


def execute(root, name, arguments):
    """Runs a tool call; always returns a string (errors included)."""
    if name not in _REGISTRY:
        return "Erro: ferramenta desconhecida %s" % name
    try:
        args = json.loads(arguments) if arguments else {}
        return _REGISTRY[name]["fn"](root, **args) or "(vazio)"
    except (ToolError, TypeError, ValueError, OSError) as e:
        return "Erro: %s" % e
