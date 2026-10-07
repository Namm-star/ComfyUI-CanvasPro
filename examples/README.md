# 最新示例工作流（0.7.3）

将下面的 JSON 下载后拖入 ComfyUI。更新插件后先重启 ComfyUI，再刷新浏览器。

| 文件 | 用途 |
| --- | --- |
| [optimized-workflow.json](optimized-workflow.json) | 两个完整提示词任务直接连接批量执行；更多任务接到自动出现的入口 |
| [mixed-model-workflow.json](mixed-model-workflow.json) | GPT Image、香蕉、HC 三个不同模型任务一起执行 |
| [multi-edit-workflow.json](multi-edit-workflow.json) | 两张参考图连接同一个独立任务；请先在加载图像节点选择自己的图片 |

统一流程：独立任务 → 批量执行 → 保存图像。已删除旧的按行提交、串联合并及恢复示例，旧节点仍兼容已有工作流。

`optimized-api.json` 用于 ComfyUI API，不用于拖入界面。需要恢复结果时，原批次名称和内容保持不变再运行即可；新收费批次使用新的 `job_key`。端口名称决定任务/参考图顺序。多图示例按图1人物、图2服装编写提示词。

直接在「批量执行」节点 api_key 填写 Key；示例中的 Key 为空。

每个工作流右侧有尺寸速查 Note 节点，不参与执行。
