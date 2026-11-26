"""Tool registry and execution of workspace reads and approved commands."""
import json
import os
import subprocess
import sys
import tempfile

MAX_BYTES = 200 * 1024
COMMAND_TIMEOUT = 120
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


@tool("read_file", "Le um arquivo de texto somente dentro do workspace. Linhas numeradas a partir de 1.",
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


@tool("list_dir", "Lista um diretorio somente dentro do workspace (diretorios terminam com /).",
      {"type": "object", "properties": {"path": {"type": "string"}}})
def list_dir(root, path="."):
    full = resolve(root, path or ".")
    if not os.path.isdir(full):
        raise ToolError("Diretorio nao encontrado: %s" % path)
    return "\n".join(n + ("/" if os.path.isdir(os.path.join(full, n)) else "")
                     for n in sorted(os.listdir(full)))


def _decode_output(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("oem" if sys.platform == "win32" else "utf-8", "replace")


def python_executable():
    if getattr(sys, "frozen", False):
        executable = os.path.join(os.path.dirname(sys.executable), "python-runtime", "python.exe")
        if not os.path.isfile(executable):
            raise ToolError("Python do GHC não encontrado: %s" % executable)
        return executable
    return sys.executable


def _run_process(root, argv, input_data=None, env=None):
    if sys.platform != "win32":
        raise ToolError("A execucao de comandos esta disponivel somente no Windows.")
    with tempfile.TemporaryFile() as output:
        try:
            options = {"input": input_data} if input_data is not None else {"stdin": subprocess.DEVNULL}
            result = subprocess.run(argv, cwd=root, env=env, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=COMMAND_TIMEOUT,
                                    creationflags=0x08000000, **options)
        except subprocess.TimeoutExpired:
            raise ToolError("Comando excedeu o limite de %d segundos." % COMMAND_TIMEOUT)
        output.seek(0)
        data = output.read(MAX_BYTES + 1)
    text = _decode_output(data[:MAX_BYTES])
    if len(data) > MAX_BYTES:
        text += "\n[saida truncada em %d bytes]" % MAX_BYTES
    return "Codigo de saida: %d\n%s" % (result.returncode, text)


def _run_command(root, executable, arguments, command):
    if not isinstance(command, str) or not command.strip():
        raise ToolError("Informe um comando nao vazio.")
    return _run_process(root, [executable] + arguments + [command])


def _python_env():
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@tool("run_python", "Executa codigo Python, inclusive criar arquivos solicitados, com permissoes do usuario e sem isolamento.",
      {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
      mutating=True)
def run_python(root, code):
    if not isinstance(code, str) or not code.strip():
        raise ToolError("Informe codigo Python nao vazio.")
    return _run_process(root, [python_executable(), "-u", "-"], code.encode("utf-8"), _python_env())


@tool("run_python_script", "Executa um arquivo Python pelo runtime do GHC, sem isolamento.",
      {"type": "object", "properties": {
          "path": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}},
       "required": ["path"]}, mutating=True)
def run_python_script(root, path, args=None):
    if not isinstance(path, str) or not path.strip():
        raise ToolError("Informe o caminho do script Python.")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ToolError("Argumentos do script devem ser uma lista de textos.")
    full = os.path.abspath(os.path.join(root, path))
    if not os.path.isfile(full):
        raise ToolError("Script nao encontrado: %s" % full)
    return _run_process(root, [python_executable(), "-u", full] + args, env=_python_env())


COMMAND_PARAMS = {"type": "object", "properties": {"command": {"type": "string"}},
                  "required": ["command"]}


@tool("run_cmd", "Executa um comando cmd no computador Windows, com as permissoes do usuario.",
      COMMAND_PARAMS, mutating=True)
def run_cmd(root, command):
    return _run_command(root, os.environ.get("COMSPEC", "cmd.exe"), ["/d", "/s", "/c"], command)


@tool("run_powershell", "Executa um comando PowerShell no computador Windows, com as permissoes do usuario.",
      COMMAND_PARAMS, mutating=True)
def run_powershell(root, command):
    return _run_command(root, "powershell.exe", ["-NoProfile", "-NonInteractive", "-Command"], command)


def schemas(allow_mutating=False):
    return [t["schema"] for t in _REGISTRY.values() if allow_mutating or not t["mutating"]]


def is_mutating(name):
    return name in _REGISTRY and _REGISTRY[name]["mutating"]


def execute(root, name, arguments, allow_mutating=False):
    """Runs a tool call; always returns a string (errors included)."""
    if name not in _REGISTRY:
        return "Erro: ferramenta desconhecida %s" % name
    if is_mutating(name) and not allow_mutating:
        return "Erro: ferramenta bloqueada pelo modo de permissao."
    try:
        args = json.loads(arguments) if arguments else {}
        if not isinstance(args, dict):
            raise ToolError("Os argumentos devem ser um objeto JSON.")
        return _REGISTRY[name]["fn"](root, **args) or "(vazio)"
    except (ToolError, TypeError, ValueError, OSError) as e:
        return "Erro: %s" % e
