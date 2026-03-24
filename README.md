# 灵动岛（Dynamic Island for Windows）

一个基于 PySide6 的 Windows 桌面工具，将“灵动岛”交互体验引入桌面端。项目采用插件化架构，支持媒体控制、天气、电池、剪贴板历史、系统监控与生产力快捷工具等功能。

## 功能特性

- 灵动岛主窗口：悬停展开、收起动画、托盘菜单、窗口锁定与主题感知
- 插件化扩展：通过插件管理器动态加载功能模块
- 媒体控制：播放/暂停、上下曲、音量与封面信息展示
- 系统信息：CPU/内存监控、网络状态、电池健康与充电状态提示
- 生产力工具：区域截屏、录屏指示、剪贴板历史快捷唤出
- 快捷交互：支持全局快捷键和三色快捷点自定义动作

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

## 安装与运行

```powershell
cd d:\demo\灵动岛
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
py -3 src\main.py
```

## 测试

```powershell
cd d:\demo\灵动岛
pytest -q
py -3 tests\coverage_runner.py
py -3 tests\benchmark_profile.py
```

## 打包

```powershell
cd d:\demo\灵动岛
py -3 build.py
```

## 配置说明

- 应用首次运行会自动生成 `config.yaml`
- 主要配置项包括窗口位置、动画参数、插件显示状态和性能阈值

## 平台说明

- 当前主要面向 Windows 环境
- 部分功能依赖系统能力（如 PowerShell、媒体会话、系统热键）

## 许可证

本项目采用 MIT License，详见 [LICENSE](./LICENSE)。
