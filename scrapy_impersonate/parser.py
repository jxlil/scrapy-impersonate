import base64
from typing import Any, Dict, List, Optional, Tuple, Union

from curl_cffi import CurlOpt
from scrapy.http.request import Request


def curl_option_method(func):
    func._is_curl_option = True
    return func


class CurlOptionsParser:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.curl_options = {}

    @curl_option_method
    def _set_proxy_auth(self):
        """Add support for proxy auth headers"""

        proxy_auth = self.request.headers.pop(b"Proxy-Authorization", None)
        if proxy_auth is None:
            return

        proxy = self.request.meta.get("proxy", "")
        is_basic = proxy_auth[0].lower().startswith(b"basic ")
        if proxy.startswith(("socks5h://", "socks5://", "socks4://")) or (
            is_basic and proxy.startswith(("http://", "https://"))
        ):
            # Passed as username/password rather than a raw header so libcurl won't
            # reuse a pooled proxy connection that was opened with other credentials.
            # the password may contain ":", the username can't (RFC 7617)
            credentials = base64.b64decode(proxy_auth[0].split(b" ")[1])
            username, password = credentials.split(b":", 1)
            self.curl_options[CurlOpt.PROXYUSERNAME] = username
            self.curl_options[CurlOpt.PROXYPASSWORD] = password

        elif proxy.startswith(("http://", "https://")):
            proxy_auth_header = [b"Proxy-Authorization: " + proxy_auth[0]]
            self.curl_options[CurlOpt.PROXYHEADER] = proxy_auth_header

    def _set_custom_options(self):
        """Add support for raw libcurl options set through request.meta"""

        for option, value in self.request.meta.get("impersonate_curl_options", {}).items():
            if isinstance(option, str):
                try:
                    option = CurlOpt[option.upper()]
                except KeyError:
                    raise ValueError(f"Unknown curl option: {option}") from None

            self.curl_options[option] = value

    def as_dict(self):
        for method_name in dir(self):
            method = getattr(self, method_name)
            if callable(method) and getattr(method, "_is_curl_option", False):
                method()

        # applied last, so that user provided options take precedence
        self._set_custom_options()

        return self.curl_options


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
        # Prevent curl_cffi from adding the "Content-Type: application/octet-stream" header
        # when the request body is empty.
        body = self._request.body
        return None if body == b"" else body

    @property
    def headers(self) -> dict:
        # Same as Headers.to_unicode_dict(), deprecated in Scrapy 2.20; to_tuple_list()
        # isn't available on the minimum supported Scrapy.
        headers = self._request.headers
        return {
            key.decode(headers.encoding, errors="replace"): b",".join(values).decode(
                headers.encoding, errors="replace"
            )
            for key, values in headers.items()
        }

    @property
    def allow_redirects(self) -> bool:
        # Prevent curl_cffi from doing redirects, these should be handled by Scrapy
        return False

    @property
    def proxy(self) -> Optional[str]:
        return self._request.meta.get("proxy")

    @property
    def impersonate(self) -> Optional[str]:
        return self._request.meta.get("impersonate")

    def as_dict(self) -> dict:
        request_args = {
            property_name: getattr(self, property_name)
            for property_name, method in self.__class__.__dict__.items()
            if isinstance(method, property)
        }

        # Not a property: curl_cffi treats timeout=None as "no timeout", not as its default
        if "download_timeout" in self._request.meta:
            request_args["timeout"] = self._request.meta["download_timeout"]

        request_args.update(self._impersonate_args)
        return request_args
