from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.api.core.config import settings


def resolve_frontend_url(client: str | None) -> str:
    selected_client = client or settings.OAUTH_DEFAULT_CLIENT
    frontend_url = settings.OAUTH_CLIENT_FRONTEND_MAP.get(
        selected_client,
        settings.OAUTH_CLIENT_FRONTEND_MAP[settings.OAUTH_DEFAULT_CLIENT],
    )
    return frontend_url.rstrip("/")


def add_client_query(url: str, client: str | None) -> str:
    if not client or client == settings.OAUTH_DEFAULT_CLIENT:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query["client"] = client
    return urlunparse(parsed._replace(query=urlencode(query)))
