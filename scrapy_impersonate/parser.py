from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from curl_cffi import CurlHttpVersion, CurlMime
from scrapy.http import Request


class RequestParser:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._impersonate_args = request.meta.get("impersonate_args", {})

    @property
    def method(self) -> str:
        return self._request.method

    @property
    def url(self) -> str:
        return self._request.url

    @property
    def params(self) -> Optional[Union[Dict, List, Tuple]]:
        return self._impersonate_args.get("params")

    @property
    def data(self) -> Optional[Any]:
        return self._request.body

    @property
    def json(self) -> Optional[dict]:
        return self._impersonate_args.get("json")

    @property
    def headers(self) -> dict:
        headers = self._request.headers.to_unicode_dict()
        return dict(headers)

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
    def files(self) -> Optional[dict]:
        return self._impersonate_args.get("files")

    @property
    def auth(self) -> Optional[Tuple[str, str]]:
        return self._impersonate_args.get("auth")

    @property
    def timeout(self) -> Union[float, Tuple[float, float]]:
        return self._impersonate_args.get("timeout", 30.0)

    @property
    def allow_redirects(self) -> bool:
        return False if self._request.meta.get("dont_redirect") else True

    @property
    def max_redirects(self) -> int:
        return self._impersonate_args.get("max_redirects", -1)

    @property
    def proxies(self) -> Optional[dict]:
        return self._impersonate_args.get("proxies")

    @property
    def proxy(self) -> Optional[str]:
        return self._request.meta.get("proxy")

    @property
    def proxy_auth(self) -> Optional[Tuple[str, str]]:
        return self._impersonate_args.get("proxy_auth")

    @property
    def verify(self) -> Optional[bool]:
        return self._impersonate_args.get("verify")

    @property
    def referer(self) -> Optional[str]:
        return self._impersonate_args.get("referer")

    @property
    def accept_encoding(self) -> str:
        return self._impersonate_args.get("accept_encoding", "gzip, deflate, br")

    @property
    def content_callback(self) -> Optional[Callable]:
        return self._impersonate_args.get("content_callback")

    @property
    def impersonate(self) -> Optional[str]:
        return self._request.meta.get("impersonate")

    @property
    def default_headers(self) -> Optional[bool]:
        return self._impersonate_args.get("default_headers")

    @property
    def default_encoding(self) -> Union[str, Callable[[bytes], str]]:
        return self._impersonate_args.get("default_encoding", "utf-8")

    @property
    def http_version(self) -> Optional[CurlHttpVersion]:
        return self._impersonate_args.get("http_version")

    @property
    def interface(self) -> Optional[str]:
        return self._impersonate_args.get("interface")

    @property
    def cert(self) -> Optional[Union[str, Tuple[str, str]]]:
        return self._impersonate_args.get("cert")

    @property
    def stream(self) -> bool:
        return self._impersonate_args.get("stream", False)

    @property
    def max_recv_speed(self) -> int:
        return self._impersonate_args.get("max_recv_speed", 0)

    @property
    def multipart(self) -> Optional[CurlMime]:
        return self._impersonate_args.get("multipart")

    def as_dict(self) -> dict:
        return {
            property_name: getattr(self, property_name)
            for property_name, method in self.__class__.__dict__.items()
            if isinstance(method, property)
        }
