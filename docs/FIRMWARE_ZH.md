# 固件源码边界

[English](FIRMWARE.md)

[`firmware/brookesia`](../firmware/brookesia/) 是本开发板系列维护中的
ESP-Brookesia 交付源码工程。它以 LCD-X 固件源码布局为基线并适配 XC 开发板，
不属于 `examples/` 下的普通示例。

## 支持的构建 profile

固件只面向 ESP32-P4 rev3.x 和 32 MB Flash 构建。两个显示 profile 需要独立构建：

| Profile | 显示屏 | 预期 FactoryOnly combine bin 名称 |
| --- | --- | --- |
| `3_4c` | 3.4C，800 × 800 | `ESP32-P4-WIFI6-Touch-LCD-3.4C-FactoryOnly-260821.bin` |
| `4c` | 4C，720 × 720 | `ESP32-P4-WIFI6-Touch-LCD-4C-FactoryOnly-260821.bin` |

固件没有 `rev1_3` 构建 profile。ESP32-P4 pre-v3 的 DSI PHY 参考源为旧版
PLL_F20M，rev3.x 为 XTAL。XC 固件及托管 BSP 将 `.phy_clk_src` 保持为 `0`，由
ESP-IDF 根据实际芯片 profile 自动选择。DPI 像素时钟始终为 80 MHz；两种 XC
显示屏均使用两条 1,500 Mbps/lane 的 DSI 通道。

## 编译与合并流程

按以下顺序使用已检入的默认配置：`sdkconfig.defaults`、
`sdkconfig.defaults.rev3_x`，以及所选显示文件（`sdkconfig.defaults.3_4c` 或
`sdkconfig.defaults.4c`）。每个 profile 必须使用独立构建目录；不要在 profile
之间复用生成的 `sdkconfig`、`managed_components/` 或 `dependencies.lock`。

```bash
cd firmware/brookesia
idf.py -B build-3_4c-rev3_x \
  -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.3_4c" build
idf.py -B build-4c-rev3_x \
  -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.4c" build
```

每个构建成功后，从对应构建目录使用该目录生成的 `flash_args` 运行
`esptool merge_bin`。上表是所需的 FactoryOnly 命名规范。合并镜像必须来自自身
成功的 profile 构建，不能复制其他镜像，也不能使用填充后的整片 Flash 镜像。

## 依赖与硬件约定

开发板 BSP 依赖为已发布的注册表组件
[`waveshare/esp32_p4_wifi6_touch_lcd_xc`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)，
且精确固定为 `3.0.1`。不要在组件 manifest 中改用未发布版本、Git URL 或本地路径，
因为这些输入不能通过 Component Registry 打包。

GT911 兼容触控有意只使用轮询。软件不配置 INT 和 RST，先探测 `0x5D`、再探测
`0x14`，并以有响应的地址初始化。不得安装触控 ISR，也不得驱动地址/复位 strap。

## CI 与验证边界

维护固件工作流与默认示例矩阵分离。路由选中固件源码时，预期构建上述两个
rev3.x 显示 profile；固件源码不会加入正常的 ESP-IDF 或 Arduino 示例发现范围。

本地维护任务只编译源码并准备按 profile 区分的 combine bin 输出，不会烧录开发板，
也不构成显示、触控、音频、摄像头、Wi-Fi 或其他硬件在环（HIL）验证。只有完成并
记录对应实机检查后，编译出的镜像才可视为已验证。
