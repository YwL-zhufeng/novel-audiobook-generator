# 豆包声音克隆功能实现报告

## 实现状态: ✅ 已完成

### 功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 标准TTS | ✅ | 100+ 官方音色 |
| 声音克隆 - ICL 1.0 | ✅ | model_type=1 |
| 声音克隆 - ICL 2.0 | ✅ | model_type=4 (推荐) |
| 声音克隆 - DiT标准版 | ✅ | model_type=2 |
| 声音克隆 - DiT还原版 | ✅ | model_type=3 |
| 训练状态查询 | ✅ | 实时跟踪训练进度 |
| 音色激活 | ✅ | 锁定音色用于生产 |
| 自动集群选择 | ✅ | 标准/克隆音色自动切换 |

### API端点

```python
# 标准TTS
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"

# 声音克隆
VOICE_CLONE_UPLOAD_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/audio/upload"
VOICE_CLONE_STATUS_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/status"
VOICE_CLONE_ACTIVATE_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/audio/activate"
```

### 使用示例

```python
from src.tts_backends.doubao import DoubaoBackend, ModelType

# 初始化
backend = DoubaoBackend(
    app_id="your-app-id",
    access_token="your-access-token"
)

# 1. 克隆声音 (5秒样本)
cloned = backend.clone_voice(
    sample_audio_path="sample.mp3",
    speaker_id="S_my_voice",
    model_type=ModelType.ICL_2_0,  # 推荐
    wait_for_completion=True
)

# 2. 查询训练状态
voice = backend.get_voice_status("S_my_voice")
print(f"状态: {voice.status_text}")  # 训练中/训练完成/训练失败

# 3. 使用克隆的声音生成语音
backend.generate_speech(
    text="你好，这是克隆的声音",
    voice_id="S_my_voice",  # 自动识别为克隆音色
    output_path="output.mp3"
)

# 4. 激活音色 (生产环境建议)
backend.activate_voice("S_my_voice")
```

### 模型类型说明

| ModelType | 值 | 特点 |
|-----------|-----|------|
| ICL_1_0 | 1 | 声音复刻1.0 |
| DIT_STANDARD | 2 | DiT标准版，还原音色 |
| DIT_RESTORATION | 3 | DiT还原版，还原音色+风格 |
| ICL_2_0 | 4 | 声音复刻2.0，推荐 |

### 集群自动切换

- **标准音色**: `volcano_tts`
- **克隆音色**: `volcano_icl`

系统自动识别voice_id是否以"S_"开头或是否在克隆列表中，自动选择正确的集群。

### 限制说明

1. **训练次数**: 每个音色最多10次训练
2. **音频长度**: 建议5-20秒
3. **文件大小**: 最大10MB
4. **音频格式**: wav, mp3, m4a, ogg, pcm

### 文件变更

- `src/tts_backends/doubao.py` - 完整的声音克隆实现

### 新增类

- `ModelType` - 克隆模型类型枚举
- `ClonedVoice` - 克隆音色数据类

### 新增方法

- `clone_voice()` - 克隆声音
- `get_voice_status()` - 查询训练状态
- `activate_voice()` - 激活音色
- `list_cloned_voices()` - 列出克隆音色

## 验证结果

代码结构检查通过：
- ✅ ModelType 枚举定义
- ✅ ClonedVoice 数据类
- ✅ 克隆API端点配置
- ✅ clone_voice 方法
- ✅ 状态查询方法
- ✅ 激活方法

## 文档

- API文档: https://www.volcengine.com/docs/6561/1305191
- 音色列表: https://www.volcengine.com/docs/6561/1257544
