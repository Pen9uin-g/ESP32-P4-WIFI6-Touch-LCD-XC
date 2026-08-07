# 仓库结构

[English](PROJECT_STRUCTURE.md)

本仓库按开发板软件包组织，包含一方示例、维护中的固件源码、原理图和仓库级
文档。

## 顶层目录

| 路径 | 用途 |
| --- | --- |
| `README.md` / `README_ZH.md` | 项目概览与快速开始 |
| `examples/` | ESP-IDF 和 Arduino 一方示例 |
| `firmware/` | 单独维护的开发板固件源码 |
| `hardware/` | 原理图和硬件参考文件 |
| `docs/` | 仓库级文档 |
| `.github/` | CI 工作流、检查脚本和模板 |
| `LICENSE` | Apache 许可证文本 |

## ESP-IDF 一方示例

可构建的 ESP-IDF 示例通常包含：

| 文件或目录 | 用途 |
| --- | --- |
| `CMakeLists.txt` | ESP-IDF 工程入口 |
| `main/` | 主应用组件 |
| `main/CMakeLists.txt` | 主组件构建定义 |
| `main/idf_component.yml` | 按需声明的托管依赖 |
| `components/` | 工程本地组件、板级 glue 或上游组件副本 |
| `sdkconfig.defaults` | 工程默认配置 |
| `sdkconfig.ci*` | 可选的 CI 配置覆盖 |
| `partitions.csv` | 可选的自定义分区表 |

`build/`、`managed_components/`、`dependencies.lock` 和本地 `sdkconfig` 等
生成目录不应提交。

`examples/esp-idf/` 是默认产品构建面。`firmware/` 单独维护，除非维护者明确
建立固件专用工作流，否则不会进入默认示例矩阵。

## 示例文档

每个面向硬件的示例都应说明支持的开发板、所需外设、框架版本、跳线/线缆、
`menuconfig` 或 Arduino 设置、编译烧录方式以及已知限制。新增、重命名或删除
工程时同步更新[示例索引](../examples/README_ZH.md)。

## CI 约定

CI 辅助脚本只会发现 `examples/esp-idf/` 下的一方 ESP-IDF 示例。新的示例应
能够独立运行：

```bash
idf.py set-target esp32p4
idf.py build
```

仓库策略与 Markdown 检查位于独立且始终可见的工作流中。纯文档修改不会启动
昂贵的示例构建矩阵。
