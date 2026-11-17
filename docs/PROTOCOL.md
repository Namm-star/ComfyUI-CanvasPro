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
| T香蕉2、T香蕉2.1、T香蕉pro / KR Gemini | POST `/kr/gemini/v1/images/generations` Gemini JSON | 同一入口，parts 中 inlineData | GET `/kr/gemini/v1/images/tasks/{task_id}` | 一个 role=user contents；1–32 parts；本插件一个 text≤8000 UTF-16 单元；≤14 图，单图≤12 MiB，base64合计≤64 MiB |
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

## 2026-10-08：T香蕉2.1

无凭据 GET 公开 `/api/pricing` 确认 T香蕉2.1 已上架，声明生成/查询使用 KR Gemini 路径、支持 inlineData 参考图、最多14图、1K/2K/4K、单次输出1图。目录字段摘录见 [T-BANANA-2.1.json](T-BANANA-2.1.json)。其余请求结构沿用现有香蕉协议，新增型号通过本地模拟接口完成文生图、多图编辑、查询和结果下载验证；没有调用付费生产生成。

## 2026-10-10：24款图片模型与香蕉比例

依据公开 /api/pricing 与 /source/ 发布包；选定源码路径、包SHA256和型号合同记录于 [IMAGE-CONTRACTS-20261010.json](IMAGE-CONTRACTS-20261010.json)。17款新增即梦型号：POST /aistars/v1/images/generations 或 /aistars/v1/images/edits，JSON model/prompt/aspect_ratio/resolution/n=1；编辑 images 为公网URL数组。未确认文件上传接口，不自动上传本地图片。提交返回id，GET /aistars/v1/tasks/{id}，completed终态 artifacts[].content_url 指向本站 /v1/tasks/{id}/artifacts/{artifact}/content；单图任务验证恰好一件制品。同站下载带Key，跨站仍禁止转发。

香蕉pro支持10种比例；香蕉2/2.1支持14种，详见image_models.json。新型号的比例、档位、最大URL数量按公开源登记独立校验；prompt≤5000 UTF-16单元。新增协议仍保持POST单次提交、持久化恢复、失败不自动重提交。此次使用本地模拟HTTP与真实ComfyUI加载验证，未调用付费生产生成。


## 2026-11-11 文档合同更新（0.10.0）

来源摘要与 SHA256 见 IMAGE-CONTRACTS-20261111.json；新版覆盖此前合同。

图片模型更新（0.10.0 / 文档2026-11-11）：共34款。
SR/FULL：/v1/images 同步返回，不轮询；使用整数宽高，16倍数、最长边≤3840、总像素655360–8294400、长短边≤3。参考图接 IMAGE，最多16张，不支持 reference_urls。quality 按型号选择，GPT Image 2-SR 不支持xhigh/max。同步请求超时或结果未知不会自动重提；相同批次恢复已有结果。
即梦新增：即梦-23-gemini-nano-banana-2.1；参考图在 reference_urls 每行填写一个公网HTTP(S)地址，不接IMAGE。所有18款即梦仅支持16:9、9:16、1:1、4:3、3:4。Seedream Pro 1K/2K，Lite 2K/4K，其余1K/2K/4K。
KR香蕉：T香蕉pro为10种比例；T香蕉2/2.1为14种，额外支持1:4、4:1、1:8、8:1；仍用IMAGE参考图与1K/2K/4K。
API Key申请：https://api.canvasproai.com/keys ；直接填写批量执行节点。report与tasks_json已连接日志显示。
同步返回支持 data[0].url 或 data[0].b64_json。Base64验证图片后保存至本地SQLite二进制列，不写入任务句柄或日志。同步POST最多一次，超时和不完整响应记为submit_unknown；查询节点跳过没有远程任务号的同步结果。同步POST等待120秒；异步仍遵循节点request_timeout。


## 2026-11-14 最新合同（0.11.0）

0.11.0 · 2026-11-14 最新图片合同：45款（文档首页旧统计32款尚未同步，按逐型号合同与在线目录核对）。
新增KR GPT 2.5/2.6 Flare、Sunburst：/kr/gpt/v1/images 异步接口；像素宽高或auto，不能传比例或image_size。质量支持auto/low/medium/high/xhigh/max，提示词最多32000字符，文件或URL参考图二选一，最多16张。
新增四款-W：同步Images接口，像素宽高或auto；参考图仅接IMAGE，不支持URL编辑；4K为超分输出，非原生4K。结果下载不携带API Key。
新增即梦2.6 Flare High、Sunburst High：1K/2K/4K；Seedream 5.5仅2K。即梦参考图填reference_urls，每行一个公网HTTP(S)地址，最多6张（其他型号上限依各型号合同）。
宽高均为16的倍数、最长边≤3840、总像素655360–8294400、长短边≤3。KR 2.5/2.6 超过3686400像素属于实验大尺寸，不保证严格尺寸。
提交不自动重试；同job_key与seed恢复已保存结果。修改输入或另生成一张，请换seed。report与tasks_json已连接日志。
Key申请：https://api.canvasproai.com/keys ；直接填写批量执行节点。
来源与SHA256、逐型号合同见IMAGE-CONTRACTS-20261114.json。KR25成功后下载本站/v1/tasks/{task_id}/artifacts/image-1/content，必须携带本站Key；W返回URL下载不携带Key。


## ImgBB 参考图上传（0.12.0 / 2026-11-15）

ImgBB临时参考图（0.12.0）：即梦现在可直接连接加载图像的IMAGE端口，接满后自动增加，按型号上限停止。
本地参考图会自动上传ImgBB后交给即梦，公开直链在上传3小时后由图床自动删除（expiration=10800秒），不会永久保存。任务等待超过3小时后原参考图可能不可用。
ImgBB Key内置在Python后端，不增加图床密码框；用户只需填写自己的CanvasPro Key。
IMAGE与reference_urls二选一；URL方式不会上传ImgBB。图床上传失败会阻止该任务生图，report显示原因。
同批相同图片只上传一次；同job_key与seed恢复原任务，不重新上传、不重复提交。修改输入或另出一张时更换seed。
上传文件每张≤32MiB，参考图按端口顺序对应图1、图2。
官方合同：https://api.imgbb.com/ ；POST https://api.imgbb.com/1/upload，表单key/expiration=10800，文件image；仅使用data.url原图直链，校验success、expiration，忽略delete_url。上传不重试，不跟随重定向，不带CanvasPro鉴权。测试图实际上传已验证10800秒回执；不声称已经等待3小时验证物理删除。


## 共用图床（0.12.1）

按维护者要求，插件内置共用ImgBB Key。用户只需填写自己的CanvasPro API Key，即梦IMAGE参考图默认使用共用图床，上传后3小时自动删除（expiration=10800）。界面不显示图床Key输入框。随客户端分发的共用Key可被提取，此方式不是密钥保护。Key不进入任务句柄或运行日志。


## 同步结果与保存修复（0.12.2）

同步图片恢复（0.12.2）：W/SR/FULL同步接口默认等待600秒。批量执行的advanced中可调整sync_timeout（1–3600秒），wait_seconds用于异步任务轮询，不替代同步等待。
没收到图片时只阻止图片分支，保存节点跳过，report/tasks_json正常显示超时或下载错误，不生成占位图。
同步下载成功后缓存本地图片；原job_key和seed保持不变并设fixed，可恢复结果或重试原URL下载，不重新生图。
submit_unknown且没有原始URL/Base64/任务号时，插件无法凭空恢复结果，请从平台记录获取原图；不要自动换seed重提。连接或上游网关仍可能提前中断，延长等待不承诺必定返回。


## 再次获取结果（0.13.0）

结果再次获取（0.13.0）：新增“CanvasPro · 再次获取结果（不重新生图）”节点。
请另开专用结果恢复工作流，或只执行恢复节点，避免同时运行原提交工作流。将原 report / tasks_json 整段粘贴到 recovery，或填写 batch_id / effective_job_key；填自己的CanvasPro Key，images连接保存图像，再次运行仅查询/下载原任务，不重新提交。
异步原网址失效时可启用refresh_urls，尝试从原任务号重新获取网址；平台若未保留制品仍可能无法恢复。
同步已保存URL时可重试下载，收到Base64或下载成功后优先用本地缓存；没有收到任何结果的同步请求无法补查。
日志包含resource_urls（完整资源网址）、task_id、cached_image及resources[].requires_api_key。需要鉴权的本站网址要用原账户有效Key下载；签名网址可能过期，分享日志前删除资源网址。
恢复依赖原电脑的本地任务数据库，请保留user/canvaspro。所有型号成功下载后均缓存图片；只查看日志时不加载图片二进制。


## 简洁生成节点（0.14.0 / 2026-11-17）

CanvasProImageGenerate复用PromptTask的参数校验与BatchExecute的提交、查询、缓存、图床和恢复实现；仅提供新的统一输入界面，全部接口仍为CanvasPro。参考GrsAI项目的单节点使用方式重新实现，没有使用其服务端地址或要求GrsAI Key。

count=1–8，每张是n=1的独立收费任务，完整多行prompt不会按行拆分。concurrency默认3，高级设置可调1–8。输入与节点标识的SHA256自动构建job_key；批次seed仍通过现有执行器参与幂等键。fixed+相同输入恢复；改变提示词、模型、参数、参考图、count或seed创建新收费任务。seed不是上游图像随机种子，不保证画面复现。

新节点名称独立，旧节点schema不变。前端仍复用精确型号合同、自动参考图端口、数字宽高/连线覆盖和密码框。三份简洁界面示例与simple-api.json均不包含用户CanvasPro Key。结果失败输出与再次获取方式和原批量模式一致，不自动重试POST。


## 异步分步提交与累计队列（0.15.0）

[异步分步工作流](examples/异步分步工作流-Async-Two-Step.json)

异步分两步：
1. 提交节点与批量查询节点填写同一queue_key（默认queue-001），两个节点都填写自己的CanvasPro API Key。
2. 保持提交节点启用，连续运行一次、两次、三次；seed的生成后控制设randomize，每次提交加入新任务。fixed且输入相同不会重复收费，也不会重复加入队列。
3. 提交结束后，将“异步提交”节点设为禁用/从不（mode 2），再运行工作流；批量查询会获取同队列历次提交的全部任务并下载。
同一队列的提交节点仍启用时，查询节点自动跳过，保存图片也会跳过，不会在提交阶段等待生成。
查询可反复运行，尚未完成或下载失败时继续查询；成功图片优先读取缓存，原网址过期可勾选refresh_urls续查原任务。
队列保存在本机user/canvaspro，重启后仍保留。要开始另一批任务使用新的队列名；查询不清空旧队列。
异步提交仅列出能返回任务号的型号；W/SR/FULL同步型号仍使用简洁生图。参考图自动处理，需图床时使用内置ImgBB，3小时后删除。
不需要复制、合并多个task_id。report含批次、原任务号及资源网址，分享日志前删除临时网址。


## 查询界面说明（0.15.1）

队列查询界面（0.15.1）：默认隐藏model，queue_key会查询该队列的全部模型，不按下拉框筛选。tasks_json标为“单独任务（可选，留空查询整个队列）”；留空或完整JSON/批次编号时隐藏型号，仅手工填写平台任务号时显示“手动任务号对应模型”。字段只隐藏，旧工作流序列化位置和后端兼容性保留。


## 提交状态核对（0.15.2）

提交回执与状态（0.15.2）：ComfyUI节点绿色只代表节点执行结束，不代表平台创建了新任务。
报告submission.mode为new_batch或restored_existing；new_post_attempts是本次尝试调用生成接口的次数，不证明服务器收到；new_acknowledged是本次收到平台任务号/同步图片回执的数量。复用旧批次会明确显示“本次未新建”，次数为0。
每项submission_receipt记录endpoint、attempted_at（UTC）、http_status、request_id（平台响应头提供时）及acknowledgement；task_id才是平台任务号，batch_id是本地批次号。
固定seed且输入相同会复用旧任务，不再POST；提交失败或结果未知时不再显示固定的“任务已提交”。只有收到有效任务号才显示“平台返回任务号”，并注明非生成完成。
没收到任务号不能认定成功，也不能认定平台绝未受理。图床失败不会提交生成请求。若已有平台任务号但后台找不到，按任务号、请求编号、接口路径、时间和相同账号核对API侧记录。旧记录不会凭空补出历史HTTP回执。


## 单次查询与提交错误（0.15.3）

队列批量查询每次只获取一轮当前状态，不再等待任务完成。排队/处理中会返回日志，稍后再次运行查询；已完成的任务会下载图片。旧工作流保存的wait_seconds（包括600）已停用并隐藏，不会恢复轮询。request_timeout是单次网络请求的超时，查询和下载仍需网络耗时。再次获取结果、批量执行等其他节点的等待设置保持原有行为。

提交异常会区分连接、代理、TLS、超时、非JSON响应和任务号缺失，回执保留收到的HTTP状态。未取得平台任务号显示“未取得平台任务号”，不会声称已受理；提交标题也从节点返回结果更新，避免仅依赖状态推送。连接或响应中断时服务端是否已受理仍可能未知，不自动重提收费。图片编辑与文生图独立保存，即使队列和seed相同也不会互相覆盖。已确认无平台任务后，可更换seed发起新提交。

异步分步示例已分别连接提交report/tasks_json和查询report/tasks_json。升级后必须重启ComfyUI并强制刷新浏览器，磁盘更新不会替换正在运行的旧Python模块。
