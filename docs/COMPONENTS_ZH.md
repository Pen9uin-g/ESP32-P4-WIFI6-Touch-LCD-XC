# 组件归属与依赖说明

[English](COMPONENTS.md)

本文记录本地组件候选为何保留在当前边界内。不能仅凭目录名称判断一个组件
是否可以删除。

## 注册表板级支持

ESP-IDF 示例在 manifest 中声明 Waveshare 的
`waveshare/esp32_p4_wifi6_touch_lcd_xc` 以及相关 Espressif/LVGL 组件。仓库中
多个示例下的 `waveshare__esp32_p4_wifi6_touch_lcd_xc` 是带板级头文件和
manifest 的注册表形态 BSP 源码，为支持当前矩阵而保持一致。未来如果改为只下载
managed component，必须先核对组件版本、支持的 IDF 分支、生成配置和两个显示
变体的板级行为。

## 产品或示例本地组件

| 组件 | 当前保留本地的原因 |
| --- | --- |
| `examples/esp-idf/05_sdmmc/components/sd_card` | 示例专用的 SD 测试辅助和 GPIO 测试逻辑 |
| `examples/esp-idf/08_lvgl_demo_v9/components/bsp_extra` | 音频/显示集成所需的板级与示例 glue |
| `examples/esp-idf/10_mp4_player/components/esp_extractor` | 本示例使用的 Espressif extractor 集成及按目标提供的预编译库 |
| `examples/esp-idf/11_esp_brookesia_phone/components/brookesia_app_squareline_demo` | 示例应用组合逻辑 |
| `examples/esp-idf/12_usb_extend_screen/components/bsp_extra` | USB/显示示例专用的板级 glue |

`firmware/brookesia/components/` 是单独维护的固件源码面。本次仓库工作只盘点它，
不会修改或加入默认示例 CI。

如果可复用的修复应当进入 Waveshare 共享组件仓库，应先获得上游修改和发布新依赖
版本的授权。未经原理图和两个显示变体核对，不要静默用共享组件替换本地板级 glue。
