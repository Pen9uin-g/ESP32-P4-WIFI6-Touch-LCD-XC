# 组件归属与依赖说明

[English](COMPONENTS.md)

本文记录本地组件候选为何保留在当前边界内。不能仅凭目录名称判断一个组件
是否可以删除。

## 注册表板级支持

示例 07 至 12 与维护中的固件都使用托管的
[`waveshare/esp32_p4_wifi6_touch_lcd_xc`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)
BSP，并精确固定为 `3.0.1`。示例中不再保留该 BSP 的 vendored 副本；`bsp_extra`
和其他无关本地组件仍保持本地边界。

官方 `3.0.1` BSP 将触控复位设为 `GPIO_NUM_NC`，而示例 08 和 09 之前的本地副本使用
GPIO23。本次迁移不会凭空添加全局 GPIO 覆盖，因为原理图证据不足。受影响开发板必须
进行真实硬件触控复位回归测试。

USB 扩展屏示例还把 `espressif/tinyusb` 精确固定为 `0.17.0~2`，这是现有
`espressif/usb_device_uac` `1.2.0` 允许的精确版本。两者都使用精确版本，可避免
未来 TinyUSB 上传静默改变 USB 描述符或 P4 PHY 行为。UAC 组件依赖受
顶层 `USB_DEVICE_UAC_COMPONENT` CMake 选项控制。常规构建保持启用；CI 的
vendor-only 命令同时关闭该选项与 `CONFIG_UAC_AUDIO_ENABLE`，因此不会再编译一个
其描述符类型已被项目 TinyUSB 配置关闭的组件。这里使用 CMake 选项，是因为基于
Kconfig 的 manifest 条件要求 ESP-IDF 6.0，而本仓库还要验证 ESP-IDF 5.5；详情见
Component Manager 的
[Kconfig 条件说明](https://docs.espressif.com/projects/idf-component-manager/en/latest/reference/manifest_file.html#kconfig-options)。

## 产品或示例本地组件

| 组件 | 当前保留本地的原因 |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | 示例专用的 SD 测试辅助和 GPIO 测试逻辑 |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | 音频/显示集成所需的板级与示例 glue |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | 本示例使用的 Espressif extractor 集成及按目标提供的预编译库 |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | 示例应用组合逻辑 |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/显示示例专用的板级 glue |

`firmware/brookesia/components/` 是单独维护的固件源码面。其 BSP 使用者同样固定为
`3.0.1`，两个 revision profile 与未改变的示例矩阵分开构建。

如果可复用的修复应当进入 Waveshare 共享组件仓库，应先获得上游修改和发布新依赖
版本的授权。未经原理图和两个显示变体核对，不要静默用共享组件替换本地板级 glue。
