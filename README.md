# 桌面灵动交互与状态聚合软件 V1.0.1

产品名：灵动岛（Dynamic Island for Windows）

一个基于 PySide6 的 Windows 桌面工具，将“灵动岛”交互体验引入桌面端。项目采用插件化架构，支持媒体控制、天气、电池、剪贴板历史、系统监控与生产力快捷工具等功能。

## 功能特性

- 灵动岛主窗口：悬停展开、收起动画、托盘菜单、窗口锁定与主题感知
- 插件化扩展：通过插件管理器动态加载功能模块
- 媒体控制：播放/暂停、上下曲、音量以及媒体标题和歌手信息
- 系统信息：CPU/内存监控、网络状态、电池电量与充电状态提示
- 生产力工具：区域截屏、录屏指示、剪贴板历史快捷唤出
- 快捷交互：支持窗口快捷键和三色快捷点自定义动作

## 技术栈

- Python 3.10+
- PySide6（GUI）
- psutil（系统信息）
- PyYAML（配置）
- pytest（测试）
- PyInstaller（打包）

## 目录结构

```text
灵动岛/
├─ src/                    # 应用主代码
│  ├─ core/                # 核心事件机制
│  ├─ ui/                  # 主界面与交互组件
│  ├─ plugins/             # 插件基类与管理器
│  └─ utils/               # 配置、日志、主题工具
├─ plugins/                # 具体插件实现
├─ tests/                  # 单元测试与质量脚本
├─ docs/                   # PRD、架构与报告文档
├─ demo/                   # HTML 原型示例
├─ build.py                # 打包脚本
└─ requirements.txt        # 依赖清单
```

## 使用 Windows 可执行文件

1. 在本项目的 GitHub Releases 页面下载 `DynamicIsland.exe`，放入一个可写的文件夹。
2. 双击运行。程序会在屏幕顶部显示灵动岛，并在 Windows 通知区域显示托盘图标；如果没有看到图标，可查看通知区域的隐藏图标。
3. 将鼠标移到灵动岛上展开模块，移出后收起。需要调整位置时，先在菜单中解锁位置，再拖动窗口。
4. 右键单击灵动岛或托盘图标，可切换主题、锁定位置、管理显示模块、使用计时器或退出程序。
5. 如需配置红、黄、绿三个快捷点，打开托盘菜单的“自定义三点按键”，选择对应颜色和动作类型，再填写快捷键、网址、程序或脚本。仅配置自己信任的目标。
6. 结束使用时，从托盘菜单选择“退出”。程序在可执行文件所在目录保存 `config.yaml`；迁移或重装前可先备份该文件。

天气模块启用并展开时，会访问 `ipapi.co` 查询基于公网 IP 的位置信息，并向 Open-Meteo 请求天气和空气质量数据；这些网络服务会接收请求所需的信息。可在“显示模块”中关闭天气模块。网络或服务不可用时，天气区域可能显示获取失败。

## 从源码运行

需要 Windows、Python 3.10 或以上版本，以及能够安装依赖的网络环境。在项目根目录打开 PowerShell，依次执行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m src.main
```

首次从源码运行时，程序会在项目根目录生成 `config.yaml`。窗口内的 `Win+Shift+I` 和 `Ctrl+Shift+V` 等快捷键可能受焦点或系统快捷键冲突影响。

## 测试

```powershell
.\.venv\Scripts\python -m pytest -q
```

## 打包

```powershell
.\.venv\Scripts\python -m PyInstaller --noconfirm DynamicIsland.spec
```

构建结果位于 `dist\DynamicIsland.exe`。打包可能覆盖同目录下已有的构建结果，请先备份需要保留的文件。

## 配置说明

- 应用首次运行会自动生成 `config.yaml`；源码运行时位于项目根目录，打包运行时位于可执行文件旁
- 主要配置项包括窗口位置、动画参数、插件显示状态和性能阈值

## 平台说明

- 当前主要面向 Windows 环境
- 部分功能依赖系统能力（如 PowerShell、媒体会话、系统热键）

## 许可证

本项目采用 MIT License，详见 [LICENSE](./LICENSE)。
