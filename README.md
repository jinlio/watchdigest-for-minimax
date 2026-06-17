# watchdigest for MiniMax

OpenClaw skill: 把 B站 / 抖音视频直接喂给 MiniMax-M3 多模态模型，利用模型原生视频识别能力，一键生成结构化摘要。

## 功能

- ✅ B站视频下载 + 分析（BV URL、b23.tv 短链）
- ✅ 抖音视频下载 + 分析（分享文本解析、URL 直接下载）
- ✅ 本地视频文件分析（mp4/mov）
- ✅ 视频压缩 + 自动切分（480p/700k，每段 45s）
- ✅ MiniMax-M3 原生 video_url 模式（保留时序 + 音频 + 字幕 OCR）
- ✅ Map-reduce 分段总结 + 合并
- ✅ 输出结构化 Markdown 报告

## 快速开始

### 安装

```bash
git clone https://github.com/jinlio/watchdigest-for-minimax.git
cd watchdigest-for-minimax
pip install -e .

# 系统依赖
# ffmpeg: winget install Gyan.FFmpeg 或 pip install imageio-ffmpeg
# yt-dlp: 已包含在依赖中
```

### 配置环境变量

```bash
# 必需
export ANTHROPIC_API_KEY="your-api-key-here"

# video_url 模式需要公网 HTTP server
export WATCHDIGEST_PUBLIC_HOST="your-ecs-public-ip"
export WATCHDIGEST_HTTP_PORT="41234"

# 可选
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
export WATCHDIGEST_CHUNK_SECONDS="45"       # 每段时长（秒）
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

# CLI 选项
watchdigest --max-duration 3600 --output ./reports --verbose https://...
```

## 工作原理

```
[URL 或 本地路径]
       │
       ▼
┌──────────────────┐
│ 1. 下载视频        │   yt-dlp（B站/抖音）或本地文件
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. 压缩 + 切分     │   ffmpeg → 480p/700k + 按 45s 切段
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. 起 HTTP Server  │   Range-capable，minimax 服务端拉取
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Map: 分段分析   │   每段一次 video_url 调用
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Reduce: 合并    │   N 段总结 → 1 篇连贯报告
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. 输出 Markdown   │   ~/Documents/watchdigest/
└──────────────────┘
```

## 技术栈

- **语言**: Python 3.10+
- **核心依赖**:
  - `yt-dlp` — 视频下载（B站 + 抖音，内置反爬）
  - `ffmpeg` — 视频压缩 + 切分
  - `tenacity` — API 调用重试
  - `tqdm` — 进度条
- **API**: MiniMax-M3 原生 ChatCompletion（video_url 块）
- **打包**: `pyproject.toml`（PEP 621）

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
│       ├── downloader.py        # B站 + 抖音下载器（反爬）
│       ├── video_splitter.py    # 视频压缩 + 切分
│       ├── http_server.py       # Range-capable HTTP server
│       ├── analyzer.py          # map-reduce 视频分析
│       ├── prompt.py            # chunk + merge prompt 模板
│       ├── reporter.py          # Markdown 报告生成
│       ├── transcoder.py        # 视频信息提取
│       └── config.py            # 环境变量读取
├── tests/                       # 单元测试
├── examples/
│   └── sample-report.md         # 示例报告
└── .github/
    └── workflows/
        └── lint.yml             # CI: ruff + mypy + pytest
```

## 限制

- 不支持 YouTube / Vimeo
- 不支持 B站番剧（bangumi）
- 不支持抖音直播
- 不支持实时流媒体
- 最长视频 2 小时
- 需要公网 HTTP server（minimax 服务端拉取视频）
- 每段视频 ≤ 5MB（30s 传输窗口）

## License

MIT
