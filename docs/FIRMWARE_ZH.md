# 固件源码边界

[English](FIRMWARE.md)

仓库包含维护中的 ESP-Brookesia 源码工程：
[`firmware/brookesia`](../firmware/brookesia/)。它是单独的固件/交付面，不属于
普通示例。

## CI 与修改边界

- 默认 ESP-IDF 示例 CI 只发现 `examples/esp-idf/`。
- `firmware/brookesia` 有自己的 `maintained-firmware.yml` 路由，并产生恰好两个
  ESP-IDF `v5.5.5` 产物：`rev1_3` 和 `rev3_x`。它不会加入保持不变的 40 个 ESP-IDF
  加 10 个 Arduino 示例任务。
- 维护固件保持 3.4C 屏幕默认值并使用 32 MB Flash；`rev1_3` 是默认 profile，
  `rev3_x` 是不兼容二进制 profile。
- ESP32-C6 Hosted 镜像仍是运行时依赖，不属于这些 P4 产物中的 C6 烧录镜像。
- 产品工作流仍会发布可见的 `firmware_touched` 路由结果；它会跳过示例构建，
  而不是把固件修改当成纯文档修改。
- `.bin`、`.zip` 或类似镜像/归档修改还会显式标记 `release_review`。
- 未获得明确的固件范围授权时，不要在文档或示例 CI 维护中修改、重新打包或重新
  生成固件源码、二进制文件或交付压缩包。
- 成功的示例构建会生成可下载的示例 CI 产物；它们始终与审查过的工厂/交付固件
  分开。Release 仍为手动/延后流程，而不是自动产物发布路径。

## 烧录当前 CI 产物

`Flash-CI-Firmware.cmd` 只下载并烧录由 XC CI 路由器选择、与本地精确 HEAD 对应的
成功 Actions 产物。它需要 Git、GitHub CLI、带 `esptool` 的 Python、一个 head 与干净
本地 HEAD 完全相同的非草稿 PR、该 SHA 上全部产品构建工作流完整成功的 52 个产物集合，
以及显式串口参数。

```text
Flash-CI-Firmware.cmd -SelfTest
Flash-CI-Firmware.cmd -ListOnly
Flash-CI-Firmware.cmd -Port COMx
```

前两个命令是离线本地检查：不会访问 GitHub、串口硬件或烧录设备。正常模式必须提供
`-Port COMx`；GUI 会显示这个显式端口，并在写入前再次要求确认。GUI 从不擦除 flash，
对于 Arduino 条目，下载器只接受一个 schema 3 分段 ZIP。它会先拒绝不安全、重复、
冲突或链接条目，再安全展开 ZIP，并核验 `SHA256SUMS` 覆盖的精确文件集合。manifest、
规范化 `flash_args`、分段大小与哈希、Flash 容量、FQBN、产品 SHA，以及 reference-only
BSP 的版本、来源 SHA、source tree 和 component tree pin，都必须与所选 exact-HEAD
工作流身份完全一致。CI 生产端和验证器还会从该产品 SHA 的干净 source worktree
重新计算规范化 build identity：仓库相对 project 和已跟踪主 sketch、真实
`sketchLocation`、生成的 translation unit/object、编译 FQBN、USB/屏幕宏、source
include 与 application 分段必须彼此一致。原始 `build.options.json` 和
`compile_commands.json` 不进入 ZIP，只公开原文件名、大小和 SHA-256。merged 和
whole-flash 镜像会被拒绝。真实多段计划中的 bootloader 可以位于 `0x0`；
位于 `0x0` 的单文件计划会被拒绝。包内容与手工命令见
[Arduino 分段烧录指南](ARDUINO_FLASHING_ZH.md)。

打包器和验证器都会从自身已检入脚本的位置推导 trusted repository root；
`--source-root` 必须解析到同一个 Git 顶层 worktree（工作流传入自身的
`GITHUB_WORKSPACE`）。因此，即使另一个 checkout 自报的 SHA 与构建元数据彼此一致，
来自本 checkout 的脚本也会拒绝它。

Schema 3 ZIP 条目使用固定时间戳，manifest 不含墙上时钟生成字段，因此对同一组已
验证输入重复打包会得到逐字节一致的 ZIP。打包回归套件还会分别对 `flash.sh` 和
`flash.bat` 执行五种独立篡改：删除 helper 成员、删除一个分段对、修改 offset、修改
文件名及修改 flash option。即使重新计算 checksum 元数据，这十个 ZIP 负例也都必须
被验证器拒绝。

`-SelfTest` 还会在本地临时生成 schema 3 测试包和 ZIP，覆盖合法的 `0x0` 多段场景，
并检查 BSP、规范化 build identity、checksum、whole-flash、路径穿越、重复 ZIP
条目和符号链接等反例；整个过程不使用网络或串口设备。

GUI 从不擦除 flash，
并将精确 SHA、人工 PASS 进度、所选端口和日志保存到当前用户的本地应用数据目录；
已验证写入状态不会跨会话保存。
成功的 CI 产物及 `Hash of data verified` 并不能证明显示、触摸、音频、USB 或其他硬件
行为；只有逐项人工确认后才能标记 PASS。

芯片 revision 选择不能确认 PCB 或电气 revision。编译成功、CI 成功和验证写入都不能
替代 HIL 测试。触控 HIL 仍需在真实硬件上检查有响应的 `0x5D`/`0x14` 地址、坐标、
抬起事件和轮询行为。

当前检出内容中，`firmware/` 下没有被明确识别为交付物的 `.bin` 或 `.zip` 文件。
未来交付面的源码和构建说明目前尚未包含在仓库中，后续可以再添加。

获得固件维护授权后，应将目标芯片、ESP-IDF 版本、组件来源、分区表、生成产物
和验证证据与一方示例矩阵分开记录。
