# scrapy-impersonate
[![version](https://img.shields.io/pypi/v/scrapy-impersonate.svg)](https://pypi.python.org/pypi/scrapy-impersonate)

`scrapy-impersonate` is a Scrapy download handler. This project integrates [curl_cffi](https://github.com/yifeikong/curl_cffi) to perform HTTP requests, so it can impersonate browsers' TLS signatures or JA3 fingerprints.


## Installation

```
pip install scrapy-impersonate
```

## Activation

To use this package, replace the default `http` and `https` Download Handlers by updating the [`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html#download-handlers) setting:

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_impersonate.ImpersonateDownloadHandler",
    "https": "scrapy_impersonate.ImpersonateDownloadHandler",
}
```

By setting `USER_AGENT = None`, `curl_cffi` will automatically choose the appropriate User-Agent based on the impersonated browser:
```python
USER_AGENT = None
```

Also, be sure to [install the asyncio-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor) for proper asynchronous execution:

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```


## Usage

Set the `impersonate` [Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta) key to download a request using `curl_cffi`:

```python
import scrapy


class ImpersonateSpider(scrapy.Spider):
    name = "impersonate_spider"
    custom_settings = {
        "USER_AGENT": None,
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
        yield {"ja3_hash": response.json()["ja3_hash"]}
```

### impersonate-args

You can pass any necessary [arguments](https://github.com/lexiforest/curl_cffi/blob/38a91f2e7b23d9c9bda1d8085b7e41e33767c768/curl_cffi/requests/session.py#L1189-L1222) to `curl_cffi` through `impersonate_args`. For example:

```python
yield scrapy.Request(
    "https://tls.browserleaks.com/json",
    dont_filter=True,
    meta={
        "impersonate": browser,
        "impersonate_args": {
            "verify": False,
            "timeout": 10,
        },
    },
)
```


## Supported browsers

The following browsers can be impersonated

| Browser | Version | Build | OS | Name |
| --- | --- | --- | --- | --- |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 99 | 99.0.4844.51 | Windows 10 | `chrome99` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 99 | 99.0.4844.73 | Android 12 | `chrome99_android` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 100 | 100.0.4896.75 | Windows 10 | `chrome100` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 101 | 101.0.4951.67 | Windows 10 | `chrome101` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 104 | 104.0.5112.81 | Windows 10 | `chrome104` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 107 | 107.0.5304.107 | Windows 10 | `chrome107` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 110 | 110.0.5481.177 | Windows 10 | `chrome110` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 116 | 116.0.5845.180 | Windows 10 | `chrome116` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 119 | 119.0.6045.199 | macOS Sonoma | `chrome119` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 120 | 120.0.6099.109 | macOS Sonoma | `chrome120` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 123 | 123.0.6312.124 | macOS Sonoma | `chrome123` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 124 | 124.0.6367.60 | macOS Sonoma | `chrome124` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 131 | 131.0.6778.86 | macOS Sonoma | `chrome131` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 131 | 131.0.6778.81 | Android 14	 | `chrome131_android` |
| ![Chrome](https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_24x24.png "Chrome") | 133 | 133.0.6943.55 | macOS Sequoia | `chrome133a` |
| ![Edge](https://raw.githubusercontent.com/alrra/browser-logos/main/src/edge/edge_24x24.png "Edge") | 99 | 99.0.1150.30 | Windows 10 | `edge99` |
| ![Edge](https://raw.githubusercontent.com/alrra/browser-logos/main/src/edge/edge_24x24.png "Edge") | 101 | 101.0.1210.47 | Windows 10 | `edge101` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 15.3 | 16612.4.9.1.8 | MacOS Big Sur | `safari15_3` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 15.5 | 17613.2.7.1.8 | MacOS Monterey | `safari15_5` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 17.0 | unclear | MacOS Sonoma | `safari17_0` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 17.2 | unclear | iOS 17.2 | `safari17_2_ios` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 18.0 | unclear | MacOS Sequoia | `safari18_0` |
| ![Safari](https://github.com/alrra/browser-logos/blob/main/src/safari/safari_24x24.png "Safari") | 18.0 | unclear | iOS 18.0 | `safari18_0_ios` |
| ![Firefox](https://github.com/alrra/browser-logos/blob/main/src/firefox/firefox_24x24.png "Firefox") | 133.0 | 133.0.3 | macOS Sonoma | `firefox133` |
| ![Firefox](https://github.com/alrra/browser-logos/blob/main/src/firefox/firefox_24x24.png "Firefox") | 135.0 | 135.0.1 | macOS Sonoma	| `firefox135` |

## Thanks

This project is inspired by the following projects:

+ [curl_cffi](https://github.com/yifeikong/curl_cffi) - Python binding for curl-impersonate via cffi. A http client that can impersonate browser tls/ja3/http2 fingerprints.
+ [curl-impersonate](https://github.com/lwthiker/curl-impersonate) - A special build of curl that can impersonate Chrome & Firefox
+ [scrapy-playwright](https://github.com/scrapy-plugins/scrapy-playwright) - Playwright integration for Scrapy
