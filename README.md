# Dynamic Island (Windows)

一个基于 PySide6 的 Windows 桌面灵动岛项目，支持插件化模块（天气、音乐、系统状态、剪贴板等）。

## 运行

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python src\main.py
```

## 打包

```bash
.venv\Scripts\python build.py
```

## 目录

- `src/` 主程序源码
- `plugins/` 插件实现与媒体信息脚本
- `tests/` 测试用例
- `assets/` 静态资源
- `docs/` 文档
