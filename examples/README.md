# 最新示例工作流（0.8.1）

将下面的 JSON 下载后拖入 ComfyUI。更新插件后先重启 ComfyUI，再刷新浏览器。

| 文件 | 用途 |
| --- | --- |
| [多任务并发-Multi-Task-Batch.json](多任务并发-Multi-Task-Batch.json) | 两个完整提示词任务直接连接批量执行；更多任务接到自动出现的入口 |
| [混合模型并发-Mixed-Model-Batch.json](混合模型并发-Mixed-Model-Batch.json) | GPT Image、香蕉、HC 三个不同模型任务一起执行 |
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
