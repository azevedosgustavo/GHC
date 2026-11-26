"""Copies and removes only GHC-managed attachment snapshots."""
import os
import re
import uuid


def save_files(root, chat_id, message_index, files):
    if not files:
        return []
    if not re.fullmatch(r"[A-Za-z0-9_-]+", chat_id):
        raise ValueError("Identificador de conversa inválido.")
    root = os.path.realpath(root)
    directory = os.path.join(root, "attachments", chat_id)
    os.makedirs(directory, exist_ok=True)
    if os.path.normcase(os.path.realpath(directory)) != os.path.normcase(directory):
        raise ValueError("A pasta de anexos não pode conter links.")
    saved = []
    try:
        for item in files:
            name = uuid.uuid4().hex + "_" + os.path.basename(item["name"])
            path = os.path.join(directory, name)
            with open(path, "xb") as f:
                saved.append({"root": root, "chat": chat_id, "name": name,
                              "message": message_index, "block": item["block"]})
                f.write(item["data"])
    except OSError as e:
        cleanup_errors = []
        for ref in saved:
            try:
                os.remove(os.path.join(directory, ref["name"]))
            except OSError as cleanup:
                cleanup_errors.append(str(cleanup))
        if cleanup_errors:
            raise OSError("%s; falha ao limpar cópias parciais: %s" % (e, "; ".join(cleanup_errors))) from e
        raise
    return saved


def remove_files(refs):
    errors = []
    for ref in refs:
        root, chat, name = ref["root"], ref["chat"], ref["name"]
        if (not os.path.isabs(root) or os.path.basename(name) != name or
                not re.fullmatch(r"[A-Za-z0-9_-]+", chat) or
                not re.match(r"^[0-9a-f]{32}_", name)):
            errors.append("Referência de anexo inválida.")
            continue
        directory = os.path.join(root, "attachments", chat)
        path = os.path.join(directory, name)
        if os.path.normcase(os.path.realpath(directory)) != os.path.normcase(directory):
            errors.append("Pasta de anexos contém um link: %s" % directory)
            continue
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        except OSError as e:
            errors.append("%s: %s" % (path, e))
    return errors
