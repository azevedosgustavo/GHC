"""GitHub auth: device flow + Copilot token exchange (stdlib only, Python 3.8)."""
import json
import os
import time
import urllib.request
import urllib.error

CLIENT_ID = "Iv1.b507a08c87ecfe98"  # public GitHub Copilot editor client id
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".copilot-harness")
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")

EDITOR_HEADERS = {
    "Editor-Version": "vscode/1.95.0",
    "Editor-Plugin-Version": "copilot-chat/0.22.0",
    "Copilot-Integration-Id": "vscode-chat",
    "User-Agent": "GitHubCopilotChat/0.22.0",
}


def _post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": EDITOR_HEADERS["User-Agent"]},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


class AuthError(RuntimeError):
    """The stored GitHub token was rejected (revoked/invalid); login is required again."""


def device_start():
    """Requests a device code: dict with user_code, verification_uri, device_code, ..."""
    return _post_json("https://github.com/login/device/code",
                      {"client_id": CLIENT_ID, "scope": "read:user"})


def device_poll(d, cancelled=lambda: False):
    """Blocks until the user authorizes; saves and returns the GitHub token."""
    interval = int(d.get("interval", 5))
    deadline = time.time() + int(d.get("expires_in", 900))
    while time.time() < deadline:
        for _ in range(interval * 2):
            if cancelled():
                raise RuntimeError("Login cancelado")
            time.sleep(0.5)
        r = _post_json("https://github.com/login/oauth/access_token", {
            "client_id": CLIENT_ID,
            "device_code": d["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        if "access_token" in r:
            save_token(r["access_token"])
            return r["access_token"]
        err = r.get("error")
        if err == "slow_down":
            interval += 5
        elif err != "authorization_pending":
            raise RuntimeError("Falha no login: %s" % (r.get("error_description") or err))
    raise RuntimeError("Codigo expirado")


def device_login(out=print):
    """Terminal flow."""
    d = device_start()
    out("Abra %s e digite o codigo: %s" % (d["verification_uri"], d["user_code"]))
    return device_poll(d)


def logout():
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass


def save_token(token):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = TOKEN_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"github_token": token}, f)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, TOKEN_FILE)


def load_github_token():
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f).get("github_token")
    except (IOError, ValueError):
        return None


class CopilotSession:
    """Caches the short-lived Copilot API token."""

    def __init__(self, github_token):
        self.github_token = github_token
        self._token = None
        self._expires = 0
        self.api_base = "https://api.githubcopilot.com"

    def token(self):
        if self._token and time.time() < self._expires - 60:
            return self._token
        req = urllib.request.Request(
            "https://api.github.com/copilot_internal/v2/token",
            headers=dict(EDITOR_HEADERS, Authorization="token " + self.github_token,
                         Accept="application/json"),
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AuthError("Sessao do GitHub invalida.")
            raise RuntimeError("Token Copilot recusado (%s). Rode --login; precisa de assinatura Copilot." % e.code)
        self._token = data["token"]
        self._expires = data.get("expires_at", time.time() + 600)
        self.api_base = data.get("endpoints", {}).get("api", self.api_base)
        return self._token
