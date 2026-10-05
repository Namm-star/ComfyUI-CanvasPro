# 2026-10-05 协议依据与扩展边界

本轮用无凭据 GET 重新读取以下公开资料，没有读取管理员私有凭据或修改生产：

- https://api.canvasproai.com/api/pricing：104 款可见模型；当前六款图片路由包含 KR、KR Gemini、HC 生成/编辑/文件上传/查询。目录中的泛用 `openai` 标签不能推导图片/视频支持 Chat。
- https://api.canvasproai.com/source/：当前公开源码 SHA256 `de9f4bf5283ea4e98bb540ebef137fb032a29c0047e7849ebfea19d6955fa703`；页面声明 Native SHA256 `0abb0b5b32b0d22657d678d8bfa98af1535a7d059864b45b3336191464408fc7`。这是公开制品声明，不是独立服务器二进制审计。
- https://api.canvasproai.com/api/status：共享钱包标志 true，`version=v0.0.0` 无法作为提交 SHA；不用它推导最新版本。
- https://api.canvasproai.com/client/seedance/catalog.json：90 款算力 AI 视频能力；版本 `20261001-0b2147c4d8a9`、插件 0.3.1。不同型号具有各自档位、时长、比例和参考媒体组合限制。

本机只读资料：CanvasPro-api-relay-v2 的 `AGENTS.md`、生产里程碑、原生目录导入记录、接入指南、用户模型指南及 KR/HC 任务插件。里程碑首段的 10-05 财务修复是未发布候选，不能把候选当生产；没有使用 `new-api-main` 旧原版源码。本轮六款路由与公开目录一致，完整参数依据现行用户指南和本机任务插件；未独立鉴权读取线上活动插件源，也未声称逐参数已付费验证。

## 图片合同

| 型号/协议 | 生成 | 编辑/参考图 | 查询 | 限制 |
| --- | --- | --- | --- | --- |
| gpt-image-2 / KR | POST `/kr/v1/images/generations` JSON | POST `/kr/v1/images/edits` multipart | GET `/kr/v1/images/tasks/{task_id}` | prompt≤4000 UTF-16 单元，n=1，response_format=url；1–16 参考图，PNG/JPEG/WebP，单文件≤10 MiB、合计≤64 MiB；文件与公网 HTTPS URL 二选一 |
| T香蕉2、T香蕉pro / KR Gemini | POST `/kr/gemini/v1/images/generations` Gemini JSON | 同一入口，parts 中 inlineData | GET `/kr/gemini/v1/images/tasks/{task_id}` | 一个 role=user contents；1–32 parts；本插件一个 text≤8000 UTF-16 单元；≤14 图，单图≤12 MiB，base64合计≤64 MiB |
| 三款 s-gpt-image / HC | POST `/hc/v1/images/generations` JSON | URL JSON `/hc/v1/images/edits`；文件 multipart `/hc/v1/images/edits/upload` | GET `/hc/v1/images/tasks/{task_id}` | prompt≤8000 UTF-16 单元，n=1；1–15 图，单图≤10 MiB，合计≤50 MiB，请求体≤52 MiB |

KR：一图文件字段 `image`，多图重复 `image[]`；一 URL 字段 `image_url`，多 URL 重复 `image_url[]`。HC：所有文件重复字段 `image`；URL 字段 `image` 为字符串或数组。PNG 由节点编码，真实上传含正确 MIME/文件名，requests 创建 boundary。

KR `size`：auto、支持比例或像素格式；像素宽高须为16倍数，长边≤3840，比例≤3，总像素655360–8294400。KR 渠道扩展 `image_size=1K/2K/4K` 与比例组合由 KR 判定；quality=auto/low/medium/high。本插件只列明确五比例，其他渠道比例未扩展。

香蕉：generationConfig.imageConfig.aspectRatio=1:1/3:4/4:3/9:16/16:9，imageSize=1K/2K/4K；不传顶层 size/quality。inlineData.data 为无前缀 base64，mimeType=image/png。

HC：size 为正像素 WIDTHxHEIGHT，总像素严格小于8294400；基本 quality=auto/low/medium/high，flare/sunburst 额外支持 xhigh/max；不传 image_size。HC 文件上传由本站生成上游限时读取链接，参考文件正常约3–3.5小时后清理，这不是客户端上传到画布用户资产。

所有图片任务：提交返回 `task_id`；查询当前状态 queued/processing/succeeded/failed（unknown 保留非终态）；成功 `data[0].url`。没有服务端批量端点或已确认幂等键；插件批量是多次独立 POST。HTTP错误不能普遍证明上游未执行，客户端保守保存未知结果。

## 文本和视频扩展接口

`capabilities.json` 是只读扩展登记，未连接执行节点。`protocol.py` 的 `family/build_request/query_path` 是图片协议入口；`batch.py` 管调度，`store.py` 管本地意图，`client.py` 提供单次 POST、GET 与鉴权下载。

- 文本当前四款 gpt-6.1-sol/gpt-5.6-sol/gpt-6-astra/gpt-6-sol：公开支持 POST `/v1/chat/completions`、`/v1/responses`。后续独立文本适配器需处理同步/流式返回、用量与字符串输出，不能套图片任务状态。这个清单来自本轮公开目录，不来自旧 Codex++。
- HC 中文视频四款：POST `/hc-cn/v1/video/tasks`、GET `/hc-cn/v1/video/tasks/{task_id}`。成功 video_url 可是本站 `/v1/tasks/{task_id}/artifacts/video/content`，同站下载携带本站 Key；跨站不得转发 Key。精确四个中文名称见能力快照，不裁掉“官转”前缀。
- 算力 AI 90 款：POST `/suanli/v1/videos`、GET `/suanli/v1/videos/{task_id}`；条件参数以版本化公网 catalog 为准。后续需按各 variants 校验分辨率、时长、比例、媒体类型/数量及组合，不能用通用固定参数一键适配全部型号。
- 视频输出需要专用媒体类型/本地文件与下载缓存；不得将 MP4 填 IMAGE 或猜测现有 ComfyUI VIDEO 构造 API。视频上传上限、轮询输出映射、终态费用不能从图片合同外推。

后续发布前重新读取目录、核对路径与活动协议，再做独立无费合同测试；真实生成需另有明确授权及预算。
