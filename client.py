"""POST exactly once. GET retries only. Never echo transport/body errors."""
import time
from urllib.parse import urljoin, urlsplit
import requests


class ClientError(Exception):
    pass


def origin(url):
    u = urlsplit(url)
    return u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80)


class Client:
    def __init__(self, base, key, request_timeout=30):
        self.base, self.key = base, key
        self.timeout = max(1, min(120, request_timeout))

    def submit(self, path, payload, uploads):
        kwargs = {"json": payload} if uploads is None else {"data": payload, "files": uploads}
        # URL-only KR edit still requires multipart: encode text as text parts.
        if uploads == []:
            kwargs = {"files": [(k, (None, v)) for k, v in payload]}
        try:
            with requests.post(self.base + path, headers={"Authorization": "Bearer " + self.key},
                               timeout=self.timeout, allow_redirects=False, **kwargs) as r:
                if not 200 <= r.status_code < 300:
                    # No generic HTTP code proves upstream did not run/charge.
                    raise ClientError(f"submit_http_{r.status_code}_outcome_unknown")
                body = r.json()
                task_id = body.get("task_id") if isinstance(body, dict) else None
                if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
                    raise ClientError("submit_response_missing_task_id_outcome_unknown")
                if self.key in task_id or any(c.isspace() for c in task_id):
                    raise ClientError("submit_response_invalid_task_id_outcome_unknown")
                return task_id
        except (requests.RequestException, ValueError):
            raise ClientError("submit_transport_or_response_error_outcome_unknown") from None

    def query(self, path, cancel, deadline):
        last = "query_unavailable"
        for attempt in range(3):
            if cancel.is_set() or time.monotonic() >= deadline:
                raise ClientError("wait_cancelled_or_timed_out")
            try:
                timeout = max(0.1, min(self.timeout, deadline - time.monotonic()))
                with requests.get(self.base + path, headers={"Authorization": "Bearer " + self.key}, timeout=timeout, allow_redirects=False) as r:
                    if 200 <= r.status_code < 300:
                        body = r.json()
                        if not isinstance(body, dict) or body.get("status") not in ("queued", "processing", "succeeded", "failed", "unknown"):
                            raise ClientError("query_invalid_response")
                        return body
                    last = f"query_http_{r.status_code}"
                    if r.status_code not in (408, 429) and r.status_code < 500:
                        raise ClientError(last)
            except (requests.RequestException, ValueError):
                last = "query_transport_or_response_error"
            cancel.wait(min(0.5 * 2**attempt, max(0, deadline - time.monotonic())))
        raise ClientError(last)

    def download(self, url, max_bytes=64 * 1024**2):
        url = urljoin(self.base + "/", url)
        # Re-evaluate auth at every redirect, including redirects off-site.
        for _ in range(6):
            u = urlsplit(url)
            local_test = origin(url) == origin(self.base) and u.hostname == "127.0.0.1"
            if u.username or u.password or (u.scheme != "https" and not local_test):
                raise ClientError("download_url_not_allowed")
            headers = {"Authorization": "Bearer " + self.key} if origin(url) == origin(self.base) else {}
            response = None
            for attempt in range(3):
                try:
                    response = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=False, stream=True)
                    if response.status_code in (408, 429) or response.status_code >= 500:
                        response.close()
                        response = None
                        time.sleep(0.2 * 2**attempt)
                        continue
                    break
                except requests.RequestException:
                    if attempt < 2:
                        time.sleep(0.2 * 2**attempt)
            if response is None:
                raise ClientError("download_transport_error")
            with response as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    if "Location" not in r.headers:
                        raise ClientError("download_redirect_missing_location")
                    url = urljoin(url, r.headers["Location"])
                    continue
                if not 200 <= r.status_code < 300:
                    raise ClientError(f"download_http_{r.status_code}")
                chunks, length = [], 0
                try:
                    for chunk in r.iter_content(65536):
                        length += len(chunk)
                        if length > max_bytes:
                            raise ClientError("download_exceeds_64_MiB")
                        chunks.append(chunk)
                except requests.RequestException:
                    raise ClientError("download_stream_error_retry_fetch_node") from None
                return b"".join(chunks)
        raise ClientError("download_redirect_limit")
