# ComfyUI CanvasPro 0.8.0

**独立任务 → 批量执行 → 保存图像**。支持完整多行提示词、混合模型、自动增加任务及参考图入口。每批最多 256 个任务，提交并发数 1～8；重复运行同一批次不会重新提交收费。

## 最新示例工作流

旧示例已删除，当前只保留以下三个界面工作流：

- [普通多任务](examples/多任务并发-Multi-Task-Batch.json)：多个独立任务直接连接批量执行，无需合并节点。
- [混合模型](examples/混合模型并发-Mixed-Model-Batch.json)：GPT Image、香蕉、HC 三个任务一起执行。
- [多图编辑](examples/多图编辑-Multi-Image-Edit.json)：两张参考图连接一个完整提示词任务，再连接批量执行；先选择自己的图片。

下载对应 JSON 后拖入 ComfyUI。已安装用户先更新插件、重启 ComfyUI，再刷新浏览器。更多说明见 [示例目录](examples/README.md)。`optimized-api.json` 是 API 格式，界面导入请使用 `*-workflow.json`。

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

支持图片模型：`gpt-image-2`、`T香蕉2`、`T香蕉pro`、`s-gpt-image-2`、`s-gpt-image-2.5-flare`、`s-gpt-image-2.5-sunburst`。详细参数见 [协议记录](docs/PROTOCOL.md)。视频和文本执行节点尚未实现。

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
