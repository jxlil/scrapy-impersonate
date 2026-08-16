import pytest
from twisted.internet import asyncioreactor
from twisted.internet.error import ReactorAlreadyInstalledError

# The download handler requires the asyncio reactor, and it must be installed
# before anything imports twisted.internet.reactor.
try:
    asyncioreactor.install()
except ReactorAlreadyInstalledError:
    pass

from tests.servers import (  # noqa: E402
    ConnectProxyHandler,
    EchoHandler,
    LocalServer,
    make_self_signed_cert,
)


@pytest.fixture(scope="session")
def certificate(tmp_path_factory):
    return make_self_signed_cert(tmp_path_factory.mktemp("certs"))


@pytest.fixture
def http_server():
    server = LocalServer(EchoHandler)
    yield server
    server.stop()


@pytest.fixture
def https_server(certificate):
    server = LocalServer(EchoHandler, certificate=certificate)
    yield server
    server.stop()


@pytest.fixture
def proxy_server():
    server = LocalServer(ConnectProxyHandler)
    yield server
    server.stop()
