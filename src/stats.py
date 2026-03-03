"""
Statistics and analytics for audiobook generation.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GenerationStats:
    """Statistics for a single generation task."""
    task_id: str
    input_file: str
    output_file: str
    backend: str
    voice: str
    total_chars: int
    total_chunks: int
    duration_seconds: float
    start_time: str
    end_time: str
    cost_estimate: float  # Estimated cost in USD/RMB
    
    @property
    def chars_per_second(self) -> float:
        """Characters processed per second."""
        if self.duration_seconds > 0:
            return self.total_chars / self.duration_seconds
        return 0.0
    
    @property
    def cost_per_1k_chars(self) -> float:
        """Cost per 1000 characters."""
        if self.total_chars > 0:
            return (self.cost_estimate / self.total_chars) * 1000
        return 0.0


class StatsTracker:
    """Track and analyze generation statistics."""
    
    # Cost estimates per 1M characters (approximate)
    COST_RATES = {
        'doubao': 0.7,      # ~5 RMB per 1M chars
        'elevenlabs': 4.0,  # ~$4 per 1M chars
        'xtts': 0.0,        # Free (local)
        'kokoro': 0.0,      # Free (local)
    }
    
    def __init__(self, stats_dir: Optional[str] = None):
        """
        Initialize stats tracker.
        
        Args:
            stats_dir: Directory for stats persistence
        """
        if stats_dir is None:
            stats_dir = Path.home() / '.novel-audiobook-generator' / 'stats'
        else:
            stats_dir = Path(stats_dir)
        
        self.stats_dir = stats_dir
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats_file = self.stats_dir / 'generation_stats.jsonl'
        self.daily_stats: Dict[str, List[GenerationStats]] = defaultdict(list)
        
        # Load existing stats
        self._load_stats()
    
    def _load_stats(self):
        """Load stats from disk."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            stat = GenerationStats(**data)
                            day = stat.start_time[:10]  # YYYY-MM-DD
                            self.daily_stats[day].append(stat)
                logger.info(f"Loaded stats for {len(self.daily_stats)} days")
            except Exception as e:
                logger.error(f"Failed to load stats: {e}")
    
    def record_generation(
        self,
        task_id: str,
        input_file: str,
        output_file: str,
        backend: str,
        voice: str,
        total_chars: int,
        total_chunks: int,
        duration_seconds: float,
        start_time: datetime
    ) -> GenerationStats:
        """
        Record a generation task.
        
        Returns:
            GenerationStats object
        """
        end_time = datetime.now()
        
        # Estimate cost
        cost = (total_chars / 1_000_000) * self.COST_RATES.get(backend, 0)
        
        stat = GenerationStats(
            task_id=task_id,
            input_file=input_file,
            output_file=output_file,
            backend=backend,
            voice=voice,
            total_chars=total_chars,
            total_chunks=total_chunks,
            duration_seconds=duration_seconds,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            cost_estimate=cost
        )
        
        # Save to file
        with open(self.stats_file, 'a') as f:
            f.write(json.dumps(asdict(stat)) + '\n')
        
        # Add to memory
        day = stat.start_time[:10]
        self.daily_stats[day].append(stat)
        
        logger.info(f"Stats recorded: {total_chars} chars in {duration_seconds:.1f}s")
        
        return stat
    
    def get_daily_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for the last N days.
        
        Returns:
            Dictionary of date -> stats
        """
        result = {}
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            stats = self.daily_stats.get(date, [])
            
            if stats:
                total_chars = sum(s.total_chars for s in stats)
                total_cost = sum(s.cost_estimate for s in stats)
                total_time = sum(s.duration_seconds for s in stats)
                
                result[date] = {
                    'generations': len(stats),
                    'total_chars': total_chars,
                    'total_cost': round(total_cost, 4),
                    'total_time_seconds': round(total_time, 1),
                    'avg_speed': round(total_chars / total_time, 1) if total_time > 0 else 0
                }
            else:
                result[date] = {
                    'generations': 0,
                    'total_chars': 0,
                    'total_cost': 0,
                    'total_time_seconds': 0,
                    'avg_speed': 0
                }
        
        return result
    
    def get_backend_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics grouped by backend."""
        backend_stats = defaultdict(lambda: {
            'generations': 0,
            'total_chars': 0,
            'total_cost': 0.0,
            'total_time': 0.0
        })
        
        for day_stats in self.daily_stats.values():
            for stat in day_stats:
                backend = stat.backend
                backend_stats[backend]['generations'] += 1
                backend_stats[backend]['total_chars'] += stat.total_chars
                backend_stats[backend]['total_cost'] += stat.cost_estimate
                backend_stats[backend]['total_time'] += stat.duration_seconds
        
        # Calculate averages
        for backend, stats in backend_stats.items():
            if stats['generations'] > 0:
                stats['avg_chars_per_gen'] = stats['total_chars'] / stats['generations']
                stats['avg_cost_per_gen'] = stats['total_cost'] / stats['generations']
                stats['avg_time_per_gen'] = stats['total_time'] / stats['generations']
        
        return dict(backend_stats)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall summary statistics."""
        total_generations = 0
        total_chars = 0
        total_cost = 0.0
        total_time = 0.0
        
        for day_stats in self.daily_stats.values():
            for stat in day_stats:
                total_generations += 1
                total_chars += stat.total_chars
                total_cost += stat.cost_estimate
                total_time += stat.duration_seconds
        
        return {
            'total_generations': total_generations,
            'total_chars': total_chars,
            'total_cost': round(total_cost, 4),
            'total_time_hours': round(total_time / 3600, 2),
            'avg_speed_chars_per_sec': round(total_chars / total_time, 1) if total_time > 0 else 0,
            'avg_cost_per_1m_chars': round((total_cost / total_chars) * 1_000_000, 4) if total_chars > 0 else 0
        }
    
    def print_report(self):
        """Print statistics report."""
        print("=" * 60)
        print("📊 Generation Statistics Report")
        print("=" * 60)
        
        # Summary
        summary = self.get_summary()
        print("\n📈 Overall Summary:")
        print(f"  Total Generations: {summary['total_generations']}")
        print(f"  Total Characters: {summary['total_chars']:,}")
        print(f"  Total Cost: ${summary['total_cost']:.4f}")
        print(f"  Total Time: {summary['total_time_hours']:.2f} hours")
        print(f"  Avg Speed: {summary['avg_speed_chars_per_sec']:.1f} chars/sec")
        print(f"  Avg Cost: ${summary['avg_cost_per_1m_chars']:.4f} per 1M chars")
        
        # Daily stats (last 7 days)
        print("\n📅 Last 7 Days:")
        daily = self.get_daily_stats(7)
        for date, stats in sorted(daily.items()):
            if stats['generations'] > 0:
                print(f"  {date}: {stats['generations']} gens, "
                      f"{stats['total_chars']:,} chars, "
                      f"${stats['total_cost']:.4f}")
        
        # Backend stats
        print("\n🎙️  By Backend:")
        backend_stats = self.get_backend_stats()
        for backend, stats in backend_stats.items():
            print(f"  {backend}: {stats['generations']} gens, "
                  f"${stats['total_cost']:.4f} total")
        
        print("\n" + "=" * 60)


if __name__ == '__main__':
    tracker = StatsTracker()
    tracker.print_report()
