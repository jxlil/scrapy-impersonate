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


class ImpersonateDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)

        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

    @classmethod
    def from_crawler(cls: Type[ImpersonateHandler], crawler: Crawler) -> ImpersonateHandler:
        return cls(crawler)

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("impersonate"):
            return self._download_request(request, spider)

        return super().download_request(request, spider)

    @deferred_f_from_coro_f
    async def _download_request(self, request: Request, spider: Spider) -> Response:
        # copy the request to avoid mutating the original in CurlOptionsParser (which pops headers)
        request_orig = request.copy()
        curl_options = CurlOptionsParser(request).as_dict()
        async with AsyncSession(max_clients=1, curl_options=curl_options) as client:
            request_args = RequestParser(request).as_dict()
            response = await client.request(**request_args)

        headers = Headers(response.headers.multi_items())
        headers.pop("Content-Encoding", None)

        respcls = responsetypes.from_args(
            headers=headers,
            url=response.url,
            body=response.content,
        )

        return respcls(
            url=response.url,
            status=response.status_code,
            headers=headers,
            body=response.content,
            flags=["impersonate"],
            request=request_orig,
        )
