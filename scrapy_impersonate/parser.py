import base64
from typing import Optional, Tuple, Union
from urllib.parse import urlparse

from scrapy.http import Request


class RequestParser:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._impersonate_args = request.meta.get("impersonate_args", {})

    @property
    def url(self) -> str:
        return self._request.url

    @property
    def method(self) -> str:
        return self._request.method

    @property
    def data(self) -> Union[bytes, str, None]:
        return self._request.body

    @property
    def cookies(self) -> dict:
        cookies = self._request.cookies
        if isinstance(cookies, list):
            return {k: v for cookie in cookies for k, v in cookie.items()}

        elif isinstance(cookies, dict):
            return {k: v for k, v in cookies.items()}

        else:
            return {}

    @property
    def headers(self) -> dict:
        headers = self._request.headers.to_unicode_dict()
        return dict(headers)

    @property
    def proxies(self) -> Union[dict, None]:
        proxy = self._request.meta.get("proxy")
        if not proxy:
            return

        parsed_proxy = urlparse(proxy)

        proxy_scheme = parsed_proxy.scheme or "http"
        proxy_netloc = parsed_proxy.netloc or parsed_proxy.path

        if proxy_auth := self.headers.get("Proxy-Authorization"):
            proxy_auth = proxy_auth.replace("Basic", "").strip()
            proxy_auth = base64.b64decode(proxy_auth).decode()

            if "@" not in proxy_netloc:
                proxy_netloc = f"{proxy_auth}@{proxy_netloc}"

        proxy = f"{proxy_scheme}://{proxy_netloc}"
        return {"http": proxy, "https": proxy}

    @property
    def allow_redirects(self) -> bool:
        return False if self._request.meta.get("dont_redirect") else True

    @property
    def impersonate(self) -> Union[str, None]:
        return self._request.meta.get("impersonate")

    @property
    def params(self) -> Optional[dict]:
        return self._impersonate_args.get("params")

    @property
    def json(self) -> Optional[dict]:
        return self._impersonate_args.get("json")

    @property
    def auth(self) -> Optional[Tuple[str, str]]:
        return self._impersonate_args.get("auth")

    @property
    def timeout(self) -> Union[float, Tuple[float, float]]:
        return self._impersonate_args.get("timeout", 30)

    @property
    def max_redirects(self) -> int:
        return self._impersonate_args.get("max_redirects", -1)

    @property
    def verify(self) -> Optional[bool]:
        return self._impersonate_args.get("verify")

    @property
    def thread(self) -> Optional[str]:
        return self._impersonate_args.get("thread")

    def as_dict(self) -> dict:
        return {
            property_name: getattr(self, property_name)
            for property_name, method in self.__class__.__dict__.items()
            if isinstance(method, property)
        }
