import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody.server import make_server


def start(path):
    httpd = make_server(path)
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def stop(httpd):
    httpd.shutdown()
    httpd.server_close()


def call(url, method, path, token=None, payload=None, form=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        data = form.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = "Bearer " + token
    split = urlsplit(url + path)
    request_url = urlunsplit((split.scheme, split.netloc, quote(split.path, safe="/"), quote(split.query, safe="=&"), ""))
    request = urllib.request.Request(request_url, data=data, headers=headers, method=method)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)
