# ESP-Brookesia 类手机界面示例

[English](README.md)

本示例面向 ESP32-P4-WIFI6-Touch-LCD-XC 开发板，运行 ESP-Brookesia 类手机
界面。它使用仓库内的 XC 板级支持组件和 Brookesia 集成代码，显示分辨率由
开发板配置选择。

## 硬件

- ESP32-P4-WIFI6-Touch-LCD-XC，配 3.4C 或 4C 显示屏；
- 连接开发板 USB-UART 接口的数据线；
- 当前配置启用时所需的音频、存储、摄像头或 Hosted Wi-Fi 外设。

修改显示、触控、音频、存储或协处理器设置时，请参考仓库的
[硬件审计](../../../docs/HARDWARE_ZH.md)和
[开发板原理图](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)。
本示例不是上游项目中面向 ESP32-P4-Function-EV-Board、分辨率为 1024 × 600
的示例。

## 配置、编译与烧录

仓库默认配置选择 3.4C 的 800 × 800 显示屏和开发板实际的 32 MB NOR Flash。
4C 型号请在 **Board Support Package Configuration → LCD → Select LCD type**
中选择 **720 × 720 4-inch Display**。运行 `idf.py menuconfig` 检查
ESP-Brookesia 和板级设置，然后执行：

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

将 `PORT` 替换为开发板串口。退出串口监视器请按 `Ctrl-]`。仓库已经包含产品
示例集成并声明所需的托管依赖，构建此工程不需要另外克隆上游示例。

该示例的 3.4C 与 4C 两种显示配置都会进入仓库 ESP-IDF `v5.5.5` 和 `v6.0.2`
矩阵。CI 验证可以编译，不能替代实体显示、触控、音频或 Wi-Fi 兼容性测试。
