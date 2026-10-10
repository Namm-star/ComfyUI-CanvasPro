"""CanvasPro native image contracts updated 2026-10-10; see docs evidence."""
import base64
import re
import json
from pathlib import Path
from urllib.parse import urlsplit

IMAGE_MODELS = json.loads((Path(__file__).with_name("image_models.json")).read_text(encoding="utf-8"))
AISTARS = IMAGE_MODELS["aistars"]
MODELS = ("gpt-image-2", "T香蕉2", "T香蕉2.1", "T香蕉pro", "s-gpt-image-2", "s-gpt-image-2.5-flare", "s-gpt-image-2.5-sunburst", *AISTARS)
RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9")

def ratios(model):
    return tuple(AISTARS[model]["ratios"] if model in AISTARS else IMAGE_MODELS["banana_ratios"].get(model, RATIOS))

def reference_limit(model):
    return AISTARS[model]["references"] if model in AISTARS else {"kr":16,"hc":15,"gemini":14}[family(model)]


def family(model):
    if model not in MODELS:
        raise ValueError("Unsupported model; consult protocol evidence before extending registry")
    return "aistars" if model in AISTARS else "gemini" if model.startswith("T香蕉") else "hc" if model.startswith("s-") else "kr"


def query_path(model, task_id):
    from urllib.parse import quote
    if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
        raise ValueError("Invalid task ID")
    if family(model) == "aistars":
        return "/aistars/v1/tasks/" + quote(task_id, safe="")
    prefix = {"gemini": "/kr/gemini", "hc": "/hc", "kr": "/kr"}[family(model)]
    return prefix + "/v1/images/tasks/" + quote(task_id, safe="")


def public_reference(url):
    u = urlsplit(url)
    host = u.hostname or ""
    if (u.scheme != "https" or u.username or u.password or u.port not in (None, 443)
            or "." not in host or host.endswith((".local", ".localhost"))
            or re.fullmatch(r"[\d.]+", host) or ":" in host or len(url) > 2048):
        raise ValueError("Reference URLs must be public HTTPS domain URLs")
    return url


def build_request(model, prompt, size="", quality="", image_size="", files=(), urls=()):
    f = family(model)
    prompt = prompt.strip()
    # JavaScript contract limits UTF-16 units, not Python Unicode code points.
    if not prompt or len(prompt.encode("utf-16-le")) // 2 > (4000 if f == "kr" else 5000 if f == "aistars" else 8000):
        raise ValueError("Prompt empty or exceeds model text limit")
    if files and urls:
        raise ValueError("Use image tensor(s) or reference URLs, not both")
    limit = reference_limit(model)
    if max(len(files), len(urls)) > limit:
        raise ValueError("Too many reference images for model")
    urls = [public_reference(url) for url in urls]
    if f == "aistars":
        spec = AISTARS[model]
        if files:
            raise ValueError("此模型参考图需公网 HTTPS URL，请断开 IMAGE 并填写 reference_urls；API 未提供文件上传接口")
        if quality or size not in spec["ratios"] or image_size not in spec["resolutions"]:
            raise ValueError("该模型需要支持的比例和清晰度；不支持像素宽高或 quality")
        body = {"model":model,"prompt":prompt,"aspect_ratio":size,"resolution":image_size,"n":1}
        if urls:body["images"]=list(urls)
        return "/aistars/v1/images/" + ("edits" if urls else "generations"), body, None
    if image_size and image_size not in ("1K", "2K", "4K"):
        raise ValueError("Resolution tier must be 1K/2K/4K")
    allowed_quality = ("auto", "low", "medium", "high")
    if model in ("s-gpt-image-2.5-flare", "s-gpt-image-2.5-sunburst"):
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
    if files:
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
    if f == "kr":
        body["response_format"] = "url"
    if not files and not urls:
        return f"/{f}/v1/images/generations", body, None
    if f == "hc" and urls:
        body["image"] = urls[0] if len(urls) == 1 else urls
        return "/hc/v1/images/edits", body, None
    fields = [(k, str(v)) for k, v in body.items()]
    if urls:
        fields += [("image_url" if len(urls) == 1 else "image_url[]", u) for u in urls]
    file_field = "image[]" if f == "kr" and len(files) > 1 else "image"
    uploads = [(file_field, (f"reference-{i}.png", b, "image/png")) for i, b in enumerate(files)]
    return f"/{f}/v1/images/edits" + ("/upload" if f == "hc" else ""), fields, uploads
