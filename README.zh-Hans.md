# 极米神灯 · Home Assistant 集成

<div align="center">

[![hassfest](https://github.com/shadlc/xgimi-sunlight/actions/workflows/validate.yml/badge.svg)](https://github.com/shadlc/xgimi-sunlight/actions/workflows/validate.yml)
[![GitHub Release](https://img.shields.io/github/v/release/shadlc/xgimi-sunlight)](https://github.com/shadlc/xgimi-sunlight/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.10%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shadlc&repository=xgimi-sunlight&category=integration)

<img width="320" alt="极米神灯仪表盘" src="https://github.com/user-attachments/assets/13ec01b3-bd0a-47d8-9a71-f63e2c59641d">

<sub>示例仪表盘</sub>

[English](README.md) · **简体中文**

</div>

面向极米神灯（吸顶灯 + 投影仪）的本地推送集成。指令走 13145 端口的长度前缀 TCP 流，UDP
16750 作为回落通道；状态由同一条 TCP 流上的 `50023` 帧回传。**无强制联网与平台通讯需求，
零外部依赖**，所有流量都留在本地网络。

---

## 特性

- **四种灯光模式** —— 自定义、节律光、日光、观影各自独立成实体，另有总开关
- **自定义模式下可控亮度与色温**，各 10 档，色温 2700–6500 K
- **投影仪电源**，状态取自设备状态表，不靠猜测
- **遥控器全部 15 个按键** —— 既可通过 `remote` 实体发送，也有点按 / 长按按钮
- **系统音量**滑条，0–99
- **已安装应用** —— 列表从设备读取，可按名称或包名启动
- **媒体播放** —— 经 DLNA 渲染器播放图片、视频与音频，不依赖手机 App
- **按需截屏** —— 存到 `www`，可直接在仪表盘查看
- **状态自纠正** —— 每 30 秒重读灯光参数，设备漏推也不会让实体长期停在旧值
- **两种实体布局** —— 每种灯一个开关，或一个灯 + 效果选择器

## 环境要求

| 项目 | 说明 |
| --- | --- |
| Home Assistant | 2024.10 及以上（在 2026.11 验证） |
| 网络 | HA 与设备处于同一子网；协议为本地通信且不鉴权 |
| UDP 16751 | HA 主机上需可用 —— 设备的应答与状态推送发往该端口 |

## 安装

### HACS（推荐）

1. HACS → 右上角菜单 → **自定义存储库**
2. 添加 `https://github.com/shadlc/xgimi-sunlight`，类别选 **Integration**
3. 在 HACS 中搜索「XGIMI Sunlight」并下载
4. 重启 Home Assistant

### 手动

把 `custom_components/xgimi_sunlight` 复制到 `<config>/custom_components/`，重启 Home
Assistant。

## 配置

### 添加设备

1. **设置 → 设备与服务 → 添加集成**，搜索「XGIMI Sunlight」
2. 填写设备地址（例如 `192.168.1.50`，建议在路由器上做 DHCP 保留）与名称
3. 集成会与 13145 端口建立状态通道，断线自动重连

地址变化时，在集成卡片上用 **重新配置**，无需删除后重新添加。

### 选项

**设置 → 设备与服务 → XGIMI Sunlight → 配置**：

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| 灯光实体布局 | 每种模式一个开关 | 也可选择单个灯 + 效果选择器 |
| 默认灯光模式 | 自定义 | 单灯布局下未指定效果时使用的模式 |
| 预留 UDP 16751 | 开 | 关闭后收不到指令应答与拒绝判定 |

## 实体

每个设备创建 34 个实体。

### 灯光

| 实体 | 说明 |
| --- | --- |
| `light.*_custom_lamp` | 自定义模式，可调亮度（1–10 档）与色温（2700–6500 K） |
| `light.*_rhythm_lamp` | 节律光，仅开关 |
| `light.*_daylight_lamp` | 日光，仅开关 |
| `light.*_movie_lamp` | 观影，仅开关 |
| `switch.*_lamp` | 总开关，打开时恢复上次使用的模式 |

四种模式互斥 —— 设备只保存一个 `ceilingLampMode` 值。只有自定义灯暴露亮度与色温，另外三个
预设由设备自带配置驱动，因此只做开关。写亮度或色温会把设备切到自定义模式。

### 投影仪

| 实体 | 说明 |
| --- | --- |
| `switch.*_projector` | 电源。`POWER_SLEEP_SYSTEM_UI` 为 `1` 时显示为开；开机在标志为待机时只发一次 `power` 键，关机发送待机帧 |
| `remote.*_remote` | 15 个按键，通过 `remote.send_command` 发送，支持 `num_repeats`、`delay_secs`、`hold_secs` |

### 控制

| 实体 | 说明 |
| --- | --- |
| `number.*_volume` | 系统音量，0–99（固件对 100 会读回 0） |
| `select.*_remote_key` | 「点按 / 长按」按钮作用的按键 |
| `select.*_app` | 「打开应用」按钮要启动的应用，列表来自设备 |
| `text.*_command` | 存放口令；`button.*_send_command` 交给语音助手 |
| `text.*_media` | 存放地址或路径；`button.*_play_media` 播放 |

### 按钮

| 实体 | 说明 |
| --- | --- |
| `button.*_press` / `button.*_hold` | 对选中的按键执行点按或长按 |
| `button.*_power_menu` | 打开关机菜单 |
| `button.*_screenshot` | 按下遥控器截图键 |
| `button.*_screen_off` | 关闭光机 |
| `button.*_mute` | 静音 |
| `button.*_auto_focus` / `button.*_manual_focus` | 对焦 |
| `button.*_settings` / `button.*_home` / `button.*_back` / `button.*_menu` | 导航 |
| `button.*_send_command` / `button.*_play_media` / `button.*_stop_media` | 执行输入框内容、停止播放 |
| `button.*_open_app` | 打开选中的应用 |
| `button.*_reboot` / `button.*_clean_memory` / `button.*_check_for_updates` | 维护 |
| `button.*_listen_to_music` / `button.*_exit_music_mode` | 听歌模式 |

21 个按钮全部默认启用。

### 摄像头

| 实体 | 说明 |
| --- | --- |
| `camera.*_screen` | 最近一次截屏；只有调用 `xgimi_sunlight.screenshot` 才会重新抓取 |

## 服务

| 服务 | 说明 |
| --- | --- |
| `xgimi_sunlight.send_command` | 把文本交给设备语音助手，用于尚无帧结构的动作 |
| `xgimi_sunlight.press_key` | 按名称点按或长按遥控器按键 |
| `xgimi_sunlight.play_media` | 经 DLNA 渲染器播放图片、视频或音频 |
| `xgimi_sunlight.stop_media` | 结束播放会话 |
| `xgimi_sunlight.screenshot` | 截取画面并把 JPEG 存到 `www` |
| `xgimi_sunlight.open_app` | 按 `package` 或 `app` 名称启动已安装应用 |

```yaml
action: xgimi_sunlight.press_key
data:
  key: power
  hold_secs: 1
```

`play_media` 接受设备可下载的地址，或 HA 主机上的文件：

```yaml
action: xgimi_sunlight.play_media
data:
  path: /config/www/photo.jpg   # 绝对路径
  # path: www/photo.jpg        # 同一个文件
  # path: media/holiday.mp4    # 媒体目录
```

本地文件通过 HA HTTP 服务上的随机令牌发布，设备无需任何凭据。自定义集成没有上传对话框，
文件需先放到主机上（Samba、SSH 或文件编辑器插件）。不填来源时，`play_media` 会重播上一次
成功播放的内容。

## 媒体播放

设备通过 DLNA 渲染器播放，渲染器地址由 SSDP 发现，端口并不固定。图片与 MP4 视频已在真机
验证，其它格式按对应 DLNA 类透传。

播放会持续到使用遥控器或调用 `xgimi_sunlight.stop_media`。停止会结束会话，投影回到设备
自己的待机画面（环境照片墙），而不是之前正在运行的 App。仅涉及画面，不改动灯光。

`play_media` 需要渲染器在运行。设备休眠或前台被音乐播放器等应用占用时渲染器不可用，此时
服务会明确报错，而不是静默失败。

## 截屏

```yaml
action: xgimi_sunlight.screenshot
response_variable: shot
```

服务把画面写入 `www/xgimi_screen.jpg`，并返回路径与 `/local/` 地址。截屏是**按需**行为：
每次截图都会闪一下画面，并在设备的 `/storage/emulated/0/Pictures/Screenshots/` 留下 JPEG，
因此不做任何自动截图。

抓图同一时间只允许一个实例 —— 设备只处理单个请求，并发调用会直接返回
`A screen capture is already running` 而不是排队。设备侧一次抓图约 0.6–1.2 秒，传输本身
只需 50–100 毫秒。

## 仪表盘

`dashboards/xgimi_dashboard.yaml` 是英文示例，`dashboards/xgimi_dashboard.zh-Hans.yaml` 是
中文示例。复制到配置目录后注册：

```yaml
lovelace:
  dashboards:
    xgimi-lamp:
      mode: yaml
      title: 极米神灯
      icon: mdi:lamp
      show_in_sidebar: true
      filename: xgimi_dashboard.zh-Hans.yaml
```

仪表盘按实体前缀 `xgimi_sunlight` 编写；设备名不同时请相应调整实体 ID。

## 状态与行为

| 项目 | 说明 |
| --- | --- |
| 状态来源 | TCP 13145 上的 `50023` 帧；设备在变化时推送，不支持轮询 |
| 初始值 | 每次（重）连接时对四个灯光参数各发一次 `50040` 查询 |
| 自纠正 | 每 30 秒重读四个灯光参数，因为设备并非每次变化都推送 |
| 预设模式 | 日光、节律光、观影回报设备自带配置的百分比数值，仅作为属性展示 |
| 电源变化 | 不推送；由 30 秒重读保证开关状态准确 |
| 降级模式 | UDP 16751 绑定失败时指令仍可用，但收不到应答与拒绝判定，并会生成修复提示 |
| 休眠设备 | 只有 ICMP 有响应；TCP 13145、UDP 16750 与渲染器全部关闭 |

## 排错

| 现象 | 原因与处理 |
| --- | --- |
| 实体显示不可用 | 设备休眠。用遥控器或厂商 App 开机 |
| 指令没反应但状态仍在更新 | 前台应用关闭了 UDP 16750；指令已优先走 TCP，这只影响回落通道 |
| `play_media` 提示渲染器未运行 | 设备休眠或前台被应用占用。唤醒设备或退出应用 |
| 灯实体与实际不同步 | 最多等 30 秒的下一次重读；持续异常请检查日志中的 `50040` 应答 |
| 截图慢或闪屏 | 均为设备行为：抓图会重新初始化面板，无法做到无感 |
| 提示已有截图在进行 | 设备同一时间只处理一个请求，等当前抓图结束后重试 |
| 端口 16751 被占用 | 其它实例或程序占用了端口。关闭「预留 UDP 16751」以降级运行 |

## 自动化示例

```yaml
# 日落时把自定义灯调到暖色
action: light.turn_on
target:
  entity_id: light.xgimi_sunlight_custom_lamp
data:
  brightness: 200
  color_temp_kelvin: 3000
```

```yaml
# 长按主页打开多任务
action: xgimi_sunlight.press_key
data:
  key: home
  hold_secs: 1
```

## 协议

逆向记录与报文格式见 [`docs/PROTOCOL.zh-Hans.md`](docs/PROTOCOL.zh-Hans.md)：三种请求形态、
TCP 帧（`FF FF E0 4A` + 大端长度 + JSON）、结构化灯光 API（`50040`/`50041`）、状态键、
截图应答与端口扫描结果。

## 开发

```powershell
python -m pip install ruff==0.17.6
python -m ruff check custom_components
python -m ruff format --check custom_components
```

## 参与贡献

欢迎提交 issue 与 pull request。每个 PR 只做一件事，跑通上面两条 ruff 命令，并在真机上验证
行为 —— [`docs/PROTOCOL.zh-Hans.md`](docs/PROTOCOL.zh-Hans.md) 记录的都是实测结论。

## 许可证

[MIT](LICENSE)

> 非官方集成，与极米科技无隶属或背书关系。

## 相关项目

- [Lzk119/XGMI_HA](https://github.com/Lzk119/XGMI_HA) —— 同型号灯具的另一份 HA 集成，通过结构化灯光 API 控制灯与投影开关。
- [manymuch/Xgimi-4-Home-Assistant](https://github.com/manymuch/Xgimi-4-Home-Assistant) —— 通用极米投影集成，使用文本口令而非键码。
