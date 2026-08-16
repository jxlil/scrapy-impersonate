import base64

import pytest
from curl_cffi import CurlOpt
from scrapy.http.request import Request

from scrapy_impersonate.parser import CurlOptionsParser, RequestParser


def make_request(**kwargs) -> Request:
    kwargs.setdefault("url", "https://example.org")
    kwargs.setdefault("meta", {}).setdefault("impersonate", "chrome")
    return Request(**kwargs)


class TestCurlOptionsParser:
    def test_http_proxy_auth_moves_to_proxy_header(self):
        request = make_request(
            meta={"impersonate": "chrome", "proxy": "http://proxy.example:8080"},
            headers={"Proxy-Authorization": "Basic dXNlcjpwYXNz"},
        )

        curl_options = CurlOptionsParser(request).as_dict()

        assert curl_options[CurlOpt.PROXYHEADER] == [b"Proxy-Authorization: Basic dXNlcjpwYXNz"]
        assert b"Proxy-Authorization" not in request.headers

    @pytest.mark.parametrize("scheme", ["socks5h", "socks5", "socks4"])
    def test_socks_proxy_auth_moves_to_proxy_credentials(self, scheme):
        credentials = base64.b64encode(b"user:pass").decode()
        request = make_request(
            meta={"impersonate": "chrome", "proxy": f"{scheme}://proxy.example:1080"},
            headers={"Proxy-Authorization": f"Basic {credentials}"},
        )

        curl_options = CurlOptionsParser(request).as_dict()

        assert curl_options[CurlOpt.PROXYUSERNAME] == b"user"
        assert curl_options[CurlOpt.PROXYPASSWORD] == b"pass"
        assert b"Proxy-Authorization" not in request.headers

    def test_proxy_auth_is_dropped_when_no_proxy_is_set(self):
        request = make_request(headers={"Proxy-Authorization": "Basic dXNlcjpwYXNz"})

        curl_options = CurlOptionsParser(request).as_dict()

        assert curl_options == {}
        assert b"Proxy-Authorization" not in request.headers

    def test_no_options_without_proxy_auth(self):
        request = make_request(meta={"impersonate": "chrome", "proxy": "http://proxy.example"})

        assert CurlOptionsParser(request).as_dict() == {}


class TestCustomCurlOptions:
    def test_option_names_are_resolved(self):
        request = make_request(
            meta={"impersonate": "chrome", "impersonate_curl_options": {"dns_servers": "1.1.1.1"}}
        )

        assert CurlOptionsParser(request).as_dict() == {CurlOpt.DNS_SERVERS: "1.1.1.1"}

    def test_option_members_are_accepted(self):
        request = make_request(
            meta={"impersonate": "chrome", "impersonate_curl_options": {CurlOpt.MAXREDIRS: 0}}
        )

        assert CurlOptionsParser(request).as_dict() == {CurlOpt.MAXREDIRS: 0}

    def test_unknown_option_is_rejected(self):
        request = make_request(
            meta={"impersonate": "chrome", "impersonate_curl_options": {"not_an_option": 1}}
        )

        with pytest.raises(ValueError, match="Unknown curl option: not_an_option"):
            CurlOptionsParser(request).as_dict()

    def test_custom_options_take_precedence(self):
        request = make_request(
            meta={
                "impersonate": "chrome",
                "proxy": "http://proxy.example:8080",
                "impersonate_curl_options": {
                    "PROXYHEADER": [b"Proxy-Authorization: Bearer token"]
                },
            },
            headers={"Proxy-Authorization": "Basic dXNlcjpwYXNz"},
        )

        curl_options = CurlOptionsParser(request).as_dict()

        assert curl_options[CurlOpt.PROXYHEADER] == [b"Proxy-Authorization: Bearer token"]


class TestRequestParser:
    def test_basic_arguments(self):
        request = make_request(method="POST", body=b"payload")

        request_args = RequestParser(request).as_dict()

        assert request_args["method"] == "POST"
        assert request_args["url"] == "https://example.org"
        assert request_args["data"] == b"payload"
        assert request_args["impersonate"] == "chrome"

    def test_empty_body_is_not_sent(self):
        """Avoids curl_cffi adding a Content-Type header to bodyless requests."""

        assert RequestParser(make_request()).as_dict()["data"] is None

    def test_redirects_are_left_to_scrapy(self):
        assert RequestParser(make_request()).as_dict()["allow_redirects"] is False

    def test_headers_are_forwarded(self):
        request = make_request(headers={"X-Custom": "value"})

        assert RequestParser(request).as_dict()["headers"]["X-Custom"] == "value"

    @pytest.mark.parametrize(
        "cookies, expected",
        [
            ({"a": "1", "b": "2"}, {"a": "1", "b": "2"}),
            ([{"a": "1"}, {"b": "2"}], {"a": "1", "b": "2"}),
            (None, {}),
        ],
    )
    def test_cookies(self, cookies, expected):
        request = make_request(cookies=cookies)

        assert RequestParser(request).as_dict()["cookies"] == expected

    def test_impersonate_args_override_defaults(self):
        request = make_request(
            meta={"impersonate": "chrome", "impersonate_args": {"timeout": 5, "verify": False}}
        )

        request_args = RequestParser(request).as_dict()

        assert request_args["timeout"] == 5
        assert request_args["verify"] is False
