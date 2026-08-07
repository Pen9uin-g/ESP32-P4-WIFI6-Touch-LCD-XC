# 贡献指南

[English](CONTRIBUTING.md)

感谢你改进 ESP32-P4-WIFI6-Touch-LCD-XC 的示例和文档。

## 创建 Pull Request 前

- 将修改限定在受影响的一方示例或文档范围内。
- 不要添加生成的 `build/`、`managed_components/`、`dependencies.lock` 或本地
  `sdkconfig` 输出。
- 保持内置库和嵌入式上游源码的边界，不批量改写其中的文档。
- 未获得维护者明确指示时，不要在普通示例/CI 工作中修改 `firmware/` 源码或交付物。
- 涉及开发板的改动，先对照仓库原理图、BSP 头文件、Arduino 配置和示例源码，
  再修改引脚或显示设置。
- 一方人类可读 Markdown 要同时维护英文主文件和简体中文 companion。

## 验证

根据修改范围运行相关检查：

```bash
python .github/scripts/repo_self_check.py
python .github/scripts/audit_markdown.py . --working-tree --config .github/scripts/markdown-audit-config.json
python .github/scripts/discover_esp_idf_projects.py --project all
python .github/scripts/discover_arduino_sketches.py --sketch all
```

源码修改应使用 ESP-IDF 和 Arduino 工作流或等价的本地工具链。在 Pull Request
描述中记录示例、框架版本、Target、硬件/参考资料审计状态、组件影响以及固件
交付物影响。
