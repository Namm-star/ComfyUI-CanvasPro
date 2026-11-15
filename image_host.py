"""Explicit temporary ImgBB uploads, expiration fixed at three hours."""
import os
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .bundled_host import DEFAULT_IMGBB_KEY

EXPIRATION = 10800
class UploadError(Exception): pass

def host_key(value=""):
    key=value.strip() or os.environ.get("CANVASPRO_IMGBB_API_KEY", "").strip()
    if not key:
        p=Path(os.environ.get("LOCALAPPDATA",Path.home()/".config"))/"CanvasProComfyUI/imgbb-key.txt"
        if p.exists(): key=p.read_text(encoding="utf-8").strip()
    key = key or DEFAULT_IMGBB_KEY
    if not key or any(c.isspace() for c in key):
        raise ValueError("即梦本地参考图需填写批量执行节点的 imgbb_api_key；图床自动删除时间为3小时")
    return key

def upload(blob,key):
    if not blob or len(blob)>32*1024**2:raise UploadError("imgbb_image_exceeds_32_MiB")
    try:
        with requests.post("https://api.imgbb.com/1/upload",data={"key":key,"expiration":str(EXPIRATION)},
                files={"image":("reference.png",blob,"image/png")},timeout=60,allow_redirects=False) as response:
            if response.status_code!=200:raise UploadError("imgbb_upload_failed")
            body=response.json();data=body.get("data",{})
            if body.get("success") is not True or str(data.get("expiration"))!=str(EXPIRATION):
                raise UploadError("imgbb_expiration_not_confirmed")
            url=data.get("url","");u=urlsplit(url)
            if u.scheme!="https" or u.hostname!="i.ibb.co" or u.username or u.password or key in url:
                raise UploadError("imgbb_invalid_image_url")
            return url
    except (requests.RequestException,ValueError,TypeError,AttributeError):
        raise UploadError("imgbb_upload_transport_or_response_error") from None
