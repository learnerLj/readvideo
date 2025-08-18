# YouTube频道视频批量处理程序设计方案

## 概述

基于现有readvideo项目的架构，设计YouTube频道视频批量获取和转录程序。完全基于yt-dlp工具，复用现有的语音转录基础设施。参考bilibili_user.py的简洁实现模式。

## 设计目标

1. **复用现有架构** - 直接模仿bilibili_user.py的设计模式
2. **简洁实用** - 避免过度工程化，保持代码简单
3. **仅使用yt-dlp** - 不依赖YouTube API，避免配额限制
4. **一致体验** - CLI接口与bilibili用户处理保持一致

## 核心设计（参考bilibili_user.py）

### 1. YouTubeUserHandler 类结构

```python
class YouTubeUserHandler:
    """Handler for processing all videos from a YouTube channel."""
    
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"):
        self.whisper_model_path = whisper_model_path
        self.youtube_handler = YouTubeHandler(whisper_model_path)
    
    # 核心方法（对应bilibili的extract_uid）
    def extract_channel_info(self, channel_input: str) -> Dict[str, str]
    
    # 对应bilibili的get_user_videos，但用yt-dlp实现
    def get_channel_videos(self, channel_url: str, max_videos: Optional[int] = None) -> List[Dict[str, Any]]
    
    # 对应bilibili的process_user
    def process_channel(self, channel_input: str, output_dir: str,
                       start_date: Optional[str] = None, 
                       max_videos: Optional[int] = None) -> Dict[str, Any]
    
    # 复用bilibili的辅助方法
    def create_channel_directory(self, output_dir: str, channel_info: Dict[str, str]) -> str
    def save_video_list(self, channel_dir: str, channel_info: Dict, videos: List[Dict])
    def load_processing_status(self, channel_dir: str) -> Dict[str, List[str]]
    def save_processing_status(self, channel_dir: str, status: Dict[str, List[str]])
    def generate_summary(self, channel_info: Dict, videos: List, results: List, channel_dir: str) -> Dict
```

### 2. 核心实现对比

| 功能 | bilibili_user.py | youtube_user.py |
|-----|-----------------|-----------------|
| 用户/频道识别 | `extract_uid()` 解析UID | `extract_channel_info()` 解析频道URL |
| 视频获取 | `get_user_videos()` 用bilibili-api | `get_channel_videos()` 用yt-dlp |
| 目录创建 | `create_user_directory()` | `create_channel_directory()` |
| 状态管理 | `load/save_processing_status()` | 直接复用相同逻辑 |
| 主流程 | `process_user()` | `process_channel()` |

### 3. yt-dlp集成要点

#### 获取频道视频列表
```bash
yt-dlp --flat-playlist --quiet \
       --print '%(id)s|%(title)s|%(upload_date)s' \
       "https://www.youtube.com/@username/videos"
```

#### 支持的频道格式
- `@username` → `https://www.youtube.com/@username/videos`
- `https://www.youtube.com/@username` → 添加 `/videos`
- `https://www.youtube.com/channel/UCxxx` → 添加 `/videos`

### 4. 简化的数据结构

#### 频道信息（对应bilibili的user_info）
```python
{
    "identifier": "@username",  # 对应bilibili的name
    "url": "https://www.youtube.com/@username",
    "total_videos": 150  # 对应bilibili user_info
}
```

#### 视频信息（对应bilibili的video列表）
```python
{
    "video_id": "abc123xyz",  # 对应bilibili的bvid
    "title": "Video Title",
    "upload_date": "20240101",
    "formatted_date": "2024-01-01",  # 对应bilibili的created_date
    "video_url": "https://www.youtube.com/watch?v=abc123xyz"  # 对应bilibili的video_url
}
```

### 5. CLI接口（复用现有模式）

参考现有的 `readvideo user` 命令，新增：

```bash
readvideo youtube-channel @username -o ./output --start-date 2024-01-01 --max-videos 50
```

参数与bilibili user命令保持一致：
- `--output-dir, -o` (必需)
- `--start-date` 
- `--max-videos`
- `--whisper-model`
- `--verbose, -v`

## 实现要点

### 1. 关键差异点
- **异步处理**: bilibili用异步API，YouTube用同步yt-dlp命令
- **数据获取**: bilibili用API分页，YouTube用yt-dlp一次获取全部
- **依赖检查**: 需要检查yt-dlp可用性（类似bilibili检查bilibili-api）

### 2. 直接复用的部分
- 目录结构创建逻辑
- JSON状态文件管理
- 进度显示和用户交互
- 错误处理和重试机制
- CLI参数验证

### 3. 简化的实现流程

```python
def process_channel(self, channel_input: str, output_dir: str, **options):
    # 1. 解析频道信息 (对应extract_uid)
    channel_info = self.extract_channel_info(channel_input)
    
    # 2. 创建目录 (直接复用)
    channel_dir = self.create_channel_directory(output_dir, channel_info)
    
    # 3. 获取视频列表 (用yt-dlp替代API)
    videos = self.get_channel_videos(channel_info['url'], max_videos)
    
    # 4. 状态管理 (直接复用)
    status = self.load_processing_status(channel_dir)
    
    # 5. 循环处理 (逻辑相同，调用youtube_handler)
    for video in videos:
        if video_id not in status['completed']:
            result = self.youtube_handler.process(video['video_url'], ...)
            # 更新状态...
    
    # 6. 生成总结 (直接复用)
    return self.generate_summary(...)
```

## 问题澄清

1. **CLI命令名称**: 使用 `readvideo youtube-channel` 还是复用 `readvideo user` 并自动识别平台？

2. **文件命名**: 频道目录是否用 `youtube_channel_@username` 格式，还是更简洁的格式？

3. **并发处理**: 是否需要考虑并发处理多个视频，还是保持简单的顺序处理？

4. **依赖检查**: 如何优雅地检查和提示yt-dlp依赖？

## 简化总结

这个设计的核心思路是**最大化复用bilibili_user.py的代码结构**，只替换数据获取部分（用yt-dlp替代bilibili-api），其他逻辑保持基本一致。这样可以快速实现功能，同时保持代码的一致性和可维护性。