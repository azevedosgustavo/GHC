"""Check official GitHub releases and download, never execute, their installer."""
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

API = "https://api.github.com/repos/azevedosgustavo/GHC/releases/latest"
MAX_RELEASE_BYTES = 2 * 1024 * 1024
MAX_SETUP_BYTES = 500 * 1024 * 1024


def version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("Versão não reconhecida: %s" % value)
    return tuple(int(part) for part in match.groups())


def check_latest():
    request = urllib.request.Request(API, headers={"User-Agent": "GHC-updater",
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_RELEASE_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("Nenhuma release pública encontrada ou repositório inacessível (HTTP 404).") from e
        raise
    if len(data) > MAX_RELEASE_BYTES:
        raise ValueError("Resposta de releases excede o limite.")
    release = json.loads(data.decode("utf-8"))
    if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
        raise ValueError("Resposta de release inválida.")
    tag = release["tag_name"]
    if version(tag) <= version(__version__):
        return None
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("A release não contém uma lista de arquivos válida.")
    expected = "https://github.com/azevedosgustavo/GHC/releases/download/%s/GHC-Setup.exe" % tag
    for asset in assets:
        if (isinstance(asset, dict) and asset.get("name") == "GHC-Setup.exe" and
                asset.get("browser_download_url") == expected):
            return {"version": tag, "url": expected}
    raise ValueError("A release %s não possui GHC-Setup.exe no repositório oficial." % tag)


def _allowed_download_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        return (p.scheme == "https" and p.hostname in ("github.com", "release-assets.githubusercontent.com",
                "objects.githubusercontent.com") and p.username is None and p.password is None and
                p.port in (None, 443))
    except ValueError:
        return False


class _DownloadRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_download_url(newurl):
            raise ValueError("Redirecionamento de atualização não permitido: " + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_setup(url, destination):
    parsed = urllib.parse.urlsplit(url)
    if (not _allowed_download_url(url) or parsed.hostname != "github.com" or parsed.query or parsed.fragment or
            not re.fullmatch(r"/azevedosgustavo/GHC/releases/download/v?\d+\.\d+\.\d+/GHC-Setup\.exe",
                             parsed.path)):
        raise ValueError("Endereço do instalador não é do GitHub oficial.")
    if not os.path.isabs(destination):
        raise ValueError("Informe um destino absoluto para o instalador.")
    fd, temporary = tempfile.mkstemp(prefix=".ghc-download-", suffix=".tmp",
                                      dir=os.path.dirname(destination))
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "GHC-updater"})
        with os.fdopen(fd, "wb") as target:
            fd = None
            with urllib.request.build_opener(_DownloadRedirect()).open(request, timeout=60) as response:
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        expected_size = int(length)
                    except ValueError as e:
                        raise ValueError("Tamanho do instalador inválido.") from e
                    if expected_size <= 0 or expected_size > MAX_SETUP_BYTES:
                        raise ValueError("Tamanho do instalador fora do limite permitido.")
                else:
                    expected_size = None
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_SETUP_BYTES:
                        raise ValueError("Instalador excede 500 MiB.")
                    target.write(chunk)
                if total == 0:
                    raise ValueError("O instalador baixado está vazio.")
                if expected_size is not None and total != expected_size:
                    raise ValueError("Download incompleto: tamanho recebido difere do esperado.")
        os.replace(temporary, destination)
    except Exception as e:
        if fd is not None:
            os.close(fd)
        try:
            os.remove(temporary)
        except OSError as cleanup:
            raise OSError("%s; não foi possível limpar %s: %s" % (e, temporary, cleanup)) from e
        raise
