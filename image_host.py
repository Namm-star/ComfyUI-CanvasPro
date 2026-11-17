"""Explicit temporary ImgBB uploads, expiration fixed at three hours."""
import os
import time
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .bundled_host import DEFAULT_IMGBB_KEY

EXPIRATION = 10800
class UploadError(Exception):
    def __init__(self,code,retryable=False):
        super().__init__(code)
        self.retryable=retryable

def host_key(value=""):
    key=value.strip() or os.environ.get("CANVASPRO_IMGBB_API_KEY", "").strip()
    if not key:
        p=Path(os.environ.get("LOCALAPPDATA",Path.home()/".config"))/"CanvasProComfyUI/imgbb-key.txt"
        if p.exists(): key=p.read_text(encoding="utf-8").strip()
    key = key or DEFAULT_IMGBB_KEY
    if not key or any(c.isspace() for c in key):
        raise ValueError("ImgBB Key缺失或格式无效，请检查插件图床配置；或断开IMAGE改用公网参考图网址。临时图片3小时后删除。")
    return key

def upload(blob,key,receipt=None,cancel=None):
    receipt=receipt if receipt is not None else {}
    receipt.update(provider="imgbb",attempts=0,http_status=None,status="pending",expiration=EXPIRATION,history=[])
    if not blob or len(blob)>32*1024**2:
        receipt.update(status="failed",error_code="imgbb_image_exceeds_32_MiB")
        raise UploadError("imgbb_image_exceeds_32_MiB")
    for attempt in range(1,4):
        if cancel is not None and cancel.is_set():
            receipt.update(status="failed",error_code="reference_upload_cancelled")
            raise UploadError("reference_upload_cancelled")
        receipt.update(attempts=attempt,http_status=None)
        info={"attempt":attempt,"http_status":None}
        try:
            with requests.post("https://api.imgbb.com/1/upload",data={"key":key,"expiration":str(EXPIRATION)},
                    files={"image":("reference.png",blob,"image/png")},timeout=(15,60),allow_redirects=False) as response:
                status=response.status_code
                receipt["http_status"]=info["http_status"]=status
                if status!=200:
                    raise UploadError(f"imgbb_http_{status}",status in (408,429) or status>=500)
                try:body=response.json()
                except ValueError:raise UploadError("imgbb_response_not_json",True) from None
                if not isinstance(body,dict):raise UploadError("imgbb_invalid_response")
                if body.get("success") is not True:raise UploadError("imgbb_api_rejected")
                if not isinstance(body.get("data"),dict):raise UploadError("imgbb_invalid_response")
                data=body["data"]
                if str(data.get("expiration"))!=str(EXPIRATION):raise UploadError("imgbb_expiration_not_confirmed")
                url=data.get("url","")
                if not isinstance(url,str):raise UploadError("imgbb_invalid_image_url")
                u=urlsplit(url)
                if u.scheme!="https" or u.hostname!="i.ibb.co" or u.username or u.password or key in url:
                    raise UploadError("imgbb_invalid_image_url")
                receipt["history"].append(info)
                receipt.update(status="succeeded")
                receipt.pop("error_code",None)
                return url
        except requests.RequestException as error:
            kind=("timeout" if isinstance(error,requests.Timeout) else
                  "proxy_error" if isinstance(error,requests.exceptions.ProxyError) else
                  "tls_error" if isinstance(error,requests.exceptions.SSLError) else
                  "connection_error" if isinstance(error,requests.ConnectionError) else "transport_error")
            problem=UploadError("imgbb_"+kind,True)
        except UploadError as error:problem=error
        except (ValueError,TypeError,AttributeError):problem=UploadError("imgbb_invalid_response")
        info["error_code"]=str(problem)
        receipt["history"].append(info)
        receipt.update(status="failed",error_code=str(problem))
        if not problem.retryable or attempt==3:raise UploadError(str(problem)) from None
        delay=0.5*attempt
        if cancel is not None:cancel.wait(delay)
        else:time.sleep(delay)
