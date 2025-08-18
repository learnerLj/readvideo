# Bilibili User Content Module Design

## 概述

用户内容模块的目标是为特定B站UP主的所有视频提供批量下载和转录功能，将单个视频处理能力扩展到用户级别的内容获取。

## 核心需求

### 功能需求
1. **用户视频枚举**: 获取指定UP主的所有公开视频列表
2. **批量处理**: 自动下载并转录用户的多个视频
3. **时间过滤**: 支持从指定日期开始处理视频
4. **数量限制**: 支持限制最大处理视频数量
5. **进度跟踪**: 提供详细的批量处理进度信息
6. **错误恢复**: 支持中断后恢复处理
7. **结果汇总**: 生成用户内容分析报告

### 非功能需求
1. **API限制**: 遵守B站API调用频率限制
2. **存储优化**: 合理组织输出文件结构
3. **用户体验**: 清晰的进度提示和错误信息

## 技术架构

### 模块结构 (简化版)
```
src/readvideo/user_content/
├── __init__.py
├── bilibili_user.py      # Bilibili用户视频处理
└── utils.py             # 工具函数
```

### 核心类设计 (简化版)

#### 1. BilibiliUserHandler
**职责**: 用户视频获取和批量处理

```python
class BilibiliUserHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"):
        """初始化用户处理器"""
    
    def extract_uid(self, user_input: str) -> int:
        """从URL或直接UID中提取用户ID
        
        支持格式:
        - 直接UID: 123456
        - 用户主页: https://space.bilibili.com/123456
        """
    
    def get_user_videos(self, uid: int, start_date=None, max_videos=None):
        """获取用户视频列表，支持过滤"""
    
    def process_user(self, user_input: str, 
                    output_dir: str,  # 必需参数，统一输出目录
                    start_date: str = None, 
                    max_videos: int = None):
        """处理用户所有视频的主要方法
        
        Args:
            user_input: 用户UID或主页URL
            output_dir: 输出目录(必需)，用于断点续传和统一管理
            start_date: 开始日期过滤
            max_videos: 最大视频数量
        """
```

## 数据流设计 (简化版)

### 整体流程
```
输入: user_input (UID或用户主页URL)
↓
1. 解析获取UID
↓
2. 获取用户信息和视频列表
↓
3. 应用过滤条件(日期/数量)
↓
4. 为每个视频调用现有处理逻辑
↓
5. 生成处理结果汇总
```

### 详细步骤

#### 阶段1: 视频信息收集
```python
# 1. 解析UID
uid = extract_uid(user_input)  # 支持 UID 或 https://space.bilibili.com/123456

# 2. 获取用户基本信息
user_info = bilibili_api.user.User(uid).get_relation_info()

# 3. 获取所有视频列表 (分页)
all_videos = []
page = 1
while True:
    videos = bilibili_api.user.User(uid).get_videos(pn=page)
    if not videos['list']['vlist']:
        break
    all_videos.extend(videos['list']['vlist'])
    page += 1

# 4. 应用过滤条件
filtered_videos = filter_by_date_and_count(all_videos, start_date, max_videos)
```

#### 阶段2: 复用现有逻辑处理
```python
# 对每个视频调用现有的BilibiliHandler
bilibili_handler = BilibiliHandler(whisper_model_path)

for video in filtered_videos:
    try:
        video_url = f"https://www.bilibili.com/video/{video['bvid']}"
        result = bilibili_handler.process(video_url, output_dir=user_output_dir)
        # 记录处理结果
    except Exception as e:
        # 记录错误，继续处理下一个
        pass
```

## 输出结构设计

### 目录组织
```
{output_dir}/
└── {username}_{uid}/
    ├── video_list.json          # 用户所有视频的基本信息列表
    ├── transcripts/
    │   ├── BV1xxx_video_title.txt
    │   ├── BV1yyy_video_title.txt
    │   └── ...
    ├── processing_status.json    # 处理状态，用于断点续传
    └── user_summary.json        # 用户信息和处理汇总
```

### 核心文件说明

#### video_list.json - 视频信息列表
```json
{
    "user_info": {
        "uid": 123456,
        "name": "用户名",
        "total_videos": 200
    },
    "videos": [
        {
            "bvid": "BV1xxx",
            "title": "视频标题",
            "pubdate": 1640995200,
            "created": "2022-01-01",
            "length": "10:30",
            "play": 50000,
            "video_url": "https://www.bilibili.com/video/BV1xxx",
            "desc": "视频简介"
        }
    ]
}
```

#### processing_status.json - 处理状态
```json
{
    "completed": ["BV1xxx", "BV1yyy"],
    "failed": ["BV1zzz"],
    "skipped": [],
    "last_update": "2024-01-01T12:00:00Z"
}
```

### 报告格式

#### user_summary.json
```json
{
    "user_info": {
        "uid": 123456,
        "username": "用户名",
        "follower_count": 50000,
        "video_count": 200
    },
    "processing_stats": {
        "total_videos": 50,
        "processed_videos": 45,
        "failed_videos": 3,
        "skipped_videos": 2,
        "total_duration": "12h 34m",
        "total_text_length": 150000,
        "start_time": "2024-01-01T10:00:00Z",
        "end_time": "2024-01-01T15:30:00Z"
    },
    "video_results": [
        {
            "bv_id": "BV1xxx",
            "title": "视频标题",
            "duration": 600,
            "publish_date": "2024-01-01",
            "status": "success",
            "output_file": "videos/BV1xxx_视频标题.txt",
            "text_length": 3000,
            "language": "zh"
        }
    ]
}
```

## CLI接口设计 (简化版)

### 命令格式
```bash
readvideo user <user_url_or_uid> [基础选项]
```

### 核心参数 (最小化)
- `user_url_or_uid`: 用户空间URL或UID (必需)
- `--start-date`: 开始日期，格式YYYY-MM-DD (可选)
- `--max-videos`: 最大处理视频数量 (可选)
- `--output-dir`: 输出目录 (可选，默认当前目录)

### 使用示例
```bash
# 处理用户所有视频
readvideo user https://space.bilibili.com/123456

# 只处理2024年以来的视频，最多30个
readvideo user 123456 --start-date 2024-01-01 --max-videos 30
```

## API限制和性能考虑

### 1. Bilibili API限制
- 用户视频列表API: 每页最多30个视频，需要分页获取
- 调用频率限制: 避免过快请求导致IP封禁
- 无需登录凭证: 使用公开API获取用户视频列表

### 2. 性能优化策略
- **顺序处理**: 简单的逐个视频处理，避免复杂的并发控制
- **断点续传**: 检查已存在的文件，跳过已处理的视频
- **错误隔离**: 单个视频失败不影响其他视频处理

### 3. 错误处理
- **网络错误**: 自动重试机制，指数退避
- **文件错误**: 详细错误日志，标记失败视频
- **API错误**: 优雅降级，跳过有问题的视频

## 集成点设计

### 与现有模块的集成
1. **复用BilibiliHandler**: 保持单视频处理逻辑不变
2. **扩展CLI模块**: 添加analyze子命令
3. **共享配置**: 使用相同的whisper模型路径和输出格式

### 向后兼容
- 不影响现有单视频处理功能
- 保持现有CLI参数不变
- 输出格式与单视频保持一致

## 未来扩展

### 1. 高级分析功能
- 内容主题分析
- 视频时长和发布频率统计
- 关键词提取和词云生成

### 2. 其他平台支持
- YouTube频道分析
- 本地视频文件夹批量处理

### 3. 导出格式
- CSV/Excel格式的汇总表
- 支持多种文本格式输出