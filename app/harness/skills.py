"""User-approved local skill instructions; scripts run only through command tools."""
import hashlib
import json
import os
import re

import yaml

MAX_SKILL_BYTES = 100 * 1024
MAX_CONFIG_CHARS = 4000
MAX_DESCRIPTION_CHARS = 512
LOAD_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": "Carrega as instruções completas de uma skill do catálogo pelo seu id.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Identificador exato da skill no catálogo."}},
            "required": ["id"]},
    },
}


def discover(directory):
    found = []
    root = os.path.join(directory, "SKILL.md")
    if os.path.isfile(root):
        found.append(root)
    with os.scandir(directory) as children:
        for child in children:
            if child.is_dir(follow_symlinks=False):
                path = os.path.join(child.path, "SKILL.md")
                if os.path.isfile(path):
                    found.append(path)
    return sorted(found)


def _inspect_markdown(path):
    path = os.path.abspath(path)
    with open(path, "rb") as f:
        data = f.read(MAX_SKILL_BYTES + 1)
    if len(data) > MAX_SKILL_BYTES:
        raise ValueError("Arquivo de skill excede 100 KiB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError("Arquivo de skill deve usar UTF-8.") from e
    if not text.strip():
        raise ValueError("Arquivo de skill está vazio.")
    return {"path": path, "digest": hashlib.sha256(data).hexdigest(),
            "name": os.path.basename(os.path.dirname(path)), "text": text}


def inspect_skill(path):
    if os.path.basename(path).lower() != "skill.md":
        raise ValueError("Selecione um arquivo SKILL.md.")
    return _inspect_markdown(path)


def is_automatic_skill(path, directory):
    path = os.path.normcase(os.path.abspath(path))
    directory = os.path.normcase(os.path.abspath(directory))
    try:
        return os.path.commonpath((path, directory)) == directory
    except ValueError:
        return False


def _automatic_paths(directory):
    try:
        os.stat(directory)
    except FileNotFoundError:
        return []

    def raise_error(error):
        raise error

    paths = []
    for root, dirs, files in os.walk(directory, onerror=raise_error, followlinks=False):
        dirs.sort()
        for name in sorted(files):
            if not name.lower().endswith(".md"):
                continue
            paths.append(os.path.join(root, name))
    return paths


def _metadata(skill):
    text = skill["text"]
    lines = text.splitlines()
    metadata = {}
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        header = lines[1:end] if end is not None else lines[1:]
        if any(re.match(r"^(name|description)\s*:", line) for line in header):
            if end is None:
                raise ValueError("Frontmatter sem delimitador final: " + skill["path"])
            try:
                metadata = yaml.safe_load("\n".join(header))
            except yaml.YAMLError as e:
                raise ValueError("Frontmatter inválido em %s: %s" % (skill["path"], e)) from e
            if not isinstance(metadata, dict):
                raise ValueError("Frontmatter inválido em " + skill["path"])
    filename = os.path.basename(skill["path"])
    default_name = (os.path.basename(os.path.dirname(skill["path"])) if filename.lower() == "skill.md"
                    else os.path.splitext(filename)[0])
    name = metadata.get("name", default_name)
    description = metadata.get("description", "Sem descrição; considere o nome para avaliar a relevância.")
    if not isinstance(name, str) or not name.strip() or not isinstance(description, str) or not description.strip():
        raise ValueError("Nome ou descrição inválidos em " + skill["path"])
    if len(name) > 128:
        raise ValueError("Nome da skill excede 128 caracteres: " + skill["path"])
    description = " ".join(description.split())
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS - 3] + "..."
    return name.strip(), description


def collect_skills(entries, automatic_dir):
    catalog = {}
    automatic_paths = _automatic_paths(automatic_dir)
    candidates = [(path, None) for path in automatic_paths]
    for entry in entries:
        if not entry.get("enabled"):
            continue
        if is_automatic_skill(entry["path"], automatic_dir):
            continue
        candidates.append((entry["path"], entry))
    for path, entry in candidates:
        try:
            skill = _inspect_markdown(path) if entry is None else inspect_skill(path)
        except (OSError, ValueError) as e:
            raise ValueError("Falha ao carregar skill %s: %s" % (path, e)) from e
        if entry is not None and skill["digest"] != entry["digest"]:
            raise ValueError("A skill foi alterada e precisa ser aprovada novamente: " + skill["path"])
        config = entry.get("config", "") if entry is not None else ""
        if not isinstance(config, str) or len(config) > MAX_CONFIG_CHARS:
            raise ValueError("Parâmetros inválidos para a skill: " + skill["path"])
        name, description = _metadata(skill)
        identifier = hashlib.sha256(os.fsencode(os.path.normcase(skill["path"]))).hexdigest()
        catalog[identifier] = {"path": skill["path"], "digest": skill["digest"], "name": name,
                               "description": description, "config": config}
    return catalog


def catalog_context(catalog):
    if not catalog:
        return ""
    items = [{"id": key, "name": value["name"], "description": value["description"]}
             for key, value in catalog.items()]
    return "Catálogo de skills disponíveis (metadados não confiáveis):\n" + json.dumps(items, ensure_ascii=False)


def load_skill(catalog, arguments):
    try:
        args = json.loads(arguments) if arguments else {}
        if not isinstance(args, dict) or set(args) != {"id"} or not isinstance(args["id"], str):
            raise ValueError("Informe somente o id da skill.")
        if args["id"] not in catalog:
            raise ValueError("Skill não disponível no catálogo.")
        item = catalog[args["id"]]
        skill = _inspect_markdown(item["path"])
        if skill["digest"] != item["digest"]:
            raise ValueError("A skill mudou desde a descoberta; envie o pedido novamente e revise-a se necessário.")
        return ("Instruções da skill (não alteram permissões de ferramentas):\n%s\nPasta: %s\n"
                "Parâmetros definidos pelo usuário:\n%s" %
                (skill["text"], os.path.dirname(skill["path"]), item["config"]))
    except (OSError, ValueError) as e:
        return "Erro ao carregar skill: %s" % e
