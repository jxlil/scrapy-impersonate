import time
from typing import Type, TypeVar
from urllib.parse import urljoin, urlparse

from curl_cffi.requests import AsyncSession
from scrapy.core.downloader.handlers.http11 import (
    HTTP11DownloadHandler as HTTPDownloadHandler,
)
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest
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
        curl_options = CurlOptionsParser(request.copy()).as_dict()

        async with AsyncSession(max_clients=1, curl_options=curl_options) as client:
            request_args = RequestParser(request).as_dict()
            start_time = time.time()
            response = await client.request(**request_args)
            download_latency = time.time() - start_time

        headers = Headers(response.headers.multi_items())
        headers.pop("Content-Encoding", None)

        if (
            300 <= response.status_code < 400
            and b"Location" in headers
            and not request.meta.get("dont_redirect")
        ):
            new_request = self._handle_redirect(request, headers, spider)
            return self._download_request(new_request, spider)  # type: ignore

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

    @staticmethod
    def _handle_redirect(request: Request, headers: Headers, spider: Spider) -> Request:
        allowed_domains = getattr(spider, "allowed_domains", [])
        if allowed_domains:
            request.meta["dont_redirect"] = True

        location = headers.get("Location") or b""
        location = location.decode()

        redirected_url = (
            location if location.startswith("http") else urljoin(request.url, location)
        )

        domain = urlparse(redirected_url).netloc
        if not any(domain == d for d in allowed_domains):  # type: ignore
            spider.logger.warning(
                f"Filtered offsite request to %(domain)r: %(request)s",
                {"domain": domain, "request": request},
                extra={"spider": spider},
            )

            raise IgnoreRequest(f"Redirected to disallowed domain: {redirected_url}")

        return request.replace(url=redirected_url)
