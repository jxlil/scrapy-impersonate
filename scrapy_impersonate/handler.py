from typing import Optional, Type, TypeVar

from curl_cffi.requests import AsyncSession
from scrapy import signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Headers, Request, Response
from scrapy.responsetypes import responsetypes
from scrapy.spiders import Spider
from scrapy.utils.defer import deferred_f_from_coro_f, deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred

from scrapy_impersonate.parser import RequestParser

ImpersonateHandler = TypeVar("ImpersonateHandler", bound="ImpersonateDownloadHandler")


class ImpersonateDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)

        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)

        self.client: Optional[AsyncSession] = None

    @classmethod
    def from_crawler(cls: Type[ImpersonateHandler], crawler: Crawler) -> ImpersonateHandler:
        return cls(crawler)

    @deferred_f_from_coro_f
    async def _engine_started(self, signal, sender) -> None:
        self.client = await AsyncSession().__aenter__()

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("impersonate"):
            return deferred_from_coro(self._download_request(request, spider))

        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        response = await self.client.request(**RequestParser(request).as_dict())  # type: ignore

        headers = Headers(response.headers)
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

    def close(self):
        yield super().close()
        yield self._close()

    @deferred_f_from_coro_f
    async def _close(self) -> None:
        await self.client.__aexit__()  # type: ignore
