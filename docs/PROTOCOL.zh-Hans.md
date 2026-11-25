# 极米神灯协议参考

极米神灯（吸顶灯 + 投影仪）的局域网控制协议。数值在真机（`deviceStateInfo.apiVersion =
1.0.4`）上测得；表格中标为「未验证」的动作只是 App 常量。引用 App 类名是为说明报文来源。

[English](PROTOCOL.md) | **简体中文**

> 非官方接口。极米未公开此协议，固件升级可能改变行为。

---

## 1. 传输层

指令走 TCP 13145，回落到 UDP 16750；状态只走 TCP 13145（见第 7 节）。

| 项目 | 值 |
| --- | --- |
| 指令传输 | UDP 16750，无握手、无鉴权 |
| 应答目标 | 固定发往 `控制端:16751`，与源端口无关 |
| 状态传输 | TCP `设备:13145`，长度前缀帧（见第 7 节） |
| 编码 | UTF-8 JSON；非 ASCII 文本直接写入，不用 `\uXXXX` |
| ICMP | 不产生端口不可达，无法用 `connect()` 探活 |
| 图片显示 | DLNA MediaRenderer，端口动态，经 SSDP 发现（见第 8 节） |

### 绑定与套接字

- 必须绑 16751 才能收到应答：任意源端口都能执行指令，但只有 16751 收应答；集成独占该端口。
- 不要 `connect()` UDP 套接字：应答来自随机临时端口（58501、33961…），连接过的套接字会被内核丢包。

---

## 2. 请求

### 2.1 按键

```json
{"action":50036,"commonCmd":{"action":"3","code":"11","type":"inst"}}
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `action` | int | 固定 `50036` |
| `commonCmd.action` | str | `"3"` 点按，`"1"` 长按（一次按下发一帧，无连发） |
| `commonCmd.code` | str | 键码（见 5.1） |
| `commonCmd.type` | str | 固定 `"inst"` |

### 2.2 单次动作

```json
{"action":50021}
```

`action` 为动作编号（见 5.2）。

### 2.3 文本 / 语音助手

```json
{"action":20000,"controlCmd":{"data":"音量调到 50%","delayTime":0,"mode":5,"time":0,"type":0},"msgid":"2"}
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `controlCmd.data` | str | 自然语言指令，接受中文 |
| `controlCmd.delayTime` | int | `0` |
| `controlCmd.mode` | int | `5`，文本通道 |
| `controlCmd.time` | int | `0` |
| `controlCmd.type` | int | `0` |
| `msgid` | str | `"2"`，字符串 |

`data` 由设备语音助手解析，可覆盖本协议未建模的行为（如「音量调到 50%」），但依赖语义理解，不适合用于电源控制。

变体：`clean_memory` 用 `mode:9, type:2`，无 `data`。

---

## 3. 应答

| `action` | 含义 | 关键字段 |
| --- | --- | --- |
| `20001` | 文本指令成功 | 回显 `msgid`、`agreement` |
| `20002` | 文本指令失败 | `extraInfo.message`（实测 `"未知错误"`） |
| `5xxxx` | 按键/动作回显 | `status.state`（`1` 已接受） |
| `50023` | 状态推送或查询应答 | `deviceStateInfo.state[]` |

### 成功

```json
{"action":20001,"endScreenCapTime":0,"msgid":"2","startScreenCapTime":0,"type":0,
 "agreement":{"agreementType":0,"isTcp":true,"msgId":"2","phoneIp":"192.168.1.10","port":13145}}
```

### 按键/动作回显

```json
{"action":50036,"msgid":"0","status":{"state":1},"type":0,"agreement":{...}}
{"action":50021,"msgid":"0","status":{"state":1},"type":0,"agreement":{...}}
```

### 状态推送

```json
{"action":50023,"deviceStateInfo":{"apiVersion":"1.0.4",
  "state":[{"curChildItem":"6","key":"ceilingLampMode"}]},"msgId":0,
 "agreement":{"agreementType":2,"isTcp":true,"port":13145}}
```

推送只在 TCP 13145 上送达；只绑 16751 的集成收不到任何状态。

### 状态查询（订阅）

`{"action":50023,"msgid":"70002"}` 返回完整状态表，并让该连接进入订阅状态：后续变化以单条 `50023` 帧推送。

```json
{"action":50023,"deviceStateInfo":{"apiVersion":"1.0.4","state":[
  {"key":"lightSwitch","value":"1"},
  {"curChildItem":"6","key":"ceilingLampMode"}]},
 "msgId":1795279299763,"agreement":{"agreementType":2,"isTcp":true,"port":13145}}
```

取值位置按 key 不同：`lightSwitch` 用 `value`，`ceilingLampMode` 用 `curChildItem`。

---

## 4. 状态键

灯的状态完整；投影仪只有系统键，没有自己的电源标志（见 4.2）。

### 4.1 灯（变化时经 `50023` 推送）

| Key | 含义 | 取值位置 | 值 |
| --- | --- | --- | --- |
| `lightSwitch` | 灯电源 | `value` | `"0"` 关，`"1"` 开 |
| `ceilingLampMode` | 灯光模式 | `curChildItem` | `"0"` 自定义，`"1"` 节律光，`"6"` 日光，`"10"` 观影 |
| `lightBrightness` | 亮度 | `value` | `1`…`10` |
| `lightColorTemp` | 色温 | `value` | `1` 最暖（约 2700 K）… `10` 最冷（约 6500 K） |

### 4.2 系统键（只在 `50023` 查询应答中）

查询返回约 12 个键，其中：

| Key | 实测值 | 含义 |
| --- | --- | --- |
| `VOLUME_SYSTEM_UI` | `"14"` | 系统音量 |
| `SHUT_SCREEN_SYSTEM_UI` | `"4"` / `"3"` | 光机：`4` 出画面，`3` 关闭 |
| `POWER_SLEEP_SYSTEM_UI` | `"1"` / `"0"` | 投影仪电源：`1` 运行，`0` 待机（灯仍在线） |
| `POWER_OFF_SYSTEM_UI` | `"1"` | 恒为 `1`，不代表电源 |
| `TIME_POWER_OFF_SYSTEM_UI` | `"-1"` | 定时关机，`-1` 未设置 |
| `SEND_COUNT_DOWN_MINUTE_TIME_SYSTEM_UI` | `"-1"` | 倒计时 |
| `CONFIG_KEY_SUPPORT_FEATURE_LIST`、`CONFIG_KEY_RESOLUTION_AND_FPS` | — | 投屏能力 |
| `MODE_SCREEN_SAVER`、`VIDEO_HISTORY_LIST_HOME`、`IMMERSED_HEALTHY`、`image` | — | 屏保、历史、沉浸场景 |

其余键携带 `com.xgimi.atmosphere`（屏保）与 `com.xgimi.home.immersed` 的长 JSON。

### 4.3 结构化灯光接口

四个灯光参数共用一个 action，由数字 `commonCmd.type` 选择（`com.xgimi.zhushou.devices.cp02light.Cp02LightUtil`）：

```
写: {"action":50041,"commonCmd":{"type":"<0..3>","value":"<n>"},"msgid":"2"}
读: {"action":50040,"commonCmd":{"type":"<0..3>"},"msgid":"70002"}
```

| `type` | 参数 | 范围 | 状态键 |
| --- | --- | --- | --- |
| `"0"` | 电源 | `"0"` / `"1"` | `lightSwitch` |
| `"1"` | 色温 | `1`…`10` | `lightColorTemp` |
| `"2"` | 亮度 | `1`…`10` | `lightBrightness` |
| `"3"` | 模式 | `"0"`/`"1"`/`"6"`/`"10"` | `ceilingLampMode` |

读取应答原文：

```json
{"action":50040,"featureDetailInfo":{"key":"lightSwitch","value":"1"},"msgid":"0","type":0,"agreement":{...}}
{"action":50040,"featureDetailInfo":{"curChildItem":"6","key":"ceilingLampMode"},"msgid":"0","type":3,"agreement":{...}}
```

电源、亮度、色温在 `value`；模式在 `curChildItem`，与 `50023` 的取值规则一致。

行为：

- 四个参数都能精确回读（`lightBrightness`、`lightColorTemp` 已验证 1/5/10）。
- 只接受整数：`2.5`、`5.5` 被忽略且无 ACK、无变化；`5`、`6` 立即生效。
- 写亮度或色温会把灯切到模式 `0`（自定义）。
- 缺 `commonCmd.type` 时设备只回空 `20001`，不执行。
- 集成在启动时与每次 TCP 重连后按 `0→2→1→3` 逐项读取，因为订阅应答里没有灯光键。

### 4.4 投递方式

- TCP 上每个变化只发一帧；查询应答与推送可能重复同一值，需去重。
- 事件驱动：`50023` 只在变化或查询时出现；与当前状态相同的指令只回 `20001`，不推送。

---

## 5. 指令表

### 5.1 按键（`action:50036`）

| 名称 | 键码 | 名称 | 键码 |
| --- | --- | --- | --- |
| `left` | 1 | `home` | 8 |
| `right` | 2 | `volume_up` | 9 |
| `up` | 3 | `volume_down` | 10 |
| `down` | 4 | `power`（切换） | 11 |
| `ok` | 5 | `settings` | 12 |
| `back` | 6 | `auto_focus` | 14 |
| `menu` | 7 | `screenshot` | 120 |
| `power_menu` | 131 | | |

### 5.2 单次动作

| `action` | 功能 | 已真机验证 |
| --- | --- | --- |
| `50021` | 关机（显式，`OPEN_DORMANT`） | 是 |
| `50040` | 读灯光参数（`commonCmd.type`） | 是 |
| `50041` | 写灯光参数（`commonCmd.type` + `value`） | 是 |
| `50004` | 听歌模式 | 否 |
| `50008` | 手动对焦 | 否 |
| `50012` | 静音 | 否 |
| `50015` | 熄屏 | 是 |
| `50029` | 重启 | 否 |
| `50030` | 检查更新 | 否 |

App 中 `VcontrolCmd` 字段初始值给出的其它常量：`50005` 自动 K 歌、`50006` 投影模式、`50007` 切换 HDMI、`50009` 音量、`50013` 退出 K 歌、`50014` 音效模式、`50016` 亮度模式、`50017` 亮度值、`50018/50019/50020` 红/绿/蓝亮度、`50025` 图像模式、`50026` 3D 模式、`50027` 登录、`50028` 自动 KST、`50031` 缩放界面、`50032/50033/50034` 幕布开/停/关、`50035` 历史播放、`50042` 会员信息。

---

## 6. 投影仪电源

| 状态 | `POWER_SLEEP_SYSTEM_UI` | `SHUT_SCREEN_SYSTEM_UI` | 网络 |
| --- | --- | --- | --- |
| 运行 | `"1"` | `"4"` | UDP 16750 与 TCP 13145 均开放 |
| 待机，灯仍供电 | `"0"` | `"3"` | TCP 13145 开放 |
| 未开机 | — | — | 端口全部关闭，仅 ICMP 可达 |

`POWER_SLEEP_SYSTEM_UI` 是电源标志：`"1"` 表示投影仪运行，`"0"` 表示待机且灯仍供电。
`SHUT_SCREEN_SYSTEM_UI` 描述光机状态，`"4"` 为出画面、`"3"` 为关闭，不能作为电源判据。

未开机时设备不接受任何指令，只回应 ICMP，需先用遥控器或手机 App 开机，网络接口才会应答。

- 关机：发送 `50021`，显式且幂等。
- 开机：从待机状态发一次 `power` 键，即 `50036` 加键码 `11`。该键为切换，发送前先读
  `POWER_SLEEP_SYSTEM_UI`，仅在值为 `"0"` 时发送。
- 刷新：电源变化时设备不推送该标志，需补发 `50023` 查询后重新读取。

---

## 7. TCP 13145（状态通道）

每个应答都带 `agreement: {"isTcp":true,"port":13145}`。帧格式（`com.xgimi.control.connect.protocol.ProtocolFactory`）：

```
FF FF E0 4A | int32 大端 payload 长度 | UTF-8 JSON（设备发出的帧尾部多 \n）
```

握手：

1. 连接 `设备:13145`。
2. 发送 `{"action":50023,"msgid":"70002"}`（`msgid` 固定 `70002`）。
3. 该连接开始收到 `50023` 推送。

| 步骤 | 结果 |
| --- | --- |
| 直接写裸 JSON | 无响应，帧头必需 |
| 发带帧头的 `50023` 查询 | 返回完整状态表 |
| UDP 发灯光指令后 | 已建立的连接收到对应 `50023` 推送 |

端口可连只说明控制服务在线：灯开着时，投影待机期间它仍然开放。电源状态由 `POWER_SLEEP_SYSTEM_UI` 决定。

订阅应答不含灯光状态：即使灯开着，`50023` 查询也只返回 12 个系统键（没有 `lightSwitch` / `ceilingLampMode`）。灯光状态只以变化推送到达，因此 Home Assistant 重启后开关实体先用 `RestoreEntity` 沿用上次状态，直到设备发生改变。

### 7.1 其它端口（已扫描，均不是入口）

| 端口 | 结论 |
| --- | --- |
| 53 | 可用的 DNS 服务器 |
| 1414 / 1182 / 1288 | UPnP/DLNA MediaRenderer（Platinum/1.0.5.13），端口随重启变化 |
| 7001 / 7002 / 7100 | AirPlay / RAOP（`AirTunes/220.68`） |
| 8080 | 可连接，不回应任何数据并关闭连接 |
| 10100 | 需签名的 HTTP JSON API：`{"status":-1,"message":"Vertify Failed!"}` |
| 16741 | 文件服务器：真实路径回 `200 image/jpeg`，其它回空 `200`（见第 9 节） |
| 12584 | 连接即发 `b'\x03tt'`，用途未知 |
| 12583 / 12585 / 15735 / 15737 | 无 banner |

---

## 8. 媒体播放（DLNA 渲染器，动态端口）

设备是 Platinum UPnP MediaRenderer，图片、视频、音频都可走标准 UPnP，无需厂商通道。

渲染器的 HTTP 端口不固定，重启后观察到过 1414、1182、1288。每次都要重新发现：

```
单播 UDP M-SEARCH -> <设备>:1900
  HOST: <设备>:1900, MAN: "ssdp:discover", MX: 2,
  ST: urn:schemas-upnp-org:device:MediaRenderer:1
回包头: LOCATION: http://<设备>:<端口>/
```

组播 SSDP 常被过滤，但发往设备地址的单播查询有应答（`Server: UPnP/1.0 DLNADOC/1.50 Platinum/1.0.5.13`、`USN: uuid:<MAC>-dmr::...`）。`GET` 该 `LOCATION` 取设备描述：`friendlyName` 极米神灯、`UDN uuid:<MAC>-dmr`、`DMR-1.50`，以及 AVTransport 控制地址 `/AVTransport/<UDN 后缀>/control.xml`。

1. 发 `SetAVTransportURI`：`CurrentURI` 指向设备可访问的文件，`CurrentURIMetaData` 为与媒体匹配的 DIDL-Lite：

   | 媒体 | `upnp:class` | `protocolInfo` 示例 |
   | --- | --- | --- |
   | 图片 | `object.item.imageItem.photo` | `http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_CI=0` |
   | 视频 | `object.item.videoItem` | `http-get:*:video/mp4:DLNA.ORG_OP=01;DLNA.ORG_CI=0` |
   | 音频 | `object.item.audioItem.musicTrack` | `http-get:*:audio/mpeg:DLNA.ORG_OP=01;DLNA.ORG_CI=0` |

   ```xml
   <DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
              xmlns:dc="http://purl.org/dc/elements/1.1/"
              xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
     <item id="1" parentID="0" restricted="1">
       <dc:title>photo</dc:title>
       <upnp:class>object.item.imageItem.photo</upnp:class>
       <res protocolInfo="http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_CI=0">http://192.168.1.10:8123/photo.jpg</res>
     </item>
   </DIDL-Lite>
   ```

2. 发 `Play`：`InstanceID 0`、`Speed 1`。

实测：每次调用都回 `200`，`GetMediaInfo` 报出 URL 与时长，`GetTransportInfo` 报 `PLAYING`。静态图与 H.264/AAC MP4 都整屏渲染；播放中抓屏能拍到视频帧，说明没有另开窗口。音频遵循同一约定但未试听。文件由设备自行下载，因此 URL 必须从设备可达且不需要鉴权；集成为此把本地文件挂在 Home Assistant HTTP 服务的随机令牌路径下。

`Stop` 结束会话，投影仪回到自己的待机画面（环境照片墙），不是上一个应用；电源与灯不受影响。再次 `SetAVTransportURI` 会替换当前内容。

厂商的图片动作在该固件上均不可用：`70000`（照片墙预览）只回 `status.state: 1` 不取图；`30200`（`customPlay`，`mediatype 22`，tag `WALL_1000`）会下载文件、上报 `30234 downloadInfo`，最后以 `progress: -1` 失败；`70002`（打开应用）只接受由云端模板拼出的 intent URI；`42000`（艺术模式）只回 `ardModeInfo`。

---

## 9. 截图（`30235`）

1. 在 TCP 状态通道（第 7 节）发：

   ```json
   {"action":20000,"controlCmd":{"mode":9,"type":1},"msgid":"2"}
   ```

   `mode` 9 配 `type` 1 选中截图处理；随后先回一条 `20001`，其中 `startScreenCapTime` 与 `endScreenCapTime` 均为 0。

2. 截图结果作为第二帧到达：

   ```json
   {"action":30235,"endScreenCapTime":1795368315590,"imagePath":"http://%s:16741/storage/emulated/0/Pictures/Screenshots/Screenshot_11-23-01-25-15.jpg","startScreenCapTime":1795368315564,"type":0}
   ```

   `%s` 是设备地址的字面占位符。每次截图都会在 `/storage/emulated/0/Pictures/Screenshots/` 下新增一个文件。

3. `GET` 该 URL。16741 的文件服务器回 `200 image/jpeg`；其它路径一律回空 `200`。该服务只读：对截图路径发 `DELETE`/`PUT` 仍返回同样内容，文件不被删除。

### 变体与副作用

只有 `type: 1` 会截图。`type: 0` 与 `type: 2` 只回 `20001`；`data` 被忽略，填 `/data/local/tmp` 或 `DCIM` 仍会落到 `Pictures/Screenshots/Screenshot_<时间戳>.jpg`。每次截图都会让投影闪一下并留下一个无法经文件服务器删除的 JPEG，也没有可用的 shell 去清理（见 7.1），因此只能按需截图。

---

## 10. 设备识别

| 方式 | 判据 |
| --- | --- |
| 协议探测（最可靠） | 文本指令回 `20001`；随后 `50023` 含 `ceilingLampMode` / `lightSwitch` |
| mDNS | `_airplay._tcp` / `_raop._tcp` 服务名带产品名 |
| 厂商 OUI | `4C:24:CE`，四川爱联（Wi-Fi 模组） |
| TCP 8080 | Android Debug Database 页面（安卓设备） |

---

## 11. 已装应用与其它模式

应用列表与打开应用共用 `action:20000` 的 `mode:7`：

| 步骤 | 报文 | 应答 |
| --- | --- | --- |
| 列表 | `{"action":20000,"controlCmd":{"mode":7,"type":3},"msgid":"2"}` | `30236`，`imagePath` 指向 `http://%s:16741/data/user/0/com.xgimi.vcontrol/app_appDatas/list` |
| 打开 | `{"action":20000,"controlCmd":{"mode":7,"type":1,"data":"<包名>"},"msgid":"2"}` | `20001` |

列表是设备文件服务器上的一份 URL 编码 JSON：

```json
{"appList":[{"appName":"QQ音乐","packageName":"com.tencent.qqmusictv",
             "versionCode":"9020008","systemApp":false}]}
```

卸载用 `type:2`，同样带 `data` 字段（未验证）。

四种灯光模式之外的模式：

| 动作 | 含义 |
| --- | --- |
| `50004` | 进入听歌模式（熄屏，仅音频） |
| `50013` | 退出听歌模式 |
| `50021` | 待机 |
| `50025` | 图像模式（`selectMode` 载荷） |
| `50026` | 3D 模式 |
| `50014` | 音效模式 |

---

## 12. 音量与光机

`50009` 设置音量，`VOLUME_SYSTEM_UI` 回报，无需读接口。写入后约 2 秒，设备用一条 `50023` 帧推送新值。

| 动作 | 报文 | 状态键 | 取值 |
| --- | --- | --- | --- |
| `50009` | `{"action":50009,"commonCmd":{"volume":"40"},"msgid":"2"}` | `VOLUME_SYSTEM_UI` | `0`-`99`；`100` 会读回 `0`，故集成止于 `99` |

`50015` 只能关光机。出画面时 `SHUT_SCREEN_SYSTEM_UI` 为 `4`，下发下面这条空帧变为 `3`：

```json
{"action":50015,"commonCmd":{},"msgid":"2"}
```

值为 `3` 时再发同一帧不会恢复画面，所以它不是开关。`ToolManager.sendTurnOn` 与 `sendTurnOff` 都编译成这一帧，这也是 App 只用它关画面的原因。要恢复画面，集成改发电源键（`11`），与投影开关的行为一致。
