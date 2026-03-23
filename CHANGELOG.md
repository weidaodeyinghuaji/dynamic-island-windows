# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-03-23

### Added
- 完成灵动岛项目基础架构与插件化加载机制
- 增加天气、音乐、剪贴板、系统监控、连接状态等插件
- 增加快捷圆点自定义能力（快捷键/网址/脚本/程序）
- 增加托盘菜单、主题切换与窗口锁定能力
- 增加打包脚本 `build.py` 与 PyInstaller 配置

### Changed
- 调整灵动岛展开长度策略，窗口更紧凑
- 优化展开/收起动画，减少抖动
- 优化音乐信息读取兼容性与显示逻辑

### Fixed
- 修复部分环境下媒体信息脚本的兼容问题
- 修复播放状态下中间区域歌名显示逻辑问题
