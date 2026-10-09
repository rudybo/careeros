"""Scarica una pagina di annuncio e ne estrae il testo leggibile."""
import re
from html.parser import HTMLParser

import httpx

_SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_LOGIN_MARKERS = ("accedi", "sign in", "log in", "login", "iscriviti")
_MIN_CHARS = 300
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class JobFetchError(Exception):
    pass


def find_emails(text: str) -> list[str]:
    return _EMAIL_RE.findall(text)


def extract_email(text: str) -> str | None:
    for m in find_emails(text):
        if not re.match(r"(no-?reply|donotreply)", m.lower()):
            return m
    return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    raw = "".join(parser.parts)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _looks_like_login_wall(text: str) -> bool:
    if len(text) < _MIN_CHARS:
        return True
    return len(text) < 1500 and any(m in text.lower() for m in _LOGIN_MARKERS)


async def fetch_job_posting(url: str, client: httpx.AsyncClient | None = None) -> str:
    if not url.lower().startswith(("http://", "https://")):
        raise JobFetchError("Il link deve iniziare con http:// o https://")
    own_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=15, headers={"User-Agent": _UA})
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise JobFetchError(f"Impossibile scaricare la pagina: {e}") from e
    finally:
        if own_client:
            await client.aclose()

    text = html_to_text(resp.text)
    if _looks_like_login_wall(text):
        raise JobFetchError("Pagina non leggibile (login o contenuto vuoto): incolla il testo dell'annuncio.")
    return text
