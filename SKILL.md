---
name: watchdigest
description: "Summarize B站 and 抖音 videos by feeding them directly to MiniMax-M3 multimodal LLM. Supports Bilibili BV URLs, Douyin share text, and local mp4/mov files. Outputs structured Markdown reports with timestamps, visual cues, and key points."
---

# watchdigest for MiniMax

把 B站 / 抖音视频直接喂给 MiniMax-M3 多模态模型，一键生成结构化摘要。

## 使用方式

```bash
watchdigest <url_or_path>
```

### 支持的输入

| 类型 | 示例 |
|------|------|
| B站 URL | `watchdigest https://www.bilibili.com/video/BV1xx411c7mD` |
| B站短链 | `watchdigest https://b23.tv/xxx` |
| 抖音分享文本 | `watchdigest "7.99 复制打开抖音，看看【XXX】https://v.douyin.com/xxx/"` |
| 抖音 URL | `watchdigest https://www.douyin.com/video/xxx` |
| 本地文件 | `watchdigest ~/Videos/sample.mp4` |

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | MiniMax API Key（兼容 `ANTHROPIC_AUTH_TOKEN`） |
| `ANTHROPIC_BASE_URL` | ❌ | API 地址，默认 `https://api.minimaxi.com/anthropic` |

## 输出

Markdown 报告保存到 `~/Documents/watchdigest/<video_id>.md`，包含：

- 一句话总览
- 分段时间轴
- 关键要点（5-10 条）
- 视觉要点（画面里看到、转录看不到的）

## 依赖

- Python 3.10+
- ffmpeg（系统安装）
- yt-dlp（自动安装）

## 工作流程

1. 下载 / 校验视频（yt-dlp 或本地文件）
2. 转码到 H.264/AAC/MP4/720p
3. 1fps 抽帧 → base64 编码
4. Token 估算 + 自动分片（≥50万 token 时按 10 分钟分片）
5. 调用 MiniMax-M3 分析
6. 合并输出 Markdown 报告
