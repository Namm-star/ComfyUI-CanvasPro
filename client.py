"""POST exactly once. GET retries only. Never echo transport/body errors."""
import time
import base64
import binascii
import re
from urllib.parse import urljoin, urlsplit
import requests


class ClientError(Exception):
    pass


def origin(url):
    u = urlsplit(url)
    return u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80)


class Client:
    def __init__(self, base, key, request_timeout=30, sync_timeout=600):
        self.base, self.key = base, key
        self.timeout = max(1, min(120, request_timeout))
        self.sync_timeout = max(1, min(3600, sync_timeout))

    def task_failure_reason(self,body):
        error=body.get('error')
        message=error.get('message') if isinstance(error,dict) else error
        if not isinstance(message,str):return ''
        message=message[:4000].replace(self.key,'[redacted]')
        message=re.sub(r"https?://[^\s<>\"']+",'[url removed]',message,flags=re.I)
        message=re.sub(r'(?i)Bearer\s+\S+|sk-[A-Za-z0-9_-]+','[redacted]',message)
        message=re.sub(r'(?i)(api[_ -]?key|authorization|token|secret|signature)\s*[:=]\s*\S+','[redacted]',message)
        return ''.join(c for c in message if c.isprintable() or c in '\n\t')[:500]

    def submit(self, path, payload, uploads, receipt=None):
        receipt = receipt if receipt is not None else {}
        receipt["post_attempted"]=True
        kwargs = {"json": payload} if uploads is None else {"data": payload, "files": uploads}
        # URL-only KR edit still requires multipart: encode text as text parts.
        if uploads == []:
            kwargs = {"files": [(k, (None, v)) for k, v in payload]}
        try:
            with requests.post(self.base + path, headers={"Authorization": "Bearer " + self.key},
                               timeout=self.sync_timeout if path in ("/v1/images/generations","/v1/images/edits") else self.timeout, allow_redirects=False, **kwargs) as r:
                receipt["http_status"]=r.status_code
                for name in ("x-request-id","x-oneapi-request-id","request-id","x-trace-id"):
                    value=r.headers.get(name)
                    if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",value) and self.key not in value:
                        receipt["request_id"]=value;break
                if not 200 <= r.status_code < 300:
                    # No generic HTTP code proves upstream did not run/charge.
                    raise ClientError(f"submit_http_{r.status_code}_outcome_unknown")
                try:
                    body = r.json()
                except ValueError:
                    raise ClientError("submit_response_not_json_outcome_unknown") from None
                if path in ("/v1/images/generations", "/v1/images/edits"):
                    result=self.normalize_sync(body)
                    receipt["acknowledgement"]="sync_image_received"
                    return result
                task_id = body.get("id" if path.startswith("/aistars/") else "task_id") if isinstance(body, dict) else None
                if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
                    raise ClientError("submit_response_missing_task_id_outcome_unknown")
                if self.key in task_id or any(c.isspace() for c in task_id):
                    raise ClientError("submit_response_invalid_task_id_outcome_unknown")
                receipt["acknowledgement"]="task_id_received"
                return task_id
        except requests.Timeout:
            message="sync_submit_timeout_outcome_unknown_no_retry" if path in ("/v1/images/generations","/v1/images/edits") else "submit_timeout_outcome_unknown_no_retry"
            raise ClientError(message) from None
        except requests.RequestException as error:
            kind = ("proxy_error" if isinstance(error, requests.exceptions.ProxyError) else
                    "tls_error" if isinstance(error, requests.exceptions.SSLError) else
                    "connection_error" if isinstance(error, requests.ConnectionError) else "transport_error")
            raise ClientError(f"submit_{kind}_outcome_unknown") from None
        except ValueError:
            raise ClientError("submit_response_parse_error_outcome_unknown") from None

    def normalize_sync(self, body):
        data=body.get("data") if isinstance(body,dict) else None
        if not isinstance(data,list) or len(data)!=1 or not isinstance(data[0],dict):
            raise ClientError("sync_invalid_response_outcome_unknown")
        item=data[0]
        encoded=item.get("b64_json")
        url=item.get("url")
        url_result=[]
        if isinstance(url,str) and url and self.key not in url:
            u=urlsplit(url)
            local_test=origin(url)==origin(self.base) and u.hostname=="127.0.0.1"
            if (u.scheme=="https" or local_test) and u.hostname and not u.username and not u.password:
                url_result=[url]
        if isinstance(encoded,str) and encoded:
            if len(encoded)>90*1024**2:
                raise ClientError("sync_image_too_large_outcome_unknown")
            try: blob=base64.b64decode(encoded,validate=True)
            except (ValueError,binascii.Error):
                raise ClientError("sync_invalid_base64_outcome_unknown") from None
            if not blob or len(blob)>64*1024**2:
                raise ClientError("sync_image_too_large_outcome_unknown")
            # Reject corrupt data before recording success; never retry the POST.
            from PIL import Image
            import io
            try:
                with Image.open(io.BytesIO(blob)) as im: im.verify()
            except Exception:
                raise ClientError("sync_invalid_image_outcome_unknown") from None
            return {"urls":url_result,"image":blob}
        if isinstance(url,str) and url and self.key not in url:
            u=urlsplit(url)
            local_test=origin(url)==origin(self.base) and u.hostname=="127.0.0.1"
            if (u.scheme=="https" or local_test) and u.hostname and not u.username and not u.password:
                return {"urls":[url],"image":None}
        raise ClientError("sync_missing_result_outcome_unknown")

    def query(self, path, cancel, deadline, single_attempt=False):
        last = "query_unavailable"
        for attempt in range(1 if single_attempt else 3):
            if cancel.is_set() or time.monotonic() >= deadline:
                raise ClientError("wait_cancelled_or_timed_out")
            try:
                timeout = max(0.1, min(self.timeout, deadline - time.monotonic()))
                with requests.get(self.base + path, headers={"Authorization": "Bearer " + self.key}, timeout=timeout, allow_redirects=False) as r:
                    if 200 <= r.status_code < 300:
                        body = r.json()
                        if path.startswith("/kr/gpt/") and isinstance(body,dict) and body.get("status")=="succeeded":
                            from urllib.parse import unquote
                            encoded=path.rsplit("/",1)[-1]
                            if body.get("task_id")!=unquote(encoded):raise ClientError("query_task_id_mismatch")
                            body["data"]=[{"url":f"/v1/tasks/{encoded}/artifacts/image-1/content"}]
                        if path.startswith("/aistars/"):
                            body = self.normalize_aistars(body, path.rsplit("/",1)[-1])
                        if not isinstance(body, dict) or body.get("status") not in ("queued", "processing", "succeeded", "failed", "unknown"):
                            raise ClientError("query_invalid_response")
                        return body
                    last = f"query_http_{r.status_code}"
                    if r.status_code not in (408, 429) and r.status_code < 500:
                        raise ClientError(last)
            except (requests.RequestException, ValueError):
                last = "query_transport_or_response_error"
            if not single_attempt:
                cancel.wait(min(0.5 * 2**attempt, max(0, deadline - time.monotonic())))
        raise ClientError(last)

    @staticmethod
    def normalize_aistars(body, encoded_id):
        from urllib.parse import unquote
        if not isinstance(body, dict) or body.get("id") != unquote(encoded_id):
            raise ClientError("query_task_id_mismatch")
        status = {"queued":"queued", "pending":"queued", "running":"processing", "in_progress":"processing",
            "processing":"processing", "completed":"succeeded", "unknown":"unknown", "failed":"failed", "cancelled":"failed"}.get(body.get("status"))
        if status is None:
            raise ClientError("query_invalid_response")
        data=[]
        if status == "succeeded":
            artifacts=body.get("artifacts")
            if not isinstance(artifacts,list) or len(artifacts)!=1:
                raise ClientError("query_success_missing_image_url")
            for artifact in artifacts:
                url=artifact.get("content_url") if isinstance(artifact,dict) else None
                prefix=f"/v1/tasks/{encoded_id}/artifacts/"
                if not isinstance(url,str) or not url.startswith(prefix) or not url.endswith("/content") or any(p in (".","..") for p in url.split("/")):
                    raise ClientError("query_invalid_artifact_content_path")
                data.append({"url":url})
        return {"task_id":body["id"],"status":status,"data":data}

    def download(self, url, max_bytes=64 * 1024**2, authorize=True):
        url = urljoin(self.base + "/", url)
        # Re-evaluate auth at every redirect, including redirects off-site.
        for _ in range(6):
            u = urlsplit(url)
            local_test = origin(url) == origin(self.base) and u.hostname == "127.0.0.1"
            if u.username or u.password or (u.scheme != "https" and not local_test):
                raise ClientError("download_url_not_allowed")
            headers = {"Authorization": "Bearer " + self.key} if authorize and origin(url) == origin(self.base) else {}
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
