# ComfyUI CanvasPro 0.15.5

推荐使用新增的 **简洁生图 → 保存图像** 模式：一个节点完成文生图、多图编辑及1–8张并发出图，继续使用CanvasPro API。原批量模式及结果恢复节点保持兼容。

- [简洁文生图](examples/简洁文生图-Simple-Text-to-Image.json)
- [简洁多图编辑](examples/简洁多图编辑-Simple-Multi-Image-Edit.json)
- [简洁多张并发](examples/简洁多张并发-Simple-Multi-Image-Batch.json)

简洁节点不需要手动填写job_key。fixed且全部输入相同会恢复缓存；修改提示词、模型、参考图、count或seed会创建新的收费任务。seed仍是批次标识，不是上游图像随机种子。三个新示例已连接report/tasks_json日志，Key留空，填写自己的CanvasPro Key即可。


**独立任务 → 批量执行 → 保存图像**。支持完整多行提示词、混合模型、自动增加任务及参考图入口。每批最多 256 个任务，提交并发数 1～8；重复运行同一批次不会重新提交收费。

## 最新示例工作流

原批量模式示例继续保留：

- [普通多任务](examples/多任务并发-Multi-Task-Batch.json)：多个独立任务直接连接批量执行，无需合并节点。
- [混合模型](examples/混合模型并发-Mixed-Model-Batch.json)：GPT Image、香蕉、SR 同步和即梦 Seedream 四个任务一起执行。
- [多图编辑](examples/多图编辑-Multi-Image-Edit.json)：两张参考图连接一个完整提示词任务，再连接批量执行；先选择自己的图片。

下载对应 JSON 后拖入 ComfyUI。已安装用户先更新插件、重启 ComfyUI，再刷新浏览器。更多说明见 [示例目录](examples/README.md)。`optimized-api.json` 是 API 格式，界面导入请使用上面三个双语文件名 JSON。

## 使用

每个「独立任务 / 完整提示词」节点只写一条完整提示词，换行会保留。任务节点自行选择模型和尺寸；参考图入口接满后自动增加，按模型上限停止。多个任务分别连接「批量执行」的 `task_1`、`task_2` 等入口；接满后自动出现下一入口。任务及图片按端口编号排序。

批量执行完成提交、等待和下载，输出图片直接连接保存图像。默认显示批次名称 `job_key`、并发数和高级设置开关。高级设置可调整等待时间（默认 600 秒）、请求超时（默认 30 秒）；任务质量和 URL 参考图也放在高级设置中。香蕉只显示比例与 1K/2K/4K 等支持的参数。GPT Image 最多 16 张参考图、香蕉最多 14 张、HC 最多 15 张；不同尺寸参考图不合并缩放。

同一个 `job_key` 和相同内容再次运行会继续原任务；改动提示词、模型、参数、参考图或任务顺序后需要新的批次名称。任务名称冲突会在提交前报错。执行标题显示阶段及排队/处理中/成功/失败数量，报告提供模型和图片对应索引。失败任务不生成占位图片，成功图片保留各自尺寸。

## 安装

### 从 GitHub 安装

进入实际 ComfyUI 源码目录的 `custom_nodes`，执行：

```powershell
git clone https://github.com/Namm-star/ComfyUI-CanvasPro.git
```

本机路径示例：

```powershell
cd F:\ComfyUI\ComfyUI\ComfyUI\custom_nodes
git clone https://github.com/Namm-star/ComfyUI-CanvasPro.git
```

随后按下方步骤检查依赖、配置本站 Key 并重启。已安装后进入插件目录执行 `git pull --ff-only` 更新；保留本地 Key 和数据目录。也可在 [GitHub 仓库](https://github.com/Namm-star/ComfyUI-CanvasPro) 选择 Code → Download ZIP 后手动解压，文件夹命名为 `ComfyUI-CanvasPro`。

### 手动安装与依赖

1. 解压发布 ZIP，把整个 `ComfyUI-CanvasPro` 文件夹放进**实际 ComfyUI 源码目录**的 `custom_nodes`。
2. 使用启动 ComfyUI 的同一个 Python 检查 `import requests, PIL, numpy, torch`。通常这些包已有；只有缺依赖时才使用该 Python 执行 `-m pip install -r custom_nodes/ComfyUI-CanvasPro/requirements.txt`。不要升级或重装整套 ComfyUI，也不要用系统 Python 替代运行环境。
3. 配置 Key，然后重新启动 ComfyUI。搜索 `CanvasPro`，应出现 11 个节点。

本机找到的实际源码目录是 `F:\ComfyUI\ComfyUI\ComfyUI`，Python 是 `F:\ComfyUI\ComfyUI\python\python.exe`；外层 `F:\ComfyUI\ComfyUI` 是启动器目录。交付时未复制插件到现有安装，也未改其配置。其他机器请核对自己的路径。

## API Key

直接在「批量执行」节点的 `api_key` 中填写本站 Key，输入遮蔽显示，无需运行配置脚本。节点 Key 优先；留空时仍可使用原有环境变量/Key 文件配置。

`job_key` 是批次名称，例如 `batch-001`，不要填 Key。工作流保存、API 请求和生成图片元数据可能包含节点中的 Key；分享工作流或图片前清除 Key。可选的服务端 Key 配置仍支持原有 `configure-key.ps1`。

## 恢复已有任务

批次保存在 ComfyUI 用户目录的 `canvaspro/tasks.sqlite3`（可用 `CANVASPRO_DATA_DIR` 指定），不保存 Key、提示词或原参考图。数据库可能含临时结果 URL，请保存在自己的本地目录。

重启或等待超时后，保持原批次名称及内容再次运行即可继续查询，不会重发提交。也可手动连接「恢复本地批次」→「等待并获取图片」→「保存图像」。这些兼容节点仍保留，但不再提供旧流程示例。

提交结果不确定会记录为 `submit_unknown`，不自动重试 POST；先核对本站任务记录，找到任务号后用「导入已有任务号」继续查询。取消客户端等待不会取消已提交的服务端任务。旧工作流与旧批次数据库保持兼容。

## 验证

```powershell
& 'F:/ComfyUI/ComfyUI/python/python.exe' -m unittest discover -s tests -v
node --test tests/*.test.mjs
& 'F:/ComfyUI/ComfyUI/python/python.exe' tests/comfy_load_check.py 'F:/ComfyUI/ComfyUI/ComfyUI'
```

23 项本地模拟 HTTP 集成测试、11 项前端逻辑测试通过；真实 ComfyUI 已验证混合模型节点执行、API 示例及不同尺寸图片保存。示例连线和类型已检查。未使用生产 Key，未发送付费请求。

支持24款图片模型：`gpt-image-2`、`T香蕉2`、`T香蕉2.1`、`T香蕉pro`、三款 `s-gpt-image`，以及17款即梦 GPT Image、Gemini 和 Seedream 型号。完整新型号及参数见 [模型能力](image_models.json)和[协议记录](docs/PROTOCOL.md)。视频和文本执行节点尚未实现。

参考项目及许可见 [第三方声明](THIRD_PARTY_NOTICES.md)。

## GPT Image 宽高填写

像素模式分开填写 width（宽）和 height（高），悬停可查看尺寸备注。

| 示例 | 宽 | 高 |
| --- | --- | --- |
| 1K 正方形 | 1024 | 1024 |
| 2K 正方形 | 2048 | 2048 |
| 4K 横图 | 3840 | 2160 |
| 4K 竖图 | 2160 | 3840 |

1K/2K/4K 是分辨率档位的常用称呼，不是所有比例都填相同宽高。GPT 像素模式要求16倍数、单边不超过3840、总像素655360～8294400、长宽比不超过3；4096×4096不支持。要按档位生成，请切换 ratio（比例）模式，选择比例和 image_size=1K/2K/4K。香蕉继续使用比例和档位。旧像素字符串工作流导入时自动迁移到宽高。

所有界面示例右侧已加入内置 Note 注释节点，列出 1:1、2:3、3:2、3:4、4:3、16:9、9:16 的尺寸参考及上述限制。2:3、3:2 使用像素模式填写宽高。

### 0.8.0

前端改为单个自包含脚本，节点定义在创建前收起多余端口。默认显示两个图片/任务入口，连线后自动添加备用入口；示例工作流已同步更新。

### 批次随机种子（0.8.0）

批次 seed 使用说明：
• seed 可手动填写；生成后控制可选 fixed / randomize / increment / decrement。
• randomize：每次排队后更换下一次使用的种子，新种子创建新批次并正常计费。
• fixed：名称、种子、输入均相同，恢复已有任务，不重复提交。
• 修改提示词、模型、尺寸或参考图后，换一个 seed；新种子也可用于再次生成相同提示词。
• 恢复旧批次时，请从 report 查看当时的 seed 并改回 fixed；不要使用排队后显示的新随机值。
• 此 seed 仅区分批次，不传给图像模型，不保证相同画面。

API 工作流通过 seed 数值区分新批次；randomize 是 ComfyUI 界面的生成后控制选项，API 调用者需自行更换 seed。旧 API 未传 seed 时保留原 job_key 行为。

### 模型和宽高连线（0.8.1）

独立任务新增 model_input（STRING）、width_input（INT）、height_input（INT）可选输入端口；接线优先使用上游结果，未接线则使用节点原有设置。宽高仅在像素模式生效；香蕉使用比例和 image_size。model_input 支持本插件已有模型名称，外部模型连线时显示各模型参数供选择，执行前按实际模型验证。多任务并发示例已用 ComfyUI 内置 Text / Int 节点连接模型、宽度和高度，并由两个任务共享。更改输入后应更换批次 seed。

### T香蕉2.1（0.8.2）

新增模型下拉与 model_input 名称支持，复用 KR Gemini 图片提交和查询接口；支持文生图、多图参考、比例和 1K/2K/4K，最多14张参考图。混合模型示例已使用 T香蕉2.1。

### 图片模型目录（0.11.0）

根据2026-11-14手册支持45款图片模型：13款同步（含4款W）、21款即梦、5款KR GPT、3款KR香蕉及3款HC。精确型号、质量、比例和分辨率见 image_models.json，合同证据见 docs/IMAGE-CONTRACTS-20261111.json。即梦参考图使用公网HTTP(S) URL；SR/FULL、KR香蕉使用IMAGE输入。混合示例同时演示同步与异步任务。


图片模型更新（0.11.0 / 文档2026-11-11）：共45款。
SR/FULL：/v1/images 同步返回，不轮询；使用整数宽高，16倍数、最长边≤3840、总像素655360–8294400、长短边≤3。参考图接 IMAGE，最多16张，不支持 reference_urls。quality 按型号选择，GPT Image 2-SR 不支持xhigh/max。同步请求超时或结果未知不会自动重提；相同批次恢复已有结果。
即梦新增：即梦-23-gemini-nano-banana-2.1；参考图在 reference_urls 每行填写一个公网HTTP(S)地址，不接IMAGE。所有21款即梦仅支持16:9、9:16、1:1、4:3、3:4。Seedream Pro 1K/2K，Lite 2K/4K，Seedream 5.5仅2K，其余1K/2K/4K。
KR香蕉：T香蕉pro为10种比例；T香蕉2/2.1为14种，额外支持1:4、4:1、1:8、8:1；仍用IMAGE参考图与1K/2K/4K。
API Key申请：https://api.canvasproai.com/keys ；直接填写批量执行节点。report与tasks_json已连接日志显示。


## 2026-11-14 更新

0.11.0 · 2026-11-14 最新图片合同：45款（文档首页旧统计32款尚未同步，按逐型号合同与在线目录核对）。
新增KR GPT 2.5/2.6 Flare、Sunburst：/kr/gpt/v1/images 异步接口；像素宽高或auto，不能传比例或image_size。质量支持auto/low/medium/high/xhigh/max，提示词最多32000字符，文件或URL参考图二选一，最多16张。
新增四款-W：同步Images接口，像素宽高或auto；参考图仅接IMAGE，不支持URL编辑；4K为超分输出，非原生4K。结果下载不携带API Key。
新增即梦2.6 Flare High、Sunburst High：1K/2K/4K；Seedream 5.5仅2K。即梦参考图填reference_urls，每行一个公网HTTP(S)地址，最多6张（其他型号上限依各型号合同）。
宽高均为16的倍数、最长边≤3840、总像素655360–8294400、长短边≤3。KR 2.5/2.6 超过3686400像素属于实验大尺寸，不保证严格尺寸。
提交不自动重试；同job_key与seed恢复已保存结果。修改输入或另生成一张，请换seed。report与tasks_json已连接日志。
Key申请：https://api.canvasproai.com/keys ；直接填写批量执行节点。


## ImgBB 临时图床（0.12.0）

ImgBB临时参考图（0.12.0）：即梦现在可直接连接加载图像的IMAGE端口，接满后自动增加，按型号上限停止。
本地参考图会自动上传ImgBB后交给即梦，公开直链在上传3小时后由图床自动删除（expiration=10800秒），不会永久保存。任务等待超过3小时后原参考图可能不可用。
ImgBB Key内置在Python后端，不增加图床密码框；用户只需填写自己的CanvasPro Key。
IMAGE与reference_urls二选一；URL方式不会上传ImgBB。图床上传失败会阻止该任务生图，report显示原因。
同批相同图片只上传一次；同job_key与seed恢复原任务，不重新上传、不重复提交。修改输入或另出一张时更换seed。
上传文件每张≤32MiB，参考图按端口顺序对应图1、图2。


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


## 增量获取队列结果（0.15.4）

队列批量查询默认只处理待完成、下载失败和尚未输出的结果；每次只输出本次新取得的图片。成功输出后记录本机queue_progress，后续运行及重启不会重复输出。单批内部分成功、部分未完成时，按原任务索引分别跟踪，不跳过未完成项。

失败、提交结果未知且没有任务号的记录只首次展开详情；后续默认不重复展开，历史总数与状态保留在queue_summary。不删除任务、图片缓存或原报告。勾选“包含历史结果（会重复输出）”可重新获取全部历史图片和旧错误；单独粘贴原报告或使用“再次获取结果”节点也仍可恢复原图。查询节点输出图片不等于下游保存成功；保存失败时可通过历史入口重新输出。

升级前已有的成功图片缓存归为历史，默认跳过；如需它们可开启历史开关。下载失败未成功缓存的图片仍待处理。每轮只展开本轮处理项，不再把整个队列的旧report/tasks_json全部带出；日志仍提供历史计数。

参考项目当前源码采用本轮新建任务在单次执行内轮询和汇总，没有累计queue_key队列；本插件继续保留多次提交与单次查询，并补充持久化的输出进度，避免重复结果。对照：[GrsAI批次汇总](https://github.com/31702160136/ComfyUI-GrsAI/blob/4bc7f76d95edc4877cc84b761c31f00eb30088a0/gpt_image_nodes.py#L175)、[任务轮询](https://github.com/31702160136/ComfyUI-GrsAI/blob/4bc7f76d95edc4877cc84b761c31f00eb30088a0/api_client.py#L205)。


## 缓存容量与清理（0.15.5）

默认图片缓存容量目标为1024 MiB（约1 GB），已输出结果距最后使用超过7天会被清理；超出容量优先淘汰最久未使用的已输出缓存。自动清理在获取结果时执行，无需配置文件或API Key。正在输出、未取回、其他队列尚未取得的结果以及旧版未标记输出的缓存受到保护；它们可能使总缓存暂时超过目标，报告会如实显示over_limit和protected_bytes。任务元数据仍保留，容量目标仅针对图片缓存，不包含成品目录。

新增 **CanvasPro · 缓存管理 / Cache Manager** 节点与[缓存管理示例](examples/缓存管理-Cache-Manager.json)（示例目录内请直接打开同名JSON）：默认“查看占用”只报告空间与生效设置；“应用设置”保存容量/天数并按规则清理；“清理已输出缓存”清空可清理缓存并整理数据库，不修改已保存设置。max_age_days=0关闭按天清理，容量限制仍生效。设置保存在本机，不写进用户模型节点。

仅清理插件数据库中的图片缓存，不删除任务号、URL、错误记录、队列进度，或保存图像节点写入的成品文件。清理后的历史图需原网址有效；异步任务可续查，网址失效时可使用refresh_urls。同步无网址结果清理后应读取已保存的成品图，不会自动重新生成收费。图片输出不代表下游文件已保存，请保存需要长期保留的结果。

新数据库支持增量回收空闲页，避免只清空图片字段却让磁盘文件保持增长。旧数据库在条件允许时整理后切换为增量回收；超过256 MiB的旧数据库不会在自动维护时进行完整重建，报告manual_compaction_required，手动清理可触发。空间不足或数据库忙时延后整理，空闲页仍可供后续写入复用。自动维护异常不会把已获取的图片改成生成失败。

实现依据：[SQLite空闲页回收](https://www.sqlite.org/pragma.html#pragma_auto_vacuum)、[VACUUM磁盘空间要求](https://www.sqlite.org/lang_vacuum.html)。
