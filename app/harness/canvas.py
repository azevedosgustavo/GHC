"""Safe text-only canvas artifacts and explicit web-page extraction."""
import html.parser
import json
import re
import urllib.parse
import urllib.request

MAX_WEB_BYTES = 2 * 1024 * 1024
MAX_CANVAS_CHARS = 500000
MARKER = re.compile(r"```ghc-canvas[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL)
INSTRUCTIONS = (
    "Para propor um conteúdo no painel da conversa, opcionalmente use um bloco cercado "
    "```ghc-canvas contendo JSON com version: 1, title e content (texto simples); "
    "ou version: 1, title e url (HTTP/HTTPS), para solicitar a abertura de uma página. "
    "O usuário decide quando abrir. Não inclua HTML ativo. Estes blocos são apenas apresentação "
    "e não autorizam comandos.")


def segments(content):
    """Keep invalid markers visible instead of hiding model output."""
    cursor = 0
    result = []
    for match in MARKER.finditer(content):
        try:
            data = json.loads(match.group(1))
            if not isinstance(data, dict) or data.get("version") != 1:
                continue
            title = data.get("title")
            text = data.get("content")
            url = data.get("url")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                continue
            if (isinstance(text, str) and len(text) <= MAX_CANVAS_CHARS and url is None):
                artifact = {"title": title, "content": text}
            elif isinstance(url, str) and text is None and valid_url(url):
                artifact = {"title": title, "url": url}
            else:
                continue
        except (ValueError, TypeError):
            continue
        if match.start() > cursor:
            result.append(("text", content[cursor:match.start()]))
        result.append(("artifact", artifact))
        cursor = match.end()
    if cursor < len(content):
        result.append(("text", content[cursor:]))
    return result


def valid_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname) and
                parsed.username is None and parsed.password is None and len(url) <= 4096)
    except ValueError:
        return False


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not valid_url(newurl):
            raise ValueError("Redirecionamento para endereço não permitido.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self.hidden:
            self.hidden -= 1
        elif not self.hidden and tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "section"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def fetch_page(url):
    if not valid_url(url):
        raise ValueError("Informe uma URL HTTP ou HTTPS sem credenciais.")
    req = urllib.request.Request(url, headers={"User-Agent": "GHC/1.0", "Accept": "text/html,text/plain"})
    with urllib.request.build_opener(_SafeRedirect()).open(req, timeout=30) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "text/plain"):
            raise ValueError("A página não é HTML ou texto simples: " + content_type)
        data = response.read(MAX_WEB_BYTES + 1)
        if len(data) > MAX_WEB_BYTES:
            raise ValueError("Página excede 2 MiB.")
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        text = data.decode(charset, "replace")
    except LookupError as e:
        raise ValueError("Codificação de página desconhecida: " + charset) from e
    if content_type == "text/html":
        parser = _TextExtractor()
        parser.feed(text)
        text = "".join(parser.parts)
    return (text[:MAX_CANVAS_CHARS] + "\n[Visualização truncada]") if len(text) > MAX_CANVAS_CHARS else text
