import httpx
import pytest

from app.services.job_fetcher import JobFetchError, extract_email, fetch_job_posting, html_to_text

LONG = "Cerchiamo uno sviluppatore Python con esperienza in FastAPI e SQL. " * 10


def test_html_to_text_strips_scripts_and_tags():
    html = "<html><head><style>x{}</style></head><body><script>var a=1</script><h1>Dev</h1><p>Python  e SQL</p></body></html>"
    text = html_to_text(html)
    assert "var a" not in text and "x{}" not in text
    assert "Dev" in text and "Python e SQL" in text


def test_extract_email():
    assert extract_email("Scrivi a hr@acme.it entro venerdì") == "hr@acme.it"
    assert extract_email("nessuna mail") is None
    assert extract_email("noreply@acme.it oppure jobs@acme.it") == "jobs@acme.it"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


async def test_fetch_ok():
    client = _client(lambda r: httpx.Response(200, text=f"<body><p>{LONG}</p></body>"))
    text = await fetch_job_posting("https://x.it/job", client=client)
    assert "FastAPI" in text


async def test_fetch_login_wall_short_text():
    client = _client(lambda r: httpx.Response(200, text="<body>Accedi per continuare</body>"))
    with pytest.raises(JobFetchError):
        await fetch_job_posting("https://x.it/job", client=client)


async def test_fetch_http_error_and_bad_scheme():
    client = _client(lambda r: httpx.Response(403))
    with pytest.raises(JobFetchError):
        await fetch_job_posting("https://x.it/job", client=client)
    with pytest.raises(JobFetchError):
        await fetch_job_posting("file:///etc/passwd")
