import inspect
import time
from typing import Type, TypeVar

from curl_cffi.requests import AsyncSession
from scrapy.core.downloader.handlers.http11 import (
    HTTP11DownloadHandler as HTTPDownloadHandler,
)
from scrapy.crawler import Crawler
from scrapy.http.headers import Headers
from scrapy.http.request import Request
from scrapy.http.response import Response
from scrapy.responsetypes import responsetypes
from scrapy.spiders import Spider
from scrapy.utils.defer import deferred_f_from_coro_f
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred

from scrapy_impersonate.parser import CurlOptionsParser, RequestParser

ImpersonateHandler = TypeVar("ImpersonateHandler", bound="ImpersonateDownloadHandler")

# Scrapy 2.14 changed the download handler API: the constructor takes the crawler
# alone instead of (settings, crawler), and download_request() became a coroutine
# taking the request alone instead of a (request, spider) method returning a
# Deferred. Both conventions are supported, which one this class uses is decided
# at import time from the base class - the same thing Scrapy inspects to decide
# how to call the handler.
ASYNC_HANDLER_API = inspect.iscoroutinefunction(HTTPDownloadHandler.download_request)


class ImpersonateDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        if ASYNC_HANDLER_API:
            super().__init__(crawler=crawler)
        else:
            super().__init__(settings=crawler.settings, crawler=crawler)

        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

    @classmethod
    def from_crawler(cls: Type[ImpersonateHandler], crawler: Crawler) -> ImpersonateHandler:
        return cls(crawler)

    if ASYNC_HANDLER_API:

        async def download_request(self, request: Request) -> Response:
            if request.meta.get("impersonate"):
                return await self._download_request(request)
            return await super().download_request(request)

    else:

        def download_request(  # type: ignore[misc]
            self, request: Request, spider: Spider
        ) -> "Deferred[Response]":
            # Scrapy 2.13 calls handlers through mustbe_deferred(), which only
            # unwraps Deferreds and Failures, so the coroutine has to be turned
            # into a Deferred here instead of being returned as one.
            if request.meta.get("impersonate"):
                return deferred_f_from_coro_f(self._download_request)(request)
            return super().download_request(request, spider)  # type: ignore[call-arg]

    async def _download_request(self, request: Request) -> Response:
        # Work on a copy so CurlOptionsParser (which pops headers) does not mutate
        # the original request, and so those popped headers (e.g. Proxy-Authorization)
        # are not sent to the target server by RequestParser.
        request_copy = request.copy()
        curl_options = CurlOptionsParser(request_copy).as_dict()

        async with AsyncSession(max_clients=1, curl_options=curl_options) as client:
            request_args = RequestParser(request_copy).as_dict()
            start_time = time.time()
            response = await client.request(**request_args)
            download_latency = time.time() - start_time

        headers = Headers(response.headers.multi_items())
        headers.pop("Content-Encoding", None)

        respcls = responsetypes.from_args(
            headers=headers,
            url=response.url,
            body=response.content,
        )

        resp = respcls(
            url=response.url,
            status=response.status_code,
            headers=headers,
            body=response.content,
            flags=["impersonate"],
            request=request,
        )

        resp.meta["download_latency"] = download_latency
        return resp
