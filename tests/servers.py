"""Local servers used by the test suite.

The proxy is a real ``CONNECT`` proxy, so anything the origin sees necessarily
travelled inside the tunnel, i.e. it was sent by curl as a request header.
"""

import datetime
import ipaddress
import json
import select
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PROXY_CREDENTIALS = "Basic dXNlcjpwYXNz"  # user:pass


def make_self_signed_cert(directory: Path) -> Tuple[Path, Path]:
    """Generate a self-signed certificate for 127.0.0.1."""

    cert_path, key_path = directory / "cert.pem", directory / "key.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    return cert_path, key_path


class EchoHandler(BaseHTTPRequestHandler):
    """Replies with a JSON dump of the headers it received."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        payload = {
            "path": self.path,
            "headers": {name.lower(): value for name, value in self.headers.items()},
        }
        body = json.dumps(payload).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class ConnectProxyHandler(BaseHTTPRequestHandler):
    """Minimal ``CONNECT`` proxy that requires ``Proxy-Authorization``."""

    protocol_version = "HTTP/1.1"

    def do_CONNECT(self) -> None:
        self.server.proxy_authorization = self.headers.get("Proxy-Authorization")  # type: ignore[attr-defined]

        if self.server.proxy_authorization != PROXY_CREDENTIALS:  # type: ignore[attr-defined]
            self.connection.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
            self.close_connection = True
            return

        host, _, port = self.path.rpartition(":")
        upstream = socket.create_connection((host, int(port)))
        self.connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        self._tunnel(upstream)

    def _tunnel(self, upstream: socket.socket) -> None:
        sockets = [self.connection, upstream]
        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 10)
                if exceptional or not readable:
                    return

                for source in readable:
                    target = upstream if source is self.connection else self.connection
                    data = source.recv(65536)
                    if not data:
                        return
                    target.sendall(data)
        finally:
            upstream.close()
            self.close_connection = True

    def log_message(self, *args) -> None:
        pass


class LocalServer:
    """Runs an ``HTTPServer`` on a free port in a background thread."""

    def __init__(self, handler, certificate: Optional[Tuple[Path, Path]] = None) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server.proxy_authorization = None  # type: ignore[attr-defined]

        if certificate:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*certificate)
            self._server.socket = context.wrap_socket(self._server.socket, server_side=True)

        self.scheme = "https" if certificate else "http"
        self.host, self.port = self._server.server_address[:2]

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def proxy_authorization(self) -> Optional[str]:
        """The ``Proxy-Authorization`` value seen on the last CONNECT."""
        return self._server.proxy_authorization  # type: ignore[attr-defined]

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
