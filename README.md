# ComfyUI CanvasPro 0.2.0

0.2.0 新增 **CanvasPro · 模型自适应 / 多图批量提交**。推荐新工作流使用此节点，旧“批量提交”节点保持原输入与兼容性。

## 多图与随模型变化的参数

新节点默认提供 `image_1`、`image_2` 两个图片端口。调整 `reference_count` 会增加/减少端口；每个端口直接接一个“加载图像”，不同尺寸无需合并成批次，不会因合并被缩放。端口也接受 IMAGE 批次，按端口编号及批次内部顺序展开；所有图片实际数量仍受每个任务的模型上限限制。

- `gpt-image-2`：最多16个端口。`size_mode=pixels` 显示 `pixel_size`；`ratio` 显示 `aspect_ratio`、`image_size`；`auto` 不显示尺寸填写控件。质量只提供 auto/low/medium/high 或留空。
- `T香蕉2/pro`：最多14个端口，显示比例 `aspect_ratio` 和分辨率 `image_size`，隐藏质量、像素尺寸及URL输入。
- `s-gpt-image`：最多15个端口，显示 `pixel_size` 和对应质量选项；flare/sunburst 增加 xhigh/max，隐藏 `image_size`。
- 模型切换或减少数量若会删除已连接图片/参数，操作会被拒绝，原连线保留；先断开不兼容输入再切换。已有URL内容须先清空才能切换香蕉，避免藏起无法使用的输入。
- `shared`：每条提示词使用所有参考图；一条提示词对应一个多图编辑任务。`paired`：按展开后的图片顺序与提示词一一对应。

导入 `examples/multi-edit-workflow.json`，在两个“加载图像”中分别选人物图和服装图，即可查看多图编辑连线。选择模型后参数界面随之更新；查询、下载、保存节点共用。使用一个全新 `job_key` 创建新任务，沿用标识会恢复原批次。

更新后须重启 ComfyUI，并刷新浏览器页面以加载前端扩展；新建上述自适应节点。旧节点不会自动转换，以免破坏已有参数/连线。

独立 ComfyUI 自定义节点，通过本站 Key 调用 [CanvasPro API](https://api.canvasproai.com)。首版提供六款异步图片模型的文生图、编辑/参考图、客户端批量提交、批量查询与图片获取。2026-10-05 已通过本地 HTTP 模拟服务和真实 ComfyUI 加载/列表执行验证，**未使用真实 Key、未发付费请求**。

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
3. 配置 Key，然后重新启动 ComfyUI。搜索 `CanvasPro`，应出现六个节点。

本机找到的实际源码目录是 `F:\ComfyUI\ComfyUI\ComfyUI`，Python 是 `F:\ComfyUI\ComfyUI\python\python.exe`；外层 `F:\ComfyUI\ComfyUI` 是启动器目录。交付时未复制插件到现有安装，也未改其配置。其他机器请核对自己的路径。

## 申请与配置本站 Key

1. 登录 [本站 Key 页面](https://api.canvasproai.com/keys)，创建你自己的 Key，确认额度、分组和目标模型权限。API 与 CanvasPro 使用统一账号、共享钱包。这里使用的是本站 Key。
2. Windows 推荐运行插件内 `configure-key.ps1`，交互输入时隐藏 Key。脚本把它保存到 `%LOCALAPPDATA%\CanvasProComfyUI\key.txt`，先设置当前 Windows 用户专属文件 ACL。ComfyUI 须以同一 Windows 用户运行；执行前可审阅脚本。
3. 也可在 ComfyUI **服务端进程**的环境中配置 `CANVASPRO_API_KEY`，或用 `CANVASPRO_KEY_FILE` 指向受保护的纯文本文件。环境变量优先于文件。不要把 Key 放进命令行、工作流、提示词、截图、Git 或聊天。

Linux/macOS 默认 Key 文件为 `~/.config/CanvasProComfyUI/key.txt`，请限制目录为 `700`、文件为 `600`。数据目录可用 `CANVASPRO_DATA_DIR` 显式指定；Key 与批次数据分开存放。默认根地址已预设为 `https://api.canvasproai.com`，不会统一追加 `/v1`。

本地文件配置用于你信任的 ComfyUI 服务端。共享/公网 ComfyUI 实例中的用户可能使用服务端同一 Key，首版不提供多用户密钥隔离；请使用独立服务进程和受保护数据目录。

## 工作流

把 `examples/batch-workflow.json` 拖入 ComfyUI：

`批量提交 → 批量查询/等待 → 批量获取图片 → SaveImage`

- `prompts`：每个非空行一个提示词；需要多行提示词时填 JSON 字符串数组，例如 `["第一行\n第二行", "另一个提示词"]`。每批 1–256 项，每项独立提交、`n=1`。
- `job_key`：本地批次标识。**同一个标识、同一组输入永远返回原批次，不重新 POST**；改动输入但沿用标识会报错。需要新的收费批次时明确换一个标识。示例默认 `example-002`，不要误认为反复点击会重新出图。这是本地防重复机制，不是服务端幂等保证。
- 旧通用节点的 `images`（新自适应节点使用 `image_1` 等独立端口）：可连接 ComfyUI IMAGE 批次，转成 PNG 后上传。`shared` 将全部图片作为每个提示词的共同参考；`paired` 按顺序将每张图分配给对应提示词，数量必须相等。`reference_urls` 支持 KR/HC 的公网 HTTPS URL，每行一个，不与 IMAGE 同时使用。香蕉使用 IMAGE 的 inlineData。
- `concurrency`：每个节点 1–8，默认 3；只限制本节点，不是整个 ComfyUI 的全局并发限额。
- 旧通用节点的 `size/quality/image_size`：留空省略。香蕉的 `size` 填比例，`image_size` 填 1K/2K/4K，`quality` 留空。HC 的 `size` 填像素尺寸，`image_size` 留空。无效组合在任何提交前整批拒绝，详见 [协议记录](docs/PROTOCOL.md)。
- `wait_seconds=0`：每个已知任务查询一次；大于零时按同一任务号轮询，间隔退避至 15 秒。等待超时只记录状态，不再次生成。
- 获取节点只下载 `succeeded` 项。输出是 **IMAGE 列表**，每项 `[1,H,W,3]`，不同尺寸保持原样；接 `SaveImage` 会逐项保存。成功图片按输入顺序排列；`download_report.output_indices` 对应原提示词索引，失败不会用空白图顶替。全部失败时输出空列表并给出报告，下游图片节点不会执行有效保存。

### 重启、分阶段运行、已有任务

批次保存在 ComfyUI 用户数据目录的 `canvaspro/tasks.sqlite3`；无 ComfyUI 环境时回退到 `%LOCALAPPDATA%\CanvasProComfyUI`（非 Windows：`~/.local/share/CanvasProComfyUI`）。保存内容包括批次标识、输入摘要、任务号、状态和结果 URL，不保存 Key、提示词或原参考图片。结果 URL 可能含临时签名，数据库应保存在受保护的本地目录，不要分享。

- 使用 `examples/resume-workflow.json`，填原 `job_key`，即可在重启后继续查询及下载。
- 只要提交节点存在，就会在运行时检查本地记录；同标识不会因 ComfyUI 缓存变化重复生成。可以先只执行提交节点，稍后用恢复工作流获取结果。
- 迁移数据库时保存整个文件；任务 JSON 是不含秘密的本地引用及状态快照，查询时以数据库为准。没有数据库时，用“导入已有任务号”节点，选择正确模型，每行填一个原任务号；它不会提交新任务。
- 超时、网络错误、非成功 HTTP、缺少任务号均保守标为 `submit_unknown`。到本站任务/账单核对，找到原任务号后导入继续查询。不要直接换标识重发未知提交。
- 进程在 POST 前已写入 `sending` 意图；重启读取时视作未知。取消提交过程中尚未开始的项可能保持 `prepared`，沿用原批次也不会自动补发。
- 使用 ComfyUI 停止/中断取消客户端等待。已提交的服务端任务仍可能运行或计费，取消等待不等于取消服务端任务或退款。已进行的 HTTP 最多等待当前请求超时后退出；下载中的请求与 GET 重试也受请求超时约束。
- 下载链接过期/下载失败时先重跑查询节点刷新 URL，再运行获取节点。查询/下载可重试；**POST 没有自动重试**。报告只保留本地错误码，避免服务端错误体回显 Key 或私有链接。

## 验证

使用已有 ComfyUI Python，从插件目录运行：

```powershell
& 'F:/ComfyUI/ComfyUI/python/python.exe' -m unittest discover -s tests -v
& 'F:/ComfyUI/ComfyUI/python/python.exe' tests/comfy_load_check.py 'F:/ComfyUI/ComfyUI/ComfyUI'
```

集成测试使用临时数据库、假 Key、真实 loopback HTTP、真实 Pillow/torch。加载检查在独立进程调用现有 ComfyUI 的 `load_custom_node`、`validate_prompt`、`get_output_data` 与 `SaveImage`，不安装进现有 `custom_nodes`。详见 [开发记录](docs/DEVELOPMENT.md)。`batch-api.json`/`resume-api.json` 是 API 格式，UI 导入请用 `*-workflow.json`。

手动模拟可运行 `tests/mock_service.py`，它打印随机 loopback 地址；在独立测试 ComfyUI 进程设置 `CANVASPRO_ALLOW_LOCAL_TEST=1`、`CANVASPRO_BASE_URL` 为该地址、`CANVASPRO_API_KEY=fake-secret`、`CANVASPRO_DATA_DIR` 为临时目录。不要为测试启动覆盖生产服务；退出后移除这些测试环境变量。模拟提示词 `fail` 产生任务失败，`always-pending` 模拟超时。

## 首版范围

图片：`gpt-image-2`、`T香蕉2`、`T香蕉pro`、`s-gpt-image-2`、`s-gpt-image-2.5-flare`、`s-gpt-image-2.5-sunburst`。模型/参数来自当前公开目录和现行协议资料，不动态猜测新型号。

视频与文本能力已记录在 `capabilities.json` 和协议文档，**首版未实现视频/文本执行节点**。后续可复用持久化意图、并发与只查询机制，但需独立响应解析、视频鉴权下载/媒体输出和逐型号能力校验。没有真实付费端到端验收，0.2.0 已核对模型切换和端口增加的实际界面；实际模型权限、上游可用性、组合参数和最终图片尺寸由服务端决定。

参考 [ComfyUI-GrsAI](https://github.com/31702160136/ComfyUI-GrsAI) 的节点拆分和并发反馈思路；本插件协议与实现独立编写，不使用 GrsAI 的 `/v1/api/result`。其 MIT 许可与原作者声明见 `THIRD_PARTY_NOTICES.md`，不包含原仓库 `.env`、价格或推广内容。
