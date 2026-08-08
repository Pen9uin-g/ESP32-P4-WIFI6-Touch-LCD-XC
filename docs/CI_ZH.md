# 持续集成

[English](CI.md)

本仓库以 GitHub Actions 作为构建结论的权威来源。维护者可以在本地运行 Python
策略检查，但产品编译证据必须来自修改提交并推送后的 Actions。

## 工作流

| 工作流 | 用途 |
| --- | --- |
| [Documentation and repository policy](../.github/workflows/documentation.yml) | 始终可见的单元测试、Markdown、结构和路由策略检查 |
| [ESP-IDF projects](../.github/workflows/esp-idf-projects.yml) | 按变更选择 ESP32-P4 一方 ESP-IDF 示例构建 |
| [Arduino projects](../.github/workflows/arduino-projects.yml) | 按变更选择 ESP32-P4 一方 Arduino 示例构建 |

三个工作流都会在每个 Pull Request 和推送到 `main` 时启动。产品工作流始终显示
路由结果，只有路由选中产品工程时才运行昂贵的构建任务。同一 Pull Request 出现
新提交时会取消过时的在途任务。Pull Request 使用精确的 head SHA，而不是 GitHub
生成的临时 merge commit。

## 静态策略门禁

策略工作流会运行：

```bash
python -m unittest discover -s .github/tests -p "test_*.py"
python .github/scripts/repo_self_check.py
python .github/scripts/audit_markdown.py . --all --config .github/scripts/markdown-audit-config.json
```

Pull Request 的 Markdown 检查会把 `--all` 换成 base SHA。仓库自检会验证必需文档
和工作流、生成物忽略规则、12 个直接 ESP-IDF 工程、5 个直接 Arduino 示例以及
示例索引。

## 完整变更路由

两个产品工作流和策略工作流共用一个分类器：

```bash
python .github/scripts/ci_change_router.py --base-ref <base-sha> --head-ref <head-sha>
```

分类器读取 `git diff --name-status -z --find-renames`，因此删除和重命名两端都会
保留原路径的构建影响。无效 ref 或意外空 diff 会作为操作失败退出，不能静默产生
绿色的零构建结果。策略工作流额外使用 `--strict-unknown`；新出现的未知路径即使
触发了保守的双全量矩阵，也必须先补充明确分类规则。

| 修改路径 | 产品路由 |
| --- | --- |
| `examples/esp-idf/<project>/**` 源码或配置 | 对应 ESP-IDF 工程 |
| `examples/arduino/examples/<sketch>/**` 源码 | 对应 Arduino 示例 |
| `examples/arduino/libraries/**` | 全部一方 Arduino 示例 |
| 产品工作流或共享路由器 | 对应的完整矩阵 |
| 一方 Markdown、`docs/**`、`assets/**`、`hardware/**`、纯策略文件 | 只运行策略检查 |
| `firmware/**` | 显示 `firmware_touched`，不推断为示例构建 |
| `.bin`、`.zip` 等固件/归档镜像 | 固件结果并标记必须显式发布审核 |
| 未分类的非文档路径 | 双完整矩阵并使严格策略失败 |

`firmware/brookesia` 是单独维护的交付/源码面。它会被盘点，但不会仅因目录中存在
ESP-IDF 工程就被当作另一个示例，也不会凭空获得未经验证的构建命令。

## ESP-IDF 矩阵

一方 ESP-IDF 工程必须同时包含 `CMakeLists.txt` 和 `main/`，并且是
`examples/esp-idf/` 的直接子目录。每个选中的工程使用：

| 设置 | 值 |
| --- | --- |
| ESP-IDF | `v5.5.5`、`v6.0.2` |
| Target | `esp32p4` |
| GitHub Action | `espressif/esp-idf-ci-action@v1` |

默认完整路由包含 24 个任务：12 个工程乘以两个 ESP-IDF 版本。
`12_usb_extend_screen` 还会使用关闭 HID 触控和 UAC 音频的 CI 专用
`vendor-only` 配置在两个版本上构建，证明条件源码和描述符路径；因此完整路由一共
包含 26 个 ESP-IDF 构建任务。

手动运行可以使用 `project=all`、工程名（如 `02_HelloWorld`）或完整工程路径。

## Arduino 矩阵

只有直接匹配 `examples/arduino/examples/<name>/<name>.ino` 的目录是一方示例，
第三方库内置示例不会被发现。每个选中的示例会针对两个显示型号构建：

| 设置 | 值 |
| --- | --- |
| Arduino-ESP32 | `3.3.11` |
| 开发板 | 通用 ESP32-P4、pre-v3 silicon、32 MB Flash、启用 PSRAM |
| 显示变体 | 3.4C（`SCREEN_3INCH_4_DSI`）、4C（`SCREEN_4INCH_DSI`） |
| 内置库 | `examples/arduino/libraries/` |

完整路由为 5 个示例乘以 2 个显示变体，共 10 个构建任务。手动运行可以使用
`sketch=all`、示例名或完整示例路径。
