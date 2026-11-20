"""CanvasPro native image contracts updated 2026-11-20; see docs evidence."""
import base64
import re
import json
from pathlib import Path
from urllib.parse import urlsplit

IMAGE_MODELS = json.loads((Path(__file__).with_name("image_models.json")).read_text(encoding="utf-8"))
AISTARS = IMAGE_MODELS["aistars"]
SYNC = IMAGE_MODELS["sync"]
KR25 = IMAGE_MODELS["kr25"]
HC_NATIVE = IMAGE_MODELS["hc_native"]
MODELS = ("gpt-image-2", "T香蕉2", "T香蕉2.1", "T香蕉pro", "s-gpt-image-2", "s-gpt-image-2.5-flare", "s-gpt-image-2.5-sunburst", *AISTARS, *SYNC, *KR25, *HC_NATIVE)
RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9")

def ratios(model):
    return tuple(AISTARS[model]["ratios"] if model in AISTARS else IMAGE_MODELS["banana_ratios"].get(model, RATIOS))

def reference_limit(model):
    return 15 if model in HC_NATIVE else 16 if model in KR25 else SYNC[model]["references"] if model in SYNC else AISTARS[model]["references"] if model in AISTARS else {"kr":16,"hc":15,"gemini":14}[family(model)]


def family(model):
    if model not in MODELS:
        raise ValueError("Unsupported model; consult protocol evidence before extending registry")
    return "hc_native" if model in HC_NATIVE else "kr25" if model in KR25 else "sync" if model in SYNC else "aistars" if model in AISTARS else "gemini" if model.startswith("T香蕉") else "hc" if model.startswith("s-") else "kr"


def query_path(model, task_id):
    from urllib.parse import quote
    if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
        raise ValueError("Invalid task ID")
    if family(model) == "sync":
        raise ValueError("同步图片接口没有任务查询入口")
    if family(model) == "aistars":
        return "/aistars/v1/tasks/" + quote(task_id, safe="")
    if model in HC_NATIVE:return HC_NATIVE[model]["path"]+"/v1/images/tasks/"+quote(task_id,safe="")
    prefix = {"kr25": "/kr/gpt", "gemini": "/kr/gemini", "hc": "/hc", "kr": "/kr"}[family(model)]
    return prefix + "/v1/images/tasks/" + quote(task_id, safe="")


def public_reference(url, https_only=True, max_length=2048):
    u = urlsplit(url)
    host = u.hostname or ""
    if (u.scheme not in (("https",) if https_only else ("http","https")) or u.username or u.password or u.port not in (None, 443, *(() if https_only else (80,)))
            or "." not in host or host.endswith((".local", ".localhost"))
            or re.fullmatch(r"[\d.]+", host) or ":" in host or len(url) > max_length):
        raise ValueError("Reference URLs must be public domain URLs using the supported HTTP(S) scheme")
    return url


def build_request(model, prompt, size="", quality="", image_size="", files=(), urls=(), defer_upload=False, background="", output_format=""):
    f = family(model)
    prompt = prompt.strip()
    # JavaScript contract limits UTF-16 units, not Python Unicode code points.
    if not prompt or (f not in ("sync","kr25","hc_native") and len(prompt.encode("utf-16-le")) // 2 > (4000 if f == "kr" else 5000 if f == "aistars" else 8000)):
        raise ValueError("Prompt empty or exceeds model text limit")
    if f == "kr25" and len(prompt)>32000:
        raise ValueError("KR GPT 2.5/2.6 prompt exceeds 32000 characters")
    if files and urls:
        raise ValueError("Use image tensor(s) or reference URLs, not both")
    limit = reference_limit(model)
    if max(len(files), len(urls)) > limit:
        raise ValueError("Too many reference images for model")
    if f!="hc_native" and (background or output_format):raise ValueError("该模型不支持background/output_format覆盖")
    urls = [public_reference(url, https_only=f != "aistars",max_length=8192 if f=="hc_native" else 2048) for url in urls]
    if f=="hc_native":
        spec=HC_NATIVE[model]
        if image_size:raise ValueError("HC新型号使用像素宽高，不使用清晰度档")
        if size and (not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*",size) or int(size.split('x')[0])*int(size.split('x')[1])>=8294400):raise ValueError("HC新型号总像素必须严格小于8294400")
        if quality and quality not in spec['qualities']:raise ValueError("该HC型号不支持此quality")
        if background and background not in ('auto','transparent','opaque'):raise ValueError("不支持此background")
        if output_format and output_format not in spec['formats']:raise ValueError("该HC型号不支持此output_format")
        if background=='transparent' and output_format not in ('png','webp'):raise ValueError("透明背景必须显式选择png或webp")
        if any(urlsplit(url).fragment for url in urls):raise ValueError("HC参考图URL不能含片段")
        body={'model':model,'prompt':prompt,'n':1}
        body.update({k:value for k,value in (('size',size),('quality',quality),('background',background),('output_format',output_format)) if value})
        if files:
            if not defer_upload:raise ValueError("HC新型号仅支持公网参考图URL")
            if any(not b or len(b)>32*1024**2 for b in files):raise ValueError("ImgBB参考图每张不得超过32MiB")
            return spec['path']+'/v1/images/edits',body,{'imgbb_files':list(files),'image_field':'image'}
        if urls:body['image']=urls[0] if len(urls)==1 else urls
        return spec['path']+'/v1/images/'+('edits' if urls else 'generations'),body,None
    if f == "aistars":
        spec = AISTARS[model]
        if files and defer_upload:
            if any(not b or len(b)>32*1024**2 for b in files):
                raise ValueError("ImgBB参考图每张不得超过32MiB")
            path,body,_=build_request(model,prompt,size,quality,image_size,(),["https://i.ibb.co/pending.png"]*len(files))
            return path,body,{"imgbb_files":list(files)}
        if files:
            raise ValueError("此模型参考图需公网 HTTPS URL，请断开 IMAGE 并填写 reference_urls；API 未提供文件上传接口")
        if quality or size not in spec["ratios"] or image_size not in spec["resolutions"]:
            raise ValueError("该模型需要支持的比例和清晰度；不支持像素宽高或 quality")
        body = {"model":model,"prompt":prompt,"aspect_ratio":size,"resolution":image_size,"n":1}
        if urls:body["images"]=list(urls)
        return "/aistars/v1/images/" + ("edits" if urls else "generations"), body, None
    if f == "sync":
        if urls or image_size:
            raise ValueError("SR/FULL 使用像素宽高和 IMAGE 文件输入，不支持 URL 或清晰度档")
        m = re.fullmatch(r"([0-9]{1,5})x([0-9]{1,5})", size)
        auto = size == "auto" and SYNC[model].get("auto")
        if not m and not auto:
            raise ValueError("SR/FULL size 必须是宽x高像素")
        w,h=map(int,m.groups()) if m else (1024,1024)
        if min(w,h)<=0 or w%16 or h%16 or max(w,h)>3840 or max(w,h)/min(w,h)>3 or not 655360<=w*h<=8294400:
            raise ValueError("Invalid SR/FULL pixel dimensions")
        if quality and quality not in SYNC[model]["qualities"]:
            raise ValueError("Unsupported quality for model")
        if SYNC[model].get("max_file_bytes_exclusive") and any(not b or len(b)>=52428800 for b in files):
            raise ValueError("W reference must be less than 50 MiB")
        body={"model":model,"prompt":prompt,"size":size,"n":1}
        if model.endswith("-W"):body["output_format"]="png"
        if quality: body["quality"]=quality
        if not files: return "/v1/images/generations",body,None
        fields=[(k,str(v)) for k,v in body.items()]
        uploads=[("image" if len(files)==1 else "image[]",(f"reference-{i}.png",b,"image/png")) for i,b in enumerate(files)]
        return "/v1/images/edits",fields,uploads
    if image_size and image_size not in ("1K", "2K", "4K"):
        raise ValueError("Resolution tier must be 1K/2K/4K")
    allowed_quality = ("auto", "low", "medium", "high")
    if f == "kr25" or model in ("s-gpt-image-2.5-flare", "s-gpt-image-2.5-sunburst"):
        allowed_quality += ("xhigh", "max")
    if quality and quality not in allowed_quality:
        raise ValueError("Unsupported quality for model")
    if f == "gemini":
        if urls:
            raise ValueError("Banana references require IMAGE inputs (inlineData), not URLs")
        if quality or (size and size not in ratios(model)):
            raise ValueError("Banana uses aspect ratio and imageSize; quality/pixel size unsupported")
        if any(len(b) > 12 * 1024**2 for b in files):
            raise ValueError("Banana reference exceeds 12 MiB")
        encoded = [base64.b64encode(b).decode("ascii") for b in files]
        if sum(map(len, encoded)) > 64 * 1024**2:
            raise ValueError("Banana base64 references exceed 64 MiB")
        parts = [{"text": prompt}] + [{"inlineData": {"mimeType": "image/png", "data": b}} for b in encoded]
        body = {"model": model, "contents": [{"role": "user", "parts": parts}]}
        cfg = {k: v for k, v in (("aspectRatio", size), ("imageSize", image_size)) if v}
        if cfg:
            body["generationConfig"] = {"imageConfig": cfg}
        return "/kr/gemini/v1/images/generations", body, None
    if f == "kr25" and (image_size or (size and size != "auto" and not re.fullmatch(r"[0-9]{1,5}x[0-9]{1,5}",size))):
        raise ValueError("KR GPT 2.5/2.6 requires auto or pixel dimensions, not ratio/tier")
    if files and f == "kr25":
        if any(not b or len(b)>=50*1024**2 for b in files) or sum(map(len,files))>=128*1024**2:
            raise ValueError("KR GPT 2.5/2.6 upload limit exceeded")
    elif files:
        if any(not b or len(b) > 10 * 1024**2 for b in files) or sum(map(len, files)) > (50 if f == "hc" else 64) * 1024**2:
            raise ValueError("Reference upload exceeds model file/total limit")
    if f == "hc" and image_size:
        raise ValueError("HC does not support image_size")
    if size:
        m = re.fullmatch(r"([0-9]{1,5})x([0-9]{1,5})", size)
        if f == "hc":
            if not m or min(map(int, m.groups())) < 1 or int(m[1]) * int(m[2]) >= 8294400:
                raise ValueError("HC size requires WIDTHxHEIGHT, pixels < 8,294,400")
        elif size not in RATIOS and size != "auto":
            if not m:
                raise ValueError("KR size requires auto, supported ratio or WIDTHxHEIGHT")
            w, h = map(int, m.groups())
            if min(w, h) <= 0 or w % 16 or h % 16 or max(w, h) > 3840 or max(w, h) / min(w, h) > 3 or not 655360 <= w*h <= 8294400:
                raise ValueError("Invalid KR pixel dimensions")
    body = {"model": model, "prompt": prompt, "n": 1}
    body.update({k: v for k, v in (("size", size), ("quality", quality), ("image_size", image_size)) if v})
    if f in ("kr","kr25"):
        body["response_format"] = "url"
    if not files and not urls:
        return f"/{'kr/gpt' if f=='kr25' else f}/v1/images/generations", body, None
    if f == "hc" and urls:
        body["image"] = urls[0] if len(urls) == 1 else urls
        return "/hc/v1/images/edits", body, None
    fields = [(k, str(v)) for k, v in body.items()]
    if urls:
        fields += [("image_url" if len(urls) == 1 else "image_url[]", u) for u in urls]
    file_field = "image[]" if f in ("kr","kr25") and len(files) > 1 else "image"
    uploads = [(file_field, (f"reference-{i}.png", b, "image/png")) for i, b in enumerate(files)]
    return f"/{'kr/gpt' if f=='kr25' else f}/v1/images/edits" + ("/upload" if f == "hc" else ""), fields, uploads
