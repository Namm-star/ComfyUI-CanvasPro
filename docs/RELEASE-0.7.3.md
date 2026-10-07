# 0.7.3

独立任务的节点定义直接移除 pixel_size 控件，不再依赖前端隐藏。旧工作流10/12项控件值自动删除旧字符串槽，并迁移/保留width、height，防止后续参数错位。旧Python/API调用仍可通过execute的pixel_size兼容参数使用。示例更新为11项控件。
