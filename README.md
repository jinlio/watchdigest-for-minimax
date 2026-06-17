# watchdigest for MiniMax

OpenClaw skill: 把 B站 / 抖音视频直接喂给 MiniMax-M3 多模态模型，一键生成结构化摘要。

## 功能

- ✅ B站视频下载 + 分析（BV URL、b23.tv 短链）
- ✅ 抖音视频下载 + 分析（分享文本解析、URL 直接下载）
- ✅ 本地视频文件分析（mp4/mov）
- ✅ 视频预处理（统一 H.264/AAC/MP4/720p）
- ✅ Token 估算 + 自动分片（≥50万 token 时按 10 分钟分片）
- ✅ MiniMax-M3 调用（Anthropic 兼容协议）
- ✅ 输出结构化 Markdown 报告

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/jinlio/watchdigest-for-minimax.git
cd watchdigest-for-minimax

# 安装依赖
pip install -e .

# 系统依赖（需要单独安装）
# ffmpeg: winget install Gyan.FFmpeg 或 pip install imageio-ffmpeg
# yt-dlp: 已包含在依赖中
```

### 配置环境变量

```bash
# 必需：MiniMax API Key
export ANTHROPIC_API_KEY="your-api-key-here"

# 可选：自定义 API 地址（默认 https://api.minimaxi.com/anthropic）
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 使用

```bash
# B站视频
watchdigest https://www.bilibili.com/video/BV1xx411c7mD

# B站短链
watchdigest https://b23.tv/xxx

# 抖音分享文本
watchdigest "7.99 复制打开抖音，看看【XXX】https://v.douyin.com/xxx/"

# 抖音 URL
watchdigest https://www.douyin.com/video/xxx

# 本地视频文件
watchdigest ~/Videos/sample.mp4
```

## 输出格式

报告保存到 `~/Documents/watchdigest/<video_id>.md`：

```markdown
# 视频标题

> **来源**: B站 / 抖音
> **时长**: 23:45
> **生成时间**: 2026-06-17 19:30
> **Token 用量**: 12.3 万 / 成本 ¥0.26

## 一句话总览
（≤50 字）

## 分段时间轴
- **00:00-03:20** | 介绍背景：XXX
- ...

## 关键要点（5-10 条）

## 视觉要点（画面里看到、转录看不到的）
- 02:15 屏幕上展示了 XXX 图表
- ...
```

## 技术栈

- **语言**: Python 3.10+
- **核心依赖**:
  - `anthropic` — MiniMax-M3 API 客户端（Anthropic 兼容协议）
  - `yt-dlp` — 视频下载（B站 + 抖音）
  - `ffmpeg` — 视频转码 + 抽帧
- **打包**: `pyproject.toml`（PEP 621）

## 工作流程

```
[URL 或 本地路径]
       │
       ▼
┌──────────────────┐
│ 1. 下载 / 校验     │   yt-dlp (B站/抖音) 或直接用本地文件
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. 转码到统一格式   │   ffmpeg → H.264/AAC/MP4/720p
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. 抽帧 + base64   │   1fps 抽帧 → base64 编码
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Token 估算 + 分片 │   帧数 × ~256 token/帧
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. 调用 MiniMax-M3  │   Anthropic Messages API
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. 合并 + 输出报告   │   Markdown 格式
└──────────────────┘
```

## MiniMax-M3 API 注意事项

1. **必须用 `role: "system"`** — 不要用 `role: "developer"`，否则报 2013 错误
2. **Tool call 顺序**: `tool_use` 后必须紧跟 `tool_result`
3. **中文 JSON 转义**: JSON 序列化时中文引号要转义
4. **Tier 限制**: 免费/低 tier 单次请求 token 上限较低，已内置客户端分片

## 项目结构

```
watchdigest-for-minimax/
├── README.md
├── LICENSE                      # MIT
├── pyproject.toml               # PEP 621
├── .gitignore
├── SKILL.md                     # OpenClaw skill 入口
├── src/
│   └── watchdigest_for_minimax/
│       ├── __init__.py
│       ├── __main__.py          # CLI 入口
│       ├── downloader.py        # B站 + 抖音下载器
│       ├── transcoder.py        # ffmpeg 转码 + 抽帧
│       ├── chunker.py           # token 估算 + 分片
│       ├── minimax_client.py    # M3 调用
│       ├── prompt.py            # prompt 模板
│       ├── reporter.py          # Markdown 报告生成
│       └── config.py            # 环境变量读取
├── examples/
│   └── sample-report.md         # 示例报告
└── .github/
    └── workflows/
        └── lint.yml             # CI: ruff + mypy
```

## 限制（MVP）

- 不支持 YouTube / Vimeo
- 不支持 B站番剧（bangumi）
- 不支持抖音直播
- 不支持实时流媒体
- 最长视频 2 小时
- 高画质（1080p+）B站视频可能需要 SESSDATA cookie

## License

MIT
