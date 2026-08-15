# Arduino 分段烧录与 Hardware CDC 验证

[English](ARDUINO_FLASHING.md)

## 适用范围

本指南适用于 `examples/arduino/examples/` 下的 5 个一方示例。它们使用
Arduino-ESP32 `3.3.11` 和 [Arduino 说明](../examples/arduino/README_ZH.md)
记录的精确 FQBN 构建。请按实际产品选择对应的 3.4C 或 4C 显示版本。

这些包是硬件测试候选，不是工厂固件，也不表示硬件在环（HIL）验证已经通过。

## 分段包内容

打包器读取完整的 Arduino CLI 构建目录，只复制该次构建生成的 `flash_args`
实际列出的 bootloader、分区表、存在时的 `boot_app0`、应用以及其他分段。偏移
和 Flash 选项不会根据芯片系列猜测，不会从其他构建复制，也不会从 merged
镜像反向切分。

每个通过验证的目录和 ZIP 包含：

- `manifest.json`，记录有序的分段偏移、文件、大小和 SHA-256；
- 规范化后的 `flash_args`，以及它自身的大小和 SHA-256 元数据；
- `SHA256SUMS`，覆盖包内元数据、烧录辅助脚本和载荷文件；
- 执行精确分段计划的 `flash.sh` 与 `flash.bat`；
- 只包含真实分段计划引用的 `bin/` 载荷文件。

原始 `build.options.json`、expanded properties、ELF/map 调试元数据及其他主机
相关构建记录不会公开。manifest 的 `build_inputs` 只记录原始 build options、
`flash_args` 与 `compile_commands.json` 的文件名、大小和 SHA-256；validator 会在
私有构建目录中重新计算这些精确文件的哈希。

脱敏后的 `build_identity` 会绑定产品 SHA、仓库相对 project 与主 `.ino` 路径、
sketch 名称、精确 FQBN 和屏幕 define；同时记录生成的 sketch translation unit 与
object 以及已跟踪主源码的文件名/大小/SHA-256、按顺序排列的编译参数数组
SHA-256，以及 application 文件名、包内路径、offset、大小和 SHA-256。验证时会
从处于声明产品 SHA 且干净的源码 checkout 和外部构建目录重新计算这些身份，并
把私有 build-options 的 `sketchLocation` 与已跟踪 project 对齐，再要求唯一匹配
的编译条目、真实源码 include、translation unit、object、application 分段，以及
精确 FQBN、屏幕 define、`ARDUINO_USB_MODE=1` 和
`ARDUINO_USB_CDC_ON_BOOT=1` 均一致。原始编译参数、用户名、绝对工作目录及工具
缓存路径不会进入公开包。

manifest 还会记录完整产品 Git SHA、Arduino FQBN 与 core 版本、Flash 容量、
`segmented_payload_total`，以及候选 BSP 的版本、来源 SHA、来源 tree hash 和
组件 tree hash。Arduino 示例不链接 ESP-IDF managed BSP，因此 BSP 关系明确
标为 `reference-only`；这些 pin 用于把 Arduino 候选与 ESP-IDF 候选绑定到同一
审查检查点。

包内不会发布 merged 或 whole-flash 镜像。如果真实的多段计划要求 bootloader
位于 `0x0`，这是合法的；禁止的是从 `0x0` 写入单个整片合并镜像。

## 烧录前验证

请保持包目录完整，并在目录内执行校验：

```sh
sha256sum -c SHA256SUMS
```

同时检查 `manifest.json` 并确认：

1. `product_variant`、`resolution` 与 `profile_id` 符合开发板。
2. `product_git_sha` 及所有 BSP pin 与待测候选一致。
3. `framework.version` 为 `3.3.11`，FQBN 是预期的 ESP32-P4 FQBN。
4. `build_identity.project`、`sketch`、`screen_define`、`primary_source.path` 与
   `application.source_basename` 对应预期的 sketch 构建。
5. 有序 `files` 和 `portable_flash_command` 描述多个独立分段，而不是 merged
   或 whole-flash 镜像。

CI 会先验证目录，再重新打开生成的 ZIP，重复检查路径安全、哈希、大小、分段
重叠、Flash 容量、隐私以及无 merged 镜像；同时会在公开包之外重算原始
build-options 的哈希。对于目录和重新打开的 ZIP，validator 都会根据已验证的
分段计划逐字节重建 `flash.sh` 与 `flash.bat`。缺少任一辅助脚本、删除任一分段，
或篡改 offset、分段文件名、Flash mode/frequency/size 选项，均会以非零状态拒绝。
验证后不要添加、删除或替换文件。

## 按生成计划分段烧录

请在烧录环境安装 Python `esptool` 包，并把 `PORT` 替换为开发板的实际上传
端口。在 Linux 或 macOS 上执行：

```sh
sh flash.sh PORT 921600
```

在 Windows 上执行：

```bat
flash.bat PORT 921600
```

辅助脚本执行一条 `write_flash` 命令，其中包含 Arduino CLI 真实生成并排序的
offset/file 对。脚本不会擦除设备，也不会写入按 Flash 容量填充的整片镜像。
`manifest.json` 的 `portable_flash_command` 还保存了可复制的完整分段命令。

## 选择正确的 USB 接口

已测试 FQBN 使用 `USBMode=hwcdc,CDCOnBoot=cdc`：

- **Type-C USB** 连接 ESP32-P4 内部 USB 引脚，示例 `Serial` 通过 Hardware
  USB Serial/JTAG CDC 输出。
- **Type-C UART** 通过 CH343P 转接芯片连接 UART0。受支持的上传流程可以使用
  该接口，但在已测试 FQBN 下，它不会收到示例的 `Serial` 日志。

一方日志封装不会等待任一接口或串口监视器。Hardware CDC 发送超时设为零；
断开连接或主机背压时会丢弃当前诊断行，不会阻塞应用、显示或触控启动。

## 必做 HIL 检查

3.4C 与 4C 包需分别执行以下检查：

1. 关闭所有串口监视器并断开 Type-C USB，然后重新上电。确认示例无需主机连接
   即可进入正常显示和触控功能。
2. 连接 Type-C USB，但不要打开监视器。持续操作界面和触控，主机背压不得造成
   停顿。
3. 以 `115200` 打开 Hardware CDC 监视器。确认打开监视器不会复位或卡住应用；
   启动日志可能已按设计丢弃。
4. 在持续操作应用时关闭、拔出并重新连接 Type-C USB。显示与触控必须继续；
   后续日志可以恢复，也可以被丢弃，但不得影响应用。
5. 对触控候选检查冷启动、软件复位、重复上电、四角、边缘、拖动和多点触控。
   `Drawing_board` 是主要轮询测试，`LVGLV9_Arduino` 用于补充持续 LVGL 刷新。
6. 如果使用 Type-C UART 上传，请确认上传和复位符合预期；不要把该接口看不到
   示例日志误判为故障。

编译、打包和主机侧测试不能代替以上实机结果。每份 HIL 报告都应记录包
SHA-256 以及精确产品/BSP pin。
