# Dynamic-Island-Latest

一个基于 PySide6 的 Windows 桌面灵动岛项目，支持插件化模块（天气、音乐、系统状态、剪贴板、音乐控制等），并提供一键打包能力。

## 功能特性

- 悬浮灵动岛窗口，支持展开/收起动画与拖拽定位
- 插件化架构，模块可独立启用/隐藏
- 音乐控制与媒体信息显示（支持系统媒体会话）
- 快捷圆点自定义（快捷键/网址/脚本/程序）
- 托盘菜单与主题切换

## 环境要求

- Windows 10/11
- Python 3.11+

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python src\main.py
```

## 打包发布

```bash
.venv\Scripts\python build.py
```

打包产物默认在 `dist/` 目录下。

## 项目结构

- `src/` 主程序源码
- `plugins/` 插件实现与媒体信息脚本
- `tests/` 测试用例
- `assets/` 静态资源
- `docs/` 需求、架构与性能文档

## 安装与使用

1. 运行程序后，灵动岛会固定在桌面顶部。
2. 鼠标移入可展开模块，移出自动收起。
3. 托盘菜单可切换主题、锁定窗口、管理模块显示。
4. 音乐播放时会尝试读取系统媒体会话并展示歌曲信息。

## 版本与发布

- 采用语义化版本（SemVer）
- 更新历史见 `CHANGELOG.md`
- 建议通过 GitHub Releases 分发可执行文件

## 截图与演示

- 可在仓库 `assets/` 或 Releases 中查看最新演示素材
- 建议添加 `assets/screenshot-main.png` 作为首页展示图

## 许可证

本项目采用 MIT License，详见 `LICENSE`。
