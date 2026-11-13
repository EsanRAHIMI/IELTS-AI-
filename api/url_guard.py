"""Block SSRF, including redirects onto private or metadata addresses.

Every hop is checked before a connection is opened. DNS answers are checked
as a set: if any address is non-public, the host is rejected. The TCP
connection then uses one address from that same lookup, so a later
re-resolution cannot swap in a link-local target.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google",
    "metadata.google.internal",
    "metadata.google.com",
    "instance-data",
    "instance-data.ec2.internal",
}

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
ALLOWED_PORTS = {80, 443}


class UrlRejected(Exception):
    """Safe to show to the job owner: ``code`` is a short token, not a URL."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def ip_is_blocked(value: str) -> bool:
    """True for private, loopback, link-local, multicast, reserved, and metadata."""
    try:
        addr = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if (
        addr.is_multicast
        or addr.is_unspecified
        or addr.is_reserved
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_private
        or not addr.is_global
    ):
        return True
    return False


def _coerce_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    text = host.strip().strip("[]")
    if text.isdigit():
        number = int(text)
        if 0 <= number <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(number)
        return None
    # Reject dotted forms that are not four plain decimal octets (octal/hex tricks).
    parts = text.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        if any((len(part) > 1 and part.startswith("0")) or int(part) > 255 for part in parts):
            raise UrlRejected("host")
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _host_name_blocked(host: str) -> bool:
    name = host.lower().rstrip(".")
    if name in BLOCKED_HOSTS or name.endswith(".localhost"):
        return True
    if name.endswith(".local") or name.endswith(".internal") or name.endswith(".localdomain"):
        return True
    if "0x" in name or "@" in name or "\\" in name:
        return True
    return False


def validate_url_syntax(url: str) -> str:
    """Return the hostname if the URL is safe to resolve. Raises UrlRejected."""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise UrlRejected("scheme")
    if parts.username or parts.password:
        raise UrlRejected("auth")
    host = parts.hostname
    if not host:
        raise UrlRejected("host")
    port = parts.port
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise UrlRejected("port")
    if _host_name_blocked(host):
        raise UrlRejected("host")
    try:
        literal = _coerce_literal(host)
    except UrlRejected:
        raise
    except ValueError as exc:
        raise UrlRejected("host") from exc
    if literal is not None and ip_is_blocked(str(literal)):
        raise UrlRejected("host")
    return host


def resolve_host(host: str) -> list[str]:
    literal = _coerce_literal(host)
    if literal is not None:
        return [str(literal)]
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlRejected("dns") from exc
    ips: list[str] = []
    for info in infos:
        ip = str(info[4][0]).split("%", 1)[0]
        if ip not in ips:
            ips.append(ip)
    return ips


def choose_connect_ip(host: str, *, resolver: Callable[[str], list[str]] = resolve_host) -> str:
    """Pick one public address. Reject the host if any answer is non-public."""
    if _host_name_blocked(host):
        raise UrlRejected("host")
    ips = resolver(host)
    if not ips or any(ip_is_blocked(ip) for ip in ips):
        raise UrlRejected("host")
    return ips[0]


def _location(base: str, headers: dict) -> str:
    loc = ""
    for key, value in headers.items():
        if key.lower() == "location":
            loc = value
            break
    if not loc:
        raise UrlRejected("redirect")
    return urljoin(base, loc.strip())


async def fetch_public_bytes(
    url: str,
    *,
    opener,
    max_bytes: int,
    max_redirects: int = 5,
) -> tuple[str, bytes]:
    """GET ``url`` with manual redirects. ``opener(url)`` returns status, headers, body."""
    current = url
    for _ in range(max_redirects + 1):
        validate_url_syntax(current)
        status, headers, body = await opener(current)
        if status in REDIRECT_STATUSES:
            current = _location(current, headers)
            continue
        if status >= 400:
            raise UrlRejected("status")
        if len(body) > max_bytes:
            raise UrlRejected("size")
        return current, body
    raise UrlRejected("redirect")


def guarded_backend():
    """httpcore backend that connects only to the address ``choose_connect_ip`` picked."""
    import httpcore

    inner = httpcore.AnyIOBackend()

    class _Backend:
        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            if port not in ALLOWED_PORTS:
                raise UrlRejected("port")
            ip = choose_connect_ip(host)
            kwargs = {
                "timeout": timeout,
                "local_address": local_address,
                "socket_options": socket_options,
            }
            return await inner.connect_tcp(ip, port, **kwargs)

        async def connect_unix_socket(self, *_args, **_kwargs):
            raise UrlRejected("socket")

        async def sleep(self, seconds):
            await inner.sleep(seconds)

    return _Backend()


async def pinned_transport():
    """httpx transport whose TCP dial uses the address ``choose_connect_ip`` picked.

    httpx 0.28 does not expose ``network_backend`` on ``AsyncHTTPTransport``.
    The pool is built directly so the dial cannot re-resolve onto a private address.
    TLS still uses the original hostname (SNI), because only the TCP host is swapped.
    """
    import httpcore
    import httpx

    transport = httpx.AsyncHTTPTransport(retries=0)
    unused = transport._pool
    transport._pool = httpcore.AsyncConnectionPool(
        ssl_context=httpx.create_ssl_context(verify=True),
        max_connections=10,
        retries=0,
        network_backend=guarded_backend(),
    )
    await unused.aclose()
    return transport


async def httpx_opener(url: str, *, max_bytes: int):
    """Streaming opener used in production. Body is capped while it is read."""
    import httpx

    timeout = httpx.Timeout(20.0, connect=5.0)
    transport = await pinned_transport()
    headers = {"User-Agent": "IELTS-AI-Mastery", "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"}
    async with httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False) as client:
        try:
            async with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code in REDIRECT_STATUSES:
                    return resp.status_code, dict(resp.headers), b""
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    if len(buf) + len(chunk) > max_bytes:
                        raise UrlRejected("size")
                    buf.extend(chunk)
                return resp.status_code, dict(resp.headers), bytes(buf)
        except UrlRejected:
            raise
        except httpx.HTTPError as exc:
            raise UrlRejected("fetch") from exc
