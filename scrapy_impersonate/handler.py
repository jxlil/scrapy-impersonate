from typing import Type, TypeVar

from curl_cffi.requests import AsyncSession
from curl_cffi.curl import CurlOpt
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Headers, Request, Response
from scrapy.responsetypes import responsetypes
from scrapy.spiders import Spider
from scrapy.utils.defer import deferred_f_from_coro_f
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred

from scrapy_impersonate.parser import RequestParser

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
        #  Add support for proxy auth headers
        curl_options = {}
        proxy_header = []
        if b'Proxy-Authorization' in request.headers:
            proxy_header_authorization=b'Proxy-Authorization: '+ request.headers.pop(b'Proxy-Authorization')[0]
            proxy_header.append(proxy_header_authorization)
            curl_options[CurlOpt.PROXYHEADER] = proxy_header
        async with AsyncSession(max_clients=1,curl_options=curl_options) as client:
            response = await client.request(**RequestParser(request).as_dict())  # type: ignore

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
            request=request,
        )
