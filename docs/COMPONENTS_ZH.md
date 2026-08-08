# 组件归属与依赖说明

[English](COMPONENTS.md)

本文记录本地组件候选为何保留在当前边界内。不能仅凭目录名称判断一个组件
是否可以删除。

## 注册表板级支持

示例 07 至 12 都带有 registry 形态的本地
`waveshare/esp32_p4_wifi6_touch_lcd_xc` BSP 2.0.0。对应一方 manifest 现在精确要求
`2.0.0`，不再使用浮动通配符，未来 registry 版本不能静默替换仓库内源码。

这六份源码不是可互换的缓存输出。示例 08 和 09 带有本板专用的 `GPIO23` GT911
复位定义，其余四份将触控复位 GPIO 保持为未连接；另有两份只存在语义等价的 CMake
依赖顺序差异。在这些差异上游化或被证明不再需要前，本地副本应继续保留。

[Component Registry](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_xc)
当前发布的是 `3.0.1`，相对本地 `2.0.0` 属于 semver 主版本变化并增加了一个依赖。
未来迁移到 managed component 前，必须核对导出 API、Kconfig、GPIO23 行为、两条
ESP-IDF 版本线、P4 revision 要求以及两个显示型号。

USB 扩展屏示例还把 `espressif/tinyusb` 精确固定为 `0.17.0~2`，这是现有
`espressif/usb_device_uac` `1.2.0` 允许的精确版本。两者都使用精确版本，可避免
未来 TinyUSB 上传静默改变 USB 描述符或 P4 PHY 行为。

## 产品或示例本地组件

| 组件 | 当前保留本地的原因 |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | 示例专用的 SD 测试辅助和 GPIO 测试逻辑 |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | 音频/显示集成所需的板级与示例 glue |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | 本示例使用的 Espressif extractor 集成及按目标提供的预编译库 |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | 示例应用组合逻辑 |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/显示示例专用的板级 glue |

`firmware/brookesia/components/` 是单独维护的固件源码面。本次仓库工作只盘点它，
不会修改、重新固定依赖或加入默认示例 CI。

如果可复用的修复应当进入 Waveshare 共享组件仓库，应先获得上游修改和发布新依赖
版本的授权。未经原理图和两个显示变体核对，不要静默用共享组件替换本地板级 glue。
