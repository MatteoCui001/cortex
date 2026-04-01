# Cortex

> AI 原生的知识引擎，服务于高信息密度的人类与 Agent。

[English README](README.md)

`Cortex` 是一个个人知识基础设施项目。
它把 Obsidian 笔记、网页、PDF、微信消息、会议纪要等异构信息源统一到一个知识图谱里，并提供语义搜索、实体抽取、thesis 跟踪、信号检测和主动通知。

它不是一个“多存一点信息”的笔记工具，更接近一个持续运转的认知后端：

- ingest 分散在不同渠道的信息
- 统一抽取实体、主题和 thesis
- 支持中英混合的搜索与关联
- 跟踪某个判断背后的证据变化
- 在出现矛盾、桥接、重要更新时主动提醒

## 这个仓库是什么

这是主仓库，包含：

- Python 后端 API / CLI
- PostgreSQL + pgvector 存储适配层
- 本地 embedding 和 LLM 接入
- React 控制台

如果你要接微信入口，请同时看兄弟仓库 [cortex-wechat](https://github.com/MatteoCui001/cortex-wechat)。

## 适合谁

- VC / 买方研究员
- 高强度研究工作者
- 创业者 / 产品负责人
- 需要长期追踪 thesis、证据和判断变化的人

## 核心能力

- 多源导入：Obsidian、网页、PDF/DOCX/TXT、微信消息、手动文本
- 混合搜索：语义检索 + 中文全文检索
- 实体抽取：公司、人物、技术、概念等
- 知识图谱：事件、实体、关系、thesis
- Thesis 跟踪：证据积累、置信度变化、覆盖情况
- Signal detection：矛盾、bridge、answer、entity momentum
- 主动通知：stale thesis、重要信号、digest
- Web console：事件流、Inbox、Signals、Graph、Search

## 仓库导航

- 想先看产品定位：`README.md`
- 想看微信接入：`cortex-wechat`
- 想快速体验：先启动主仓库，再接入微信仓库

完整 sibling-repo 形态：

```text
~/Projects/
├── cortex/
└── cortex-wechat/
```

## 快速开始

### 方式 A：本地安装（macOS）

```bash
git clone https://github.com/MatteoCui001/cortex.git
cd cortex
./install.sh
source ~/.cortex/env && uv run cortex serve
```

打开：

- Console: `http://localhost:8420/console/`
- Docs: `http://localhost:8420/docs`

### 方式 B：Docker

```bash
git clone https://github.com/MatteoCui001/cortex.git ~/Projects/cortex
git clone https://github.com/MatteoCui001/cortex-wechat.git ~/Projects/cortex-wechat
cd ~/Projects/cortex
docker compose up -d db cortex
```

## 开源说明

- License: MIT
- 当前版本：`v1.0.0`
- 项目目前优先服务个人使用和本地部署场景

## 相关仓库

- 主后端与控制台：[`cortex`](https://github.com/MatteoCui001/cortex)
- 微信 / Agent 接入：[`cortex-wechat`](https://github.com/MatteoCui001/cortex-wechat)
