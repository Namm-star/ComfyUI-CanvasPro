# 开发记录 0.1.0 — 2026-10-05

## 环境与边界

独立仓库位于本任务 outputs/ComfyUI-CanvasPro，分支 `codex/canvaspro-plugin`。祖先目录未发现 AGENTS.md；只读参考 CanvasPro 当前仓库规范。现有 ComfyUI 源码实际嵌套在 F:/ComfyUI/ComfyUI/ComfyUI，版本文件0.36.0；对应 Python3.11.9、torch2.7.0+cu128，requests/Pillow/numpy均可导入。未升级/重装依赖，未复制到现有 custom_nodes，未修改现有 ComfyUI 或 CanvasPro Git 工作树。

线上仅无凭据读取公开目录、状态、源码声明、视频能力JSON及页面/静态JS。未读真实 Key，未发模型生成请求、上传素材、写生产模型/渠道/价格/账务、重启或外发消息；没有创建 GitHub 仓库或 PR。

## 实现决定

- 五个节点采用仍由实际 ComfyUI 支持的 V1 NODE_CLASS_MAPPINGS 接口。
- SQLite事务保存批次和逐项发送意图；同 job_key 输入摘要复用原记录，不 POST；不同输入拒绝复用。这个机制只在同一保留数据库内成立，复制/删除数据或更换标识没有服务端幂等保护。
- 重启读取 sending 为 submit_unknown，不盲目重试；prepared项也不自动补发。任务状态报告不保留服务端原始错误消息，避免秘密回显。
- 带宽/网络超时下请求结果未知时保留证据。并发按节点1–8，图片查询/下载与提交完全分开；输入顺序聚合，部分失败保留其他结果。
- 图片用OUTPUT_IS_LIST输出独立张量，真实ComfyUI映射后可直接SaveImage；不硬拼不同尺寸。
- Key采用服务端环境/专属文件；本地数据库保存任务及可能带签名的结果URL，应保持私有。HTTP下载每个重定向重新判定同源，跨源不带Key。

## 验证结果

`python -m unittest discover -s tests -v`：14项通过，实际loopback HTTP与临时SQLite，覆盖：

1. 六款模型的编辑路径/上传字段/PNG字节与Gemini inlineData。
2. KR URL编辑multipart与HC URL编辑JSON。
3. 提交/查询分离、限制并发、输入顺序、逐项失败。
4. 超时、HTTP失败、缺任务号不重复POST。
5. 全批预校验与job_key输入冲突阻断。
6. GET可重试、等待超时后再查而不生成。
7. 发送中崩溃及未发送状态恢复后不重发。
8. 取消等待保留任务号、服务端任务继续存在。
9. 节点真实torch图片、不同尺寸、下载并发、恢复/导入已有任务。
10. 参数限制与UTF-16文本长度。
11. 多个线程同批标识只提交一组任务。
12. 跨源重定向移除Authorization。
13. 一项下载失败保留其他图片和原索引。
14. 全新Python子进程读取旧批次、继续查询并完成，不产生额外POST。

`tests/comfy_load_check.py`：现有ComfyUI真实加载器注册5节点；真实`validate_prompt`通过API示例；通过`get_output_data`执行提交→等待→获取，原生列表映射及`SaveImage`在临时目录保存2张不同尺寸PNG。独立CPU进程，没有启动/覆盖用户ComfyUI服务。

首轮11项曾因SQLite上下文只提交事务、不关闭连接导致Windows临时目录清理报错；修复为显式contextmanager/finally close后全部重跑通过。不是通过忽略清理错误绕过。现有运行环境有CUDA优化与pydantic模型字段警告，未改其环境；CPU加载与本插件验证通过。

## 未验证与下一版

未做真实付费端到端验收或UI目视；未验证上游每种尺寸/档位/参考图上限的实际生成。公开源码声明与线上目录已复核，但没有鉴权拉取服务器运行态插件或直接核对服务器二进制。首版视频/文本是能力登记与扩展计划，不是已可执行节点。

后续：模型动态目录与逐协议版本刷新；视频适配和媒体输出；文本独立节点；更多跨进程竞争、缓存过期及媒体下载中断测试；按明确预算选择最小真实生成验收。多用户Key隔离需独立设计，不能依靠前端隐藏输入实现。持久记录当前无自动过期清理，用户可在停止ComfyUI后备份数据目录；删除数据库会丢失本地防重复记录。
