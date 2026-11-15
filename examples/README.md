# 最新示例工作流（0.11.0）

将下面的 JSON 下载后拖入 ComfyUI。更新插件后先重启 ComfyUI，再刷新浏览器。

| 文件 | 用途 |
| --- | --- |
| [多任务并发-Multi-Task-Batch.json](多任务并发-Multi-Task-Batch.json) | 两个完整提示词任务直接连接批量执行；更多任务接到自动出现的入口 |
| [混合模型并发-Mixed-Model-Batch.json](混合模型并发-Mixed-Model-Batch.json) | GPT Image、T香蕉2.1、SR 同步与即梦 Seedream 四个模型一起执行 |
| [多图编辑-Multi-Image-Edit.json](多图编辑-Multi-Image-Edit.json) | 两张参考图连接同一个独立任务；请先在加载图像节点选择自己的图片 |

统一流程：独立任务 → 批量执行 → 保存图像。已删除旧的按行提交、串联合并及恢复示例，旧节点仍兼容已有工作流。

`optimized-api.json` 用于 ComfyUI API，不用于拖入界面。需要恢复结果时，原批次名称和内容保持不变再运行即可；新收费批次使用新的 `job_key`。端口名称决定任务/参考图顺序。多图示例按图1人物、图2服装编写提示词。

API Key 申请地址：[https://api.canvasproai.com/](https://api.canvasproai.com/)。直接在「批量执行」节点 api_key 填写 Key；示例中的 Key 为空。每个界面示例均在批量执行节点旁放置申请与填写说明注释。

每个工作流右侧有尺寸速查 Note 节点，不参与执行。

所有界面示例已连接 ComfyUI 内置 PreviewAny 文本显示节点：report 显示执行结果和错误，tasks_json 显示任务句柄，供检查任务及恢复结果使用。无需另装文本显示插件。运行结束后更新内容；处理中可看批量执行节点标题。

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

图片模型与比例（0.11.0）

T香蕉pro：1:1、2:3、3:2、3:4、4:3、4:5、5:4、9:16、16:9、21:9。
T香蕉2 / 2.1：以上比例加 1:4、4:1、1:8、8:1。

新“即梦”图片模型：选择该型号支持的 aspect_ratio 与 image_size；各型号比例、清晰度、参考数量不同。
Seedream 5 Pro 支持1K/2K；Lite支持2K/4K。

新“即梦”参考图：在 reference_urls 填公网 HTTP(S) 图片地址，每行一个；当前公开 API 仅接受URL，不支持直接 IMAGE 文件上传。
原有香蕉继续连接 IMAGE 参考图，不支持URL。

修改模型或参数后，使用新 seed 创建批次。


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
