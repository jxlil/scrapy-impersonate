# scrapy-impersonate

Scrapy download handler that can impersonate browser fingerprints.

## Installation

```
pip install git+http://github.com/jxlil/scrapy-impersonate
```

## Activation

Replace the default `http` and/or `https` Download Handlers through [`DOWNLOAD_HANDLERS`]("https://docs.scrapy.org/en/latest/topics/settings.html")

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_impersonate.ImpersonateDownloadHandler",
    "https": "scrapy_impersonate.ImpersonateDownloadHandler",
}
```

Also, be sure to install the asyncio-based Twisted reactor:

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

## Basic usage

```python
import scrapy

class AwesomeSpider(scrapy.Spider):
    name = "awesome"

    def start_requests(self):
        # GET request
        yield scrapy.Request("https://httpbin.org/get", meta={"impersonate": "chrome110"})

        # POST request
        yield scrapy.FormRequest(
            url="https://httpbin.org/post",
            formdata={"foo": "bar"},
            meta={"impersonate": "chrome110"},
        )

    def parse(self, response):
        # 'response' contains the page as seen by the browser
        return {"url": response.url}
```
