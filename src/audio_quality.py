"""
Audio quality detection and validation.
"""

import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging

from .logging_config import get_logger
from .exceptions import AudioProcessingError

logger = get_logger(__name__)

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa/soundfile not available, audio quality detection disabled")


@dataclass
class AudioQualityMetrics:
    """Audio quality metrics."""
    # Basic metrics
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    
    # Quality metrics
    snr_db: Optional[float] = None  # Signal-to-noise ratio
    dynamic_range_db: Optional[float] = None
    peak_amplitude: float = 0.0
    rms_level: float = 0.0
    
    # Issue detection
    clipping_detected: bool = False
    silence_ratio: float = 0.0
    dc_offset: float = 0.0
    
    # Advanced metrics
    spectral_centroid_hz: Optional[float] = None
    spectral_rolloff_hz: Optional[float] = None
    zero_crossing_rate: Optional[float] = None
    
    # Quality score (0-100)
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'duration_seconds': round(self.duration_seconds, 2),
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'snr_db': round(self.snr_db, 2) if self.snr_db else None,
            'dynamic_range_db': round(self.dynamic_range_db, 2) if self.dynamic_range_db else None,
            'peak_amplitude': round(self.peak_amplitude, 4),
            'rms_level': round(self.rms_level, 4),
            'clipping_detected': self.clipping_detected,
            'silence_ratio': round(self.silence_ratio, 4),
            'dc_offset': round(self.dc_offset, 6),
            'spectral_centroid_hz': round(self.spectral_centroid_hz, 2) if self.spectral_centroid_hz else None,
            'spectral_rolloff_hz': round(self.spectral_rolloff_hz, 2) if self.spectral_rolloff_hz else None,
            'zero_crossing_rate': round(self.zero_crossing_rate, 4) if self.zero_crossing_rate else None,
            'quality_score': round(self.quality_score, 2),
            'issues': self.issues,
        }


class AudioQualityDetector:
    """
    Detect audio quality issues and calculate quality metrics.
    """
    
    # Quality thresholds
    SNR_THRESHOLD_DB = 20.0  # Minimum acceptable SNR
    DYNAMIC_RANGE_THRESHOLD_DB = 20.0  # Minimum acceptable dynamic range
    CLIPPING_THRESHOLD = 0.99  # Amplitude threshold for clipping detection
    SILENCE_THRESHOLD_DB = -60.0  # dB threshold for silence
    MAX_SILENCE_RATIO = 0.3  # Maximum acceptable silence ratio
    MAX_DC_OFFSET = 0.01  # Maximum acceptable DC offset
    
    def __init__(self):
        if not LIBROSA_AVAILABLE:
            raise ImportError(
                "librosa and soundfile required for audio quality detection. "
                "Install with: pip install librosa soundfile"
            )
    
    def analyze(
        self,
        audio_path: str,
        calculate_advanced: bool = False
    ) -> AudioQualityMetrics:
        """
        Analyze audio file quality.
        
        Args:
            audio_path: Path to audio file
            calculate_advanced: Calculate advanced spectral metrics
            
        Returns:
            AudioQualityMetrics
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        try:
            # Load audio
            y, sr = librosa.load(str(path), sr=None, mono=False)
            
            # Handle mono/stereo
            if y.ndim == 1:
                y = y.reshape(1, -1)
            
            channels = y.shape[0]
            
            # Use first channel for analysis
            y_mono = librosa.to_mono(y) if channels > 1 else y[0]
            
            metrics = AudioQualityMetrics(
                duration_seconds=float(len(y_mono)) / sr,
                sample_rate=sr,
                channels=channels
            )
            
            # Basic metrics
            metrics.peak_amplitude = float(np.max(np.abs(y_mono)))
            metrics.rms_level = float(np.sqrt(np.mean(y_mono ** 2)))
            metrics.dc_offset = float(np.mean(y_mono))
            
            # Detect clipping
            metrics.clipping_detected = metrics.peak_amplitude > self.CLIPPING_THRESHOLD
            
            # Calculate silence ratio
            silence_mask = np.abs(y_mono) < (10 ** (self.SILENCE_THRESHOLD_DB / 20))
            metrics.silence_ratio = float(np.mean(silence_mask))
            
            # Calculate SNR (simple estimation)
            metrics.snr_db = self._estimate_snr(y_mono)
            
            # Calculate dynamic range
            metrics.dynamic_range_db = self._calculate_dynamic_range(y_mono)
            
            # Advanced metrics
            if calculate_advanced:
                metrics.spectral_centroid_hz = float(np.mean(
                    librosa.feature.spectral_centroid(y=y_mono, sr=sr)
                ))
                metrics.spectral_rolloff_hz = float(np.mean(
                    librosa.feature.spectral_rolloff(y=y_mono, sr=sr)
                ))
                metrics.zero_crossing_rate = float(np.mean(
                    librosa.feature.zero_crossing_rate(y_mono)
                ))
            
            # Detect issues
            metrics.issues = self._detect_issues(metrics)
            
            # Calculate overall quality score
            metrics.quality_score = self._calculate_quality_score(metrics)
            
            return metrics
            
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to analyze audio quality: {e}",
                file_path=audio_path
            )
    
    def _estimate_snr(self, y: np.ndarray) -> float:
        """
        Estimate signal-to-noise ratio.
        
        Uses a simple approach: assumes quietest segments are noise.
        """
        # Split into frames
        frame_length = 2048
        hop_length = 512
        
        frames = librosa.util.frame(y, frame_length=frame_length, hop_length=hop_length)
        
        # Calculate RMS for each frame
        rms = np.sqrt(np.mean(frames ** 2, axis=0))
        
        # Assume lowest 10% of frames are noise
        noise_frames = np.percentile(rms, 10)
        signal_frames = np.percentile(rms, 90)
        
        if noise_frames <= 0:
            return 60.0  # Very clean signal
        
        snr = 20 * np.log10(signal_frames / noise_frames)
        return float(snr)
    
    def _calculate_dynamic_range(self, y: np.ndarray) -> float:
        """Calculate dynamic range in dB."""
        # Use percentile-based approach
        peak = np.percentile(np.abs(y), 99.9)
        floor = np.percentile(np.abs(y), 0.1)
        
        if floor <= 0:
            floor = 1e-10
        
        return float(20 * np.log10(peak / floor))
    
    def _detect_issues(self, metrics: AudioQualityMetrics) -> List[str]:
        """Detect quality issues."""
        issues = []
        
        if metrics.clipping_detected:
            issues.append("Audio clipping detected - reduce input volume")
        
        if metrics.snr_db is not None and metrics.snr_db < self.SNR_THRESHOLD_DB:
            issues.append(f"Low SNR ({metrics.snr_db:.1f} dB) - noisy audio")
        
        if metrics.dynamic_range_db is not None and metrics.dynamic_range_db < self.DYNAMIC_RANGE_THRESHOLD_DB:
            issues.append(f"Low dynamic range ({metrics.dynamic_range_db:.1f} dB) - compressed audio")
        
        if metrics.silence_ratio > self.MAX_SILENCE_RATIO:
            issues.append(f"High silence ratio ({metrics.silence_ratio:.1%}) - excessive pauses")
        
        if abs(metrics.dc_offset) > self.MAX_DC_OFFSET:
            issues.append(f"DC offset detected ({metrics.dc_offset:.4f}) - may cause clicks")
        
        if metrics.peak_amplitude < 0.1:
            issues.append(f"Very low amplitude ({metrics.peak_amplitude:.4f}) - audio may be too quiet")
        
        return issues
    
    def _calculate_quality_score(self, metrics: AudioQualityMetrics) -> float:
        """Calculate overall quality score (0-100)."""
        score = 100.0
        
        # Penalize clipping heavily
        if metrics.clipping_detected:
            score -= 30
        
        # SNR penalty
        if metrics.snr_db is not None:
            if metrics.snr_db < self.SNR_THRESHOLD_DB:
                score -= (self.SNR_THRESHOLD_DB - metrics.snr_db) * 2
        
        # Dynamic range penalty
        if metrics.dynamic_range_db is not None:
            if metrics.dynamic_range_db < self.DYNAMIC_RANGE_THRESHOLD_DB:
                score -= (self.DYNAMIC_RANGE_THRESHOLD_DB - metrics.dynamic_range_db)
        
        # Silence ratio penalty
        if metrics.silence_ratio > self.MAX_SILENCE_RATIO:
            score -= (metrics.silence_ratio - self.MAX_SILENCE_RATIO) * 100
        
        # DC offset penalty
        if abs(metrics.dc_offset) > self.MAX_DC_OFFSET:
            score -= abs(metrics.dc_offset) * 1000
        
        # Low amplitude penalty
        if metrics.peak_amplitude < 0.1:
            score -= (0.1 - metrics.peak_amplitude) * 100
        
        return max(0.0, min(100.0, score))
    
    def validate_for_voice_cloning(
        self,
        audio_path: str,
        min_duration: float = 5.0,
        max_duration: float = 60.0
    ) -> Tuple[bool, List[str]]:
        """
        Validate audio file for voice cloning.
        
        Args:
            audio_path: Path to audio file
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            metrics = self.analyze(audio_path)
        except Exception as e:
            return False, [f"Failed to analyze audio: {e}"]
        
        # Duration check
        if metrics.duration_seconds < min_duration:
            issues.append(f"Audio too short ({metrics.duration_seconds:.1f}s, minimum {min_duration}s)")
        
        if metrics.duration_seconds > max_duration:
            issues.append(f"Audio too long ({metrics.duration_seconds:.1f}s, maximum {max_duration}s)")
        
        # Quality checks
        if metrics.clipping_detected:
            issues.append("Audio has clipping distortion")
        
        if metrics.snr_db is not None and metrics.snr_db < 15:
            issues.append(f"Audio too noisy (SNR: {metrics.snr_db:.1f} dB)")
        
        if metrics.silence_ratio > 0.2:
            issues.append(f"Too much silence ({metrics.silence_ratio:.1%})")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def batch_analyze(
        self,
        audio_files: List[str],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, AudioQualityMetrics]:
        """
        Analyze multiple audio files.
        
        Args:
            audio_files: List of audio file paths
            progress_callback: Optional callback(current, total)
            
        Returns:
            Dictionary mapping file paths to metrics
        """
        results = {}
        total = len(audio_files)
        
        for i, path in enumerate(audio_files):
            try:
                results[path] = self.analyze(path)
            except Exception as e:
                logger.error(f"Failed to analyze {path}: {e}")
                results[path] = None
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def generate_report(
        self,
        metrics: AudioQualityMetrics,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate human-readable quality report.
        
        Args:
            metrics: Audio quality metrics
            output_path: Optional path to save report
            
        Returns:
            Report text
        """
        lines = [
            "=" * 50,
            "Audio Quality Report",
            "=" * 50,
            "",
            f"Duration: {metrics.duration_seconds:.2f} seconds",
            f"Sample Rate: {metrics.sample_rate} Hz",
            f"Channels: {metrics.channels}",
            "",
            "Quality Metrics:",
            f"  SNR: {metrics.snr_db:.1f} dB" if metrics.snr_db else "  SNR: N/A",
            f"  Dynamic Range: {metrics.dynamic_range_db:.1f} dB" if metrics.dynamic_range_db else "  Dynamic Range: N/A",
            f"  Peak Amplitude: {metrics.peak_amplitude:.4f}",
            f"  RMS Level: {metrics.rms_level:.4f}",
            f"  Silence Ratio: {metrics.silence_ratio:.2%}",
            "",
            f"Overall Quality Score: {metrics.quality_score:.1f}/100",
            "",
        ]
        
        if metrics.issues:
            lines.append("Issues Detected:")
            for issue in metrics.issues:
                lines.append(f"  ⚠️  {issue}")
        else:
            lines.append("✅ No issues detected")
        
        lines.append("=" * 50)
        
        report = "\n".join(lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
        
        return report
