# scrapy-impersonate
[![version](https://img.shields.io/pypi/v/scrapy-impersonate.svg)](https://pypi.python.org/pypi/scrapy-impersonate)

`scrapy-impersonate` is a Scrapy download handler. This project integrates [curl_cffi](https://github.com/yifeikong/curl_cffi) to perform HTTP requests, so it can impersonate browsers' TLS signatures or JA3 fingerprints.


## Installation

```
pip install scrapy-impersonate
```

## Activation

Replace the default `http` and/or `https` Download Handlers through [`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html#download-handlers)

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_impersonate.ImpersonateDownloadHandler",
    "https": "scrapy_impersonate.ImpersonateDownloadHandler",
}
```

Also, be sure to [install the asyncio-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor):

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

## Basic usage

Set the `impersonate` [Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta) key to download a request using `curl_cffi`:

```python
import scrapy


class ImpersonateSpider(scrapy.Spider):
    name = "impersonate_spider"
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_impersonate.ImpersonateDownloadHandler",
            "https": "scrapy_impersonate.ImpersonateDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    }

    def start_requests(self):
        for browser in ["chrome110", "edge99", "safari15_5"]:
            yield scrapy.Request(
                "https://tls.browserleaks.com/json",
                dont_filter=True,
                meta={"impersonate": browser},
            )

    def parse(self, response):
        # ja3_hash: 773906b0efdefa24a7f2b8eb6985bf37
        # ja3_hash: cd08e31494f9531f560d64c695473da9
        # ja3_hash: 2fe1311860bc318fc7f9196556a2a6b9
        return {"ja3_hash": response.json()["ja3_hash"]}
```

In this case, a Chrome browser with version 110 (`chrome110`) is being impersonated. Here you can find all the [browsers that you can impersonate](https://github.com/lwthiker/curl-impersonate#supported-browsers).

## Thanks

This project is inspired by the following projects:

+ [curl_cffi](https://github.com/yifeikong/curl_cffi) - Python binding for curl-impersonate via cffi. A http client that can impersonate browser tls/ja3/http2 fingerprints.
+ [curl-impersonate](https://github.com/lwthiker/curl-impersonate) - A special build of curl that can impersonate Chrome & Firefox
+ [scrapy-playwright](https://github.com/scrapy-plugins/scrapy-playwright) - Playwright integration for Scrapy
