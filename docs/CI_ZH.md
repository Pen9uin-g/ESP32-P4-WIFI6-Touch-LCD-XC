# 持续集成

[English](CI.md)

GitHub Actions 负责运行仓库检查和产品示例构建。工作流将文档验证与固件编译
分开，纯文档修改不会消耗产品构建任务。

## 工作流

| 工作流 | 用途 |
| --- | --- |
| [Documentation and repository policy](../.github/workflows/documentation.yml) | 始终可见的 Markdown、结构和治理检查 |
| [ESP-IDF projects](../.github/workflows/esp-idf-projects.yml) | 仓库自检、ESP-IDF 示例发现和 ESP32-P4 构建 |
| [Arduino projects](../.github/workflows/arduino-projects.yml) | 一方 Arduino 示例发现和 ESP32-P4 构建 |

文档工作流会在每个 Pull Request、推送到 `main` 和手动触发时运行。产品构建
工作流在相关 Pull Request、匹配的 `main` 推送和手动触发时运行。同一 Pull
Request 有新提交时，会取消过时的在途产品构建。

## 仓库自检

文档工作流和 ESP-IDF 工作流都会运行：

```bash
python .github/scripts/repo_self_check.py
```

它会检查仓库级文档、产品图片、CI 脚本和工作流是否存在，生成的 ESP-IDF 输出
是否被忽略，每个 ESP-IDF 示例的最小结构，一方 Arduino 示例是否有同名 `.ino`
文件，以及示例索引是否包含全部工程。

## ESP-IDF 示例发现

辅助脚本为：

```bash
python .github/scripts/discover_esp_idf_projects.py
```

默认可构建的 ESP-IDF 示例必须同时包含 `CMakeLists.txt` 和 `main/`，且位于
`examples/esp-idf/` 下。Pull Request 和推送只选择受影响的一方示例；修改
ESP-IDF 工作流、发现脚本或 `config/` 下共享配置时，会选择全部 12 个示例。

`firmware/brookesia` 会被仓库盘点，但不会进入默认示例矩阵。固件源码需要维护者
明确的固件专用工作流，不能仅因路径名称而自动加入示例 CI。

每个选择的示例使用以下设置：

| 设置 | 值 |
| --- | --- |
| ESP-IDF | `v5.5.5`、`v6.0.2` |
| Target | `esp32p4` |
| GitHub Action | `espressif/esp-idf-ci-action@v1` |

手动运行可以使用 `project=all`、工程名（如 `02_HelloWorld`）或完整路径。

## Arduino 示例发现

辅助脚本为：

```bash
python .github/scripts/discover_arduino_sketches.py
```

只有直接匹配 `examples/arduino/examples/<name>/<name>.ino` 的目录是一方示例。
内置库下的上游示例不会进入矩阵。

每个选择的示例会编译两次：

| 设置 | 值 |
| --- | --- |
| Arduino-ESP32 | `3.3.11` |
| 开发板 | 通用 ESP32-P4、pre-v3 silicon、32 MB Flash、启用 PSRAM |
| 显示变体 | 3.4C（`SCREEN_3INCH_4_DSI`）、4C（`SCREEN_4INCH_DSI`） |
| 内置库 | `examples/arduino/libraries/` |

工作流使用仓库内的 Arduino GFX、LVGL 和开发板显示/触控辅助库，不会替换为
在线更新的库版本。
