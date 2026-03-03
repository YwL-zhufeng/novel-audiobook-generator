"""
Doubao (ByteDance) TTS backend with full voice cloning support.
Based on Volcano Engine API documentation.

API Documentation:
- TTS API: https://www.volcengine.com/docs/6561/1257584
- Voice Cloning API: https://www.volcengine.com/docs/6561/1305191
- Voice List: https://www.volcengine.com/docs/6561/1257544
"""

import time
import json
import base64
import uuid
from typing import Optional, Dict, Any, List
from pathlib import Path
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from ..exceptions import TTSError, APIError, RateLimitError, ValidationError
from ..logging_config import get_logger

logger = get_logger(__name__)

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests package not available")


class ModelType(Enum):
    """Voice cloning model types."""
    ICL_1_0 = 1  # 声音复刻ICL1.0
    DIT_STANDARD = 2  # DiT标准版（音色，不还原风格）
    DIT_RESTORATION = 3  # DiT还原版（音色+风格）
    ICL_2_0 = 4  # 声音复刻ICL2.0（推荐）


@dataclass
class ClonedVoice:
    """Represents a cloned voice."""
    speaker_id: str
    status: int  # 0:未找到 1:训练中 2:训练完成 3:训练失败 4:已激活
    version: int  # 训练次数
    model_type: int
    create_time: Optional[str] = None
    
    @property
    def is_ready(self) -> bool:
        """Check if voice is ready for use."""
        return self.status == 2  # 训练完成
    
    @property
    def status_text(self) -> str:
        """Get human-readable status."""
        status_map = {
            0: "未找到",
            1: "训练中",
            2: "训练完成",
            3: "训练失败",
            4: "已激活"
        }
        return status_map.get(self.status, f"未知({self.status})")


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry on rate limit errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'rate limit' in error_str or '429' in error_str or 'too many requests' in error_str:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"Rate limited, retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DoubaoBackend:
    """
    Doubao TTS backend with full voice cloning support.
    
    Features:
    - Standard TTS with 100+ voices
    - Voice cloning (5-second samples)
    - Multiple cloning models (ICL 1.0/2.0, DiT)
    - Cloned voice management
    """
    
    # API endpoints
    TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"
    VOICE_CLONE_UPLOAD_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/audio/upload"
    VOICE_CLONE_STATUS_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/status"
    VOICE_CLONE_ACTIVATE_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/audio/activate"
    
    # Clusters
    CLUSTER_STANDARD = "volcano_tts"
    CLUSTER_ICL = "volcano_icl"  # For cloned voices
    CLUSTER_ICL_CONCURR = "volcano_icl_concurr"  # For concurrent billing
    
    # Default voice IDs (updated based on official voice list)
    DEFAULT_VOICES = {
        # 通用场景
        "zh_female_wanwanxiaohe_moon_bigtts": "湾湾小何 (台湾口音)",
        "zh_female_shuangkuaisisi_moon_bigtts": "爽快思思",
        "zh_male_wennuanahu_moon_bigtts": "温暖阿虎",
        "zh_male_jingqiangkanye_moon_bigtts": "京腔侃爷 (北京口音)",
        "zh_female_wanqudashu_moon_bigtts": "湾区大叔 (粤语)",
        "zh_female_daimengchuanmei_moon_bigtts": "呆萌川妹 (四川口音)",
        "zh_male_shaonianzixin_moon_bigtts": "少年梓辛",
        "zh_male_guozhoudege_moon_bigtts": "广州德哥 (粤语)",
        "zh_male_yuanboxiaoshu_moon_bigtts": "渊博小叔",
        "zh_male_beijingxiaoye_moon_bigtts": "北京小爷 (北京口音)",
        "zh_male_yangguangqingnian_moon_bigtts": "阳光青年",
        "zh_male_wenrouxiaoge_mars_bigtts": "温柔小哥",
        "zh_female_tianmeitaozi_mars_bigtts": "甜美桃子",
        "zh_female_kefunvsheng_mars_bigtts": "暖阳女声 (客服场景)",
        "zh_female_qinqienvsheng_moon_bigtts": "亲切女声",
        "zh_female_tianmeixiaoyuan_moon_bigtts": "甜美小源",
        "zh_female_qingchezizi_moon_bigtts": "清澈梓梓",
        "zh_male_dongfanghaoran_moon_bigtts": "东方浩然",
        "zh_male_jieshuoxiaoming_moon_bigtts": "解说小明",
        "zh_female_kailangjiejie_moon_bigtts": "开朗姐姐",
        "zh_male_linjiananhai_moon_bigtts": "邻家男孩",
        "zh_female_tianmeiyueyue_moon_bigtts": "甜美悦悦",
        "zh_female_xinlingjitang_moon_bigtts": "心灵鸡汤",
        "zh_female_linjiavhai_moon_bigtts": "邻家女孩",
        "zh_female_gaolengyujie_moon_bigtts": "高冷御姐",
        "zh_female_wenrouxiaoya_moon_bigtts": "温柔小雅",
        
        # 角色扮演
        "zh_male_aojiaobazong_moon_bigtts": "傲娇霸总",
        "zh_female_meilinvyou_moon_bigtts": "魅力女友",
        "zh_male_shenyeboke_moon_bigtts": "深夜播客",
        "zh_female_sajiaonvyou_moon_bigtts": "柔美女友",
        "zh_female_yuanqinvyou_moon_bigtts": "撒娇学妹",
        "zh_female_bingruoshaonv_tob": "病弱少女",
        "zh_female_huoponvhai_tob": "活泼女孩",
        "zh_female_heainainai_tob": "和蔼奶奶",
        "zh_female_linjuayi_tob": "邻居阿姨",
        
        # 多情感 (支持情感控制)
        "zh_female_gaolengyujie_emo_v2_mars_bigtts": "高冷御姐 (多情感)",
        "zh_male_aojiaobazong_emo_v2_mars_bigtts": "傲娇霸总 (多情感)",
        "zh_male_guangzhoudege_emo_mars_bigtts": "广州德哥 (多情感)",
        "zh_male_jingqiangkanye_emo_mars_bigtts": "京腔侃爷 (多情感)",
        "zh_female_linjuayi_emo_v2_mars_bigtts": "邻居阿姨 (多情感)",
        "zh_male_yourougongzi_emo_v2_mars_bigtts": "优柔公子 (多情感)",
        "zh_female_tianxinxiaomei_emo_v2_mars_bigtts": "甜心小美 (多情感)",
        "zh_female_roumeinvyou_emo_v2_mars_bigtts": "柔美女友 (多情感)",
        "zh_male_yangguangqingnian_emo_v2_mars_bigtts": "阳光青年 (多情感)",
        "zh_female_meilinvyou_emo_v2_mars_bigtts": "魅力女友 (多情感)",
        "zh_female_shuangkuaisisi_emo_v2_mars_bigtts": "爽快思思 (多情感)",
        "zh_male_ruyayichen_emo_v2_mars_bigtts": "儒雅男友 (多情感)",
        "zh_male_junlangnanyou_emo_v2_mars_bigtts": "俊朗男友 (多情感)",
        "zh_male_beijingxiaoye_emo_v2_mars_bigtts": "北京小爷 (多情感)",
        "zh_male_lengkugege_emo_v2_mars_bigtts": "冷酷哥哥 (多情感)",
        "zh_male_shenyeboke_emo_v2_mars_bigtts": "深夜播客 (多情感)",
        
        # 英语音色
        "en_female_amanda_mars_bigtts": "Amanda (美式英语)",
        "en_male_jackson_mars_bigtts": "Jackson (美式英语)",
        "en_female_emily_mars_bigtts": "Emily (英式英语)",
        "en_female_sarah_new_conversation_wvae_bigtts": "Luna (美式英语)",
        "en_male_charlie_conversation_wvae_bigtts": "Owen (美式英语)",
        "en_male_jason_conversation_wvae_bigtts": "开朗学长 (中英双语)",
        "en_female_dacey_conversation_wvae_bigtts": "Daisy (英式英语)",
    }
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_key: Optional[str] = None,
        cluster: str = "volcano_tts",
        resource_id: str = "volc.megatts.voiceclone"
    ):
        """
        Initialize Doubao backend.
        
        Args:
            app_id: Volcano Engine App ID (from console)
            access_token: Volcano Engine Access Token (from console)
            api_key: Alternative API key (same as access_token)
            cluster: Cluster name for standard TTS
            resource_id: Resource ID for voice cloning
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests package required. "
                "Install with: pip install requests"
            )
        
        self.app_id = app_id
        self.access_token = access_token or api_key
        self.cluster = cluster
        self.resource_id = resource_id
        
        if not self.access_token:
            raise TTSError(
                "Either access_token or api_key is required for Doubao",
                backend="doubao"
            )
        
        # Track cloned voices
        self.cloned_voices: Dict[str, ClonedVoice] = {}
        
        # Setup session with connection pooling
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        logger.info("Initialized Doubao backend with voice cloning support")
    
    def _get_headers(self, resource_id: Optional[str] = None) -> Dict[str, str]:
        """Get API request headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self.access_token}",
        }
        if resource_id:
            headers["Resource-Id"] = resource_id
        return headers
    
    def _build_tts_payload(
        self,
        text: str,
        voice_type: str,
        cluster: str,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        sample_rate: int = 24000,
        encoding: str = "mp3",
        **kwargs
    ) -> Dict[str, Any]:
        """Build TTS API request payload."""
        reqid = str(uuid.uuid4())
        
        payload = {
            "app": {
                "appid": self.app_id or "",
                "token": self.access_token,
                "cluster": cluster,
            },
            "user": {
                "uid": kwargs.get("uid", "uid123")
            },
            "audio": {
                "voice_type": voice_type,
                "encoding": encoding.lower(),
                "speed_ratio": speed_ratio,
                "volume_ratio": volume_ratio,
                "sample_rate": sample_rate,
            },
            "request": {
                "reqid": reqid,
                "text": text,
                "operation": "query",
            }
        }
        
        # Optional parameters
        if "text_type" in kwargs:
            payload["request"]["text_type"] = kwargs["text_type"]
        if "model" in kwargs:
            payload["request"]["model"] = kwargs["model"]
        if "silence_duration" in kwargs:
            payload["request"]["silence_duration"] = kwargs["silence_duration"]
            payload["request"]["enable_trailing_silence_audio"] = True
        if "with_timestamp" in kwargs:
            payload["request"]["with_timestamp"] = kwargs["with_timestamp"]
        if "context_language" in kwargs:
            payload["context_language"] = kwargs["context_language"]
        
        return payload
    
    @retry_on_rate_limit(max_retries=3)
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        speed: float = 1.0,
        volume: float = 1.0,
        sample_rate: int = 24000,
        encoding: str = "mp3",
        **kwargs
    ):
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize (max 1024 bytes UTF-8)
            voice_id: Voice type ID or cloned speaker ID
            output_path: Output audio file path
            speed: Speech speed ratio (0.5-2.0)
            volume: Volume ratio (0.5-2.0)
            sample_rate: Audio sample rate
            encoding: Audio encoding ("mp3", "wav", "pcm")
        """
        # Determine cluster based on voice type
        cluster = self.CLUSTER_ICL if self._is_cloned_voice(voice_id) else self.cluster
        
        # Validate and truncate text
        text_bytes = text.encode('utf-8')
        if len(text_bytes) > 1024:
            logger.warning(f"Text too long ({len(text_bytes)} bytes), truncating")
            text = text_bytes[:1024].decode('utf-8', errors='ignore')
        
        payload = self._build_tts_payload(
            text=text,
            voice_type=voice_id,
            cluster=cluster,
            speed_ratio=speed,
            volume_ratio=volume,
            sample_rate=sample_rate,
            encoding=encoding,
            **kwargs
        )
        
        try:
            response = self.session.post(
                self.TTS_API_URL,
                headers=self._get_headers(),
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("code") != 3000:
                error_msg = result.get("message", "Unknown error")
                raise TTSError(
                    f"TTS API error: {error_msg} (code: {result.get('code')})",
                    backend="doubao"
                )
            
            audio_base64 = result.get("data", {}).get("audio")
            if not audio_base64:
                raise TTSError("No audio data in response", backend="doubao")
            
            audio_data = base64.b64decode(audio_base64)
            
            output_path = Path(output_path)
            if encoding.lower() == "mp3":
                output_path = output_path.with_suffix(".mp3")
            elif encoding.lower() == "wav":
                output_path = output_path.with_suffix(".wav")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(audio_data)
            
            logger.debug(f"Generated speech saved to {output_path}")
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Doubao rate limit exceeded")
            raise TTSError(f"TTS HTTP error: {e}", backend="doubao")
        except Exception as e:
            if isinstance(e, TTSError):
                raise
            raise TTSError(f"TTS generation failed: {e}", backend="doubao")
    
    def clone_voice(
        self,
        sample_audio_path: str,
        speaker_id: str,
        model_type: ModelType = ModelType.ICL_2_0,
        language: int = 0,
        wait_for_completion: bool = True,
        timeout: int = 60
    ) -> ClonedVoice:
        """
        Clone a voice from audio sample.
        
        Args:
            sample_audio_path: Path to voice sample (5-20 seconds recommended)
            speaker_id: Unique speaker ID for the cloned voice
            model_type: Cloning model type (default: ICL_2_0)
            language: Language code (0: Chinese, 1: English, etc.)
            wait_for_completion: Whether to wait for training to complete
            timeout: Maximum wait time in seconds
            
        Returns:
            ClonedVoice object with status information
        """
        audio_path = Path(sample_audio_path)
        if not audio_path.exists():
            raise ValidationError(f"Audio file not found: {sample_audio_path}")
        
        # Validate file size (max 10MB)
        file_size = audio_path.stat().st_size
        if file_size > 10 * 1024 * 1024:
            raise ValidationError(f"Audio file too large ({file_size / 1024 / 1024:.1f}MB)")
        
        # Read and encode audio
        with open(audio_path, "rb") as f:
            audio_data = f.read()
            audio_bytes = base64.b64encode(audio_data).decode("utf-8")
        
        audio_format = audio_path.suffix.lower().replace(".", "")
        if audio_format not in ["wav", "mp3", "m4a", "ogg", "pcm"]:
            audio_format = "wav"
        
        # Build upload payload
        payload = {
            "appid": self.app_id or "",
            "speaker_id": speaker_id,
            "audios": [{
                "audio_bytes": audio_bytes,
                "audio_format": audio_format
            }],
            "source": 2,  # API upload
            "language": language,
            "model_type": model_type.value,
        }
        
        try:
            response = self.session.post(
                self.VOICE_CLONE_UPLOAD_URL,
                headers=self._get_headers(self.resource_id),
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Voice cloning started: {speaker_id} (model: {model_type.name})")
            
            # Create ClonedVoice object
            cloned_voice = ClonedVoice(
                speaker_id=speaker_id,
                status=1,  # 训练中
                version=1,
                model_type=model_type.value
            )
            self.cloned_voices[speaker_id] = cloned_voice
            
            if wait_for_completion:
                cloned_voice = self._wait_for_training(speaker_id, timeout)
            
            return cloned_voice
            
        except requests.exceptions.HTTPError as e:
            raise TTSError(f"Voice cloning failed: {e}", backend="doubao")
        except Exception as e:
            raise TTSError(f"Voice cloning failed: {e}", backend="doubao")
    
    def _wait_for_training(
        self,
        speaker_id: str,
        timeout: int = 60,
        poll_interval: float = 2.0
    ) -> ClonedVoice:
        """Wait for voice training to complete."""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            voice = self.get_voice_status(speaker_id)
            
            if voice.status == 2:  # 训练完成
                logger.info(f"Voice training completed: {speaker_id}")
                return voice
            elif voice.status == 3:  # 训练失败
                raise TTSError(f"Voice training failed: {speaker_id}", backend="doubao")
            
            time.sleep(poll_interval)
        
        raise TTSError(f"Voice training timeout: {speaker_id}", backend="doubao")
    
    def get_voice_status(self, speaker_id: str) -> ClonedVoice:
        """Get cloned voice training status."""
        payload = {
            "appid": self.app_id or "",
            "speaker_id": speaker_id,
        }
        
        try:
            response = self.session.post(
                self.VOICE_CLONE_STATUS_URL,
                headers=self._get_headers(self.resource_id),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            voice = ClonedVoice(
                speaker_id=speaker_id,
                status=result.get("status", 0),
                version=result.get("version", 0),
                model_type=result.get("model_type", 1),
                create_time=result.get("create_time")
            )
            
            self.cloned_voices[speaker_id] = voice
            return voice
            
        except Exception as e:
            raise TTSError(f"Failed to get voice status: {e}", backend="doubao")
    
    def activate_voice(self, speaker_id: str) -> bool:
        """
        Activate a cloned voice (locks it, prevents further training).
        
        Args:
            speaker_id: Speaker ID to activate
            
        Returns:
            True if activation successful
        """
        payload = {
            "appid": self.app_id or "",
            "speaker_id": speaker_id,
        }
        
        try:
            response = self.session.post(
                self.VOICE_CLONE_ACTIVATE_URL,
                headers=self._get_headers(self.resource_id),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Voice activated: {speaker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to activate voice: {e}")
            return False
    
    def list_cloned_voices(self) -> List[ClonedVoice]:
        """List all cloned voices."""
        return list(self.cloned_voices.values())
    
    def _is_cloned_voice(self, voice_id: str) -> bool:
        """Check if voice_id is a cloned voice."""
        # Cloned voices typically start with "S_" or are in our tracked list
        return voice_id.startswith("S_") or voice_id in self.cloned_voices
    
    def list_default_voices(self) -> Dict[str, str]:
        """Return list of available default voices."""
        return self.DEFAULT_VOICES.copy()
    
    def get_voice_id(self, voice_name: str) -> str:
        """Get voice ID by name."""
        if voice_name in self.cloned_voices:
            return self.cloned_voices[voice_name].speaker_id
        if voice_name in self.DEFAULT_VOICES:
            return voice_name
        return voice_name
    
    def get_recommended_voices(self, scenario: str = "general") -> Dict[str, str]:
        """Get recommended voices for specific scenarios."""
        if scenario == "audiobook":
            return {k: v for k, v in self.DEFAULT_VOICES.items()
                    if any(x in k for x in ["wenrou", "shenyeboke", "neiliancaijun", "yangyang"])}
        elif scenario == "roleplay":
            return {k: v for k, v in self.DEFAULT_VOICES.items()
                    if "ICL" in k or any(x in k for x in ["aojiaobazong", "meilinvyou", "sajiaonvyou"])}
        elif scenario == "emotional":
            return {k: v for k, v in self.DEFAULT_VOICES.items() if "emo" in k}
        else:
            return self.DEFAULT_VOICES
