import json

import pytest
from curl_cffi import CurlOpt
from scrapy.core.downloader.handlers import DownloadHandlers
from scrapy.http.request import Request
from scrapy.spiders import Spider
from scrapy.utils.test import get_crawler

from scrapy_impersonate import ImpersonateDownloadHandler
from tests.servers import PROXY_CREDENTIALS


@pytest.fixture
def handler():
    return ImpersonateDownloadHandler.from_crawler(get_crawler())


def echoed(response) -> dict:
    return json.loads(response.body)


async def test_request_is_downloaded(handler, http_server):
    request = Request(f"{http_server.url}/hello", meta={"impersonate": "chrome"})

    response = await handler.download_request(request)

    assert response.status == 200
    assert "impersonate" in response.flags
    assert echoed(response)["path"] == "/hello"
    assert response.meta["download_latency"] > 0


async def test_headers_are_sent(handler, http_server):
    request = Request(
        http_server.url,
        meta={"impersonate": "chrome"},
        headers={"X-Custom": "value"},
    )

    response = await handler.download_request(request)

    assert echoed(response)["headers"]["x-custom"] == "value"


@pytest.mark.skipif(
    not hasattr(CurlOpt, "HTTPHEADER_ORDER"), reason="requires curl_cffi >= 0.16.0"
)
async def test_curl_options_set_the_header_order(handler, http_server):
    request = Request(
        http_server.url,
        meta={
            "impersonate": "chrome",
            "impersonate_curl_options": {"HTTPHEADER_ORDER": "Host,Accept,User-Agent"},
        },
    )

    response = await handler.download_request(request)

    assert list(echoed(response)["headers"])[:3] == ["host", "accept", "user-agent"]


@pytest.mark.filterwarnings("error::scrapy.exceptions.ScrapyDeprecationWarning")
async def test_request_is_downloaded_through_scrapy_dispatch(http_server):
    """Regression test for https://github.com/jxlil/scrapy-impersonate/issues/55

    Every other test calls the handler directly, so none of them notices when its
    signature stops matching the one the installed Scrapy calls. Going through
    DownloadHandlers is what pins the handler to the download handler API, and
    turning the deprecation into an error is what keeps it on the current one:
    Scrapy still accepts the pre-2.14 Deferred/spider variant, only warning about
    it, so without this the drift would pass unnoticed until Scrapy drops it.
    """
    crawler = get_crawler(
        Spider,
        {"DOWNLOAD_HANDLERS": {"http": "scrapy_impersonate.ImpersonateDownloadHandler"}},
    )
    crawler.spider = Spider("test")
    handlers = DownloadHandlers(crawler)
    request = Request(f"{http_server.url}/hello", meta={"impersonate": "chrome"})

    response = await handlers.download_request_async(request)

    assert response.status == 200
    assert "impersonate" in response.flags
    assert echoed(response)["path"] == "/hello"


class TestProxyAuthorization:
    """Regression tests for https://github.com/jxlil/scrapy-impersonate/issues/52

    The origin is reached through a CONNECT tunnel, so any header it sees was
    necessarily sent by curl as a regular request header.
    """

    @pytest.fixture
    def request_through_proxy(self, https_server, proxy_server):
        return Request(
            f"{https_server.url}/api/all",
            meta={
                "impersonate": "chrome",
                "proxy": proxy_server.url,
                "impersonate_args": {"verify": False},
            },
            headers={"Proxy-Authorization": PROXY_CREDENTIALS},
        )

    async def test_proxy_receives_the_credentials(
        self, handler, proxy_server, request_through_proxy
    ):
        await handler.download_request(request_through_proxy)

        assert proxy_server.proxy_authorization == PROXY_CREDENTIALS

    async def test_origin_does_not_receive_the_credentials(self, handler, request_through_proxy):
        response = await handler.download_request(request_through_proxy)

        assert "proxy-authorization" not in echoed(response)["headers"]

    async def test_original_request_is_not_mutated(self, handler, request_through_proxy):
        await handler.download_request(request_through_proxy)

        assert request_through_proxy.headers.get(b"Proxy-Authorization") == (
            PROXY_CREDENTIALS.encode()
        )
