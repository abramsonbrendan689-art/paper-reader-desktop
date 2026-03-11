# Paper Reader Desktop

本项目是一个本地优先的学术文献阅读器，核心目标是提供：

- 左侧原文 PDF、右侧中文译文的并排对照阅读
- 连续滚动阅读与页级同步
- DeepSeek 驱动的翻译、摘要、解释与聊天辅助
- 本地文献库、翻译缓存、阅读位置和笔记持久化

当前技术栈：

- PySide6
- Python 3.12 / 3.13（推荐）
- PyMuPDF
- SQLite
- DeepSeek API（通过 OpenAI SDK 兼容接口接入）

## 当前状态

当前版本已经具备这些基础能力：

- 导入 PDF 并建立本地文献库
- 连续滚动查看原文 PDF
- 右侧显示译文页面流
- DeepSeek 翻译当前页 / 可视区域
- 当前页摘要、全文摘要、聊天和笔记
- 记住阅读位置和本地配置

当前版本仍在重点优化：

- 译文区状态与排版稳定性
- 段落级近似同步
- 选中后阅读工作流闭环

## 推荐 Python 版本

- 推荐：`Python 3.12` 或 `Python 3.13`
- `Python 3.14` 可尝试，但不是首选

## 启动方式

推荐直接使用启动脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

`launch.ps1` 会自动处理：

1. 若 `.venv` 不存在，则创建虚拟环境
2. 若 `.env` 不存在，则从 `.env.example` 生成
3. 自动激活 `.venv`
4. 自动安装或补齐依赖
5. 启动 `python run.py`

如果已经在 VS Code 中固定了解释器为项目虚拟环境，也可以直接运行：

```powershell
python run.py
```

## `.env` 配置说明

程序统一只读取项目根目录下的 `.env`。

首次运行时，如果 `.env` 不存在，会自动从 `.env.example` 创建。

最关键的配置项：

```env
DEFAULT_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_REASONING_MODEL=deepseek-reasoner
```

说明：

- `DEEPSEEK_API_KEY` 可留空，程序仍能启动
- 未配置 API Key 时，阅读器与文献库仍可使用
- 翻译、摘要、聊天等 AI 功能会提示“未配置”，但不会导致主程序崩溃

## 配置持久化

- `.env`：保存 DeepSeek 和运行环境配置
- SQLite：保存应用设置、文献库、翻译缓存、阅读位置、聊天记录、笔记

`.env` 已加入 `.gitignore`，不会提交到版本库。

## VS Code 解释器

项目建议固定到：

```text
.\.venv\Scripts\python.exe
```

项目中已有：

- `.vscode/settings.json`

用于优先选择项目自己的虚拟环境，而不是全局 Python。

## 目录说明

- `app/`：主程序代码
- `data/`：本地数据库
- `logs/`：运行日志
- `artifacts/`：界面截图等调试产物
- `output/`：审计报告等生成物

其中 `data/`、`logs/`、`artifacts/`、`output/` 默认不提交到 Git。

## 下一步开发方向

当前迭代优先级：

1. 译文区状态与排版稳定性
2. 原文和译文的段落级近似同步
3. 选中后解释 / 聊天 / 笔记 / 引用的阅读工作流闭环

不优先做的事情：

- 大量新增功能按钮
- 继续扩大 AI 面板权重
- 只做样式层面的小修补

## 安全说明

请不要把以下内容提交到 Git：

- `.env`
- `.env.local`
- `.venv/`
- 数据库文件
- 日志文件
- 运行时截图和临时产物

提交前请优先确认：

```powershell
git status
git ls-files .env .env.local
```
