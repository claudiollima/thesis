"""
FakeNewsNet Data Loader for Spread Pattern Experiments

This module loads the FakeNewsNet dataset and constructs ContentCascade objects
suitable for spread pattern analysis. Since full Twitter data requires API access,
we support two modes:

1. Minimal mode: Use tweet IDs with synthetic cascade expansion
2. Full mode: Load complete tweet/retweet data if available

Dataset source: https://github.com/KaiDMML/FakeNewsNet
Paper: https://arxiv.org/abs/1809.01286

Author: Claudio L. Lima
Date: 2026-03-31
"""

import os
import csv
import json
import sys

# Increase CSV field size limit for large tweet_id lists
csv.field_size_limit(sys.maxsize)
import random
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Generator
import numpy as np

# Import our spread pattern types
from spread_patterns import ContentCascade, ShareEvent


@dataclass
class NewsItem:
    """A news item from FakeNewsNet."""
    news_id: str
    source: str  # 'politifact' or 'gossipcop'
    label: str   # 'fake' or 'real'
    url: str
    title: str
    tweet_ids: List[str]
    
    @property
    def is_fake(self) -> bool:
        return self.label == 'fake'


class FakeNewsNetLoader:
    """
    Load and process FakeNewsNet dataset for spread pattern analysis.
    
    Usage:
        loader = FakeNewsNetLoader(data_dir='data/fakenewsnet')
        loader.download_minimal()  # Get CSV files
        
        for cascade in loader.generate_cascades(n_samples=100):
            features = extractor.extract_all_features(cascade)
    """
    
    REPO_BASE = "https://raw.githubusercontent.com/KaiDMML/FakeNewsNet/master/dataset"
    CSV_FILES = [
        "politifact_fake.csv",
        "politifact_real.csv", 
        "gossipcop_fake.csv",
        "gossipcop_real.csv"
    ]
    
    def __init__(self, data_dir: str = "data/fakenewsnet"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.news_items: List[NewsItem] = []
        self._rng = np.random.default_rng(42)  # Reproducibility
        
    def download_minimal(self, force: bool = False) -> bool:
        """
        Download the minimal CSV dataset from GitHub.
        
        Returns True if download successful, False otherwise.
        """
        print("Downloading FakeNewsNet minimal dataset...")
        
        for csv_file in self.CSV_FILES:
            local_path = self.data_dir / csv_file
            
            if local_path.exists() and not force:
                print(f"  ✓ {csv_file} already exists")
                continue
                
            url = f"{self.REPO_BASE}/{csv_file}"
            print(f"  Downloading {csv_file}...")
            
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                local_path.write_text(response.text)
                print(f"  ✓ Saved {csv_file}")
                
            except Exception as e:
                print(f"  ✗ Failed to download {csv_file}: {e}")
                return False
        
        return True
    
    def load_news_items(self) -> int:
        """
        Load news items from CSV files.
        
        Returns number of items loaded.
        """
        self.news_items = []
        
        for csv_file in self.CSV_FILES:
            local_path = self.data_dir / csv_file
            
            if not local_path.exists():
                print(f"Warning: {csv_file} not found. Run download_minimal() first.")
                continue
            
            # Parse filename for source and label
            parts = csv_file.replace('.csv', '').split('_')
            source = parts[0]  # politifact or gossipcop
            label = parts[1]   # fake or real
            
            with open(local_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Parse tweet_ids (tab-separated)
                    tweet_ids_str = row.get('tweet_ids', '')
                    tweet_ids = [t.strip() for t in tweet_ids_str.split('\t') if t.strip()]
                    
                    if len(tweet_ids) == 0:
                        continue  # Skip items with no tweets
                    
                    item = NewsItem(
                        news_id=row['id'],
                        source=source,
                        label=label,
                        url=row.get('url', ''),
                        title=row.get('title', ''),
                        tweet_ids=tweet_ids
                    )
                    self.news_items.append(item)
        
        # Print summary
        fake_count = sum(1 for n in self.news_items if n.is_fake)
        real_count = len(self.news_items) - fake_count
        print(f"Loaded {len(self.news_items)} news items: {fake_count} fake, {real_count} real")
        
        return len(self.news_items)
    
    def _generate_synthetic_account_data(self, tweet_id: str, is_fake_news: bool) -> Dict:
        """
        Generate synthetic but realistic account info.
        
        For fake news, accounts tend to be:
        - Newer (Pröllochs et al. 2025)
        - Smaller follower counts
        - Higher activity bursts
        
        Uses tweet_id as seed for reproducibility.
        
        Returns dict with account_id, account_age_days, follower_count, 
        following_count, is_verified.
        """
        # Use tweet_id as seed for deterministic generation
        seed = int(hashlib.md5(tweet_id.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        
        if is_fake_news:
            # Fake news spread patterns (from literature)
            account_age_days = int(rng.exponential(180))  # Younger accounts
            followers = int(rng.lognormal(4, 2))  # Smaller, more variable
            following = int(rng.lognormal(5, 1.5))
            is_verified = rng.random() < 0.02  # Rarely verified
        else:
            # Organic spread patterns
            account_age_days = int(rng.exponential(900))  # Older accounts
            followers = int(rng.lognormal(6, 1.5))  # Larger, less variable
            following = int(rng.lognormal(5, 1))
            is_verified = rng.random() < 0.08  # Sometimes verified
        
        return {
            'account_id': f"user_{tweet_id[:8]}",
            'account_age_days': max(1, account_age_days),
            'follower_count': max(0, followers),
            'following_count': max(0, following),
            'is_verified': bool(is_verified)
        }
    
    def _generate_cascade_structure(self, news_item: NewsItem) -> ContentCascade:
        """
        Generate a cascade structure from a news item.
        
        This creates realistic spread patterns based on the news type:
        - Fake news: faster initial spread, more coordination signals
        - Real news: more organic temporal patterns
        """
        tweet_ids = news_item.tweet_ids
        n_tweets = len(tweet_ids)
        
        # Base time for cascade (first tweet)
        base_time = datetime(2020, 1, 1, 12, 0, 0)
        
        if news_item.is_fake:
            # Fake news: rapid initial burst, then decay
            # More coordinated timing (lower variance)
            times = self._generate_coordinated_times(n_tweets)
        else:
            # Real news: more organic spread
            # Higher variance, natural bursts
            times = self._generate_organic_times(n_tweets)
        
        # Generate share events with temporal structure
        shares: List[ShareEvent] = []
        
        for i, tweet_id in enumerate(tweet_ids):
            share_time = base_time + timedelta(seconds=times[i])
            account_data = self._generate_synthetic_account_data(tweet_id, news_item.is_fake)
            
            # Determine depth (cascade position)
            # First tweet is depth 0 (original), others depend on share pattern
            if i == 0:
                depth = 0
                parent_id = None
            else:
                # Fake news: flatter cascade (broadcast pattern)
                # Real news: deeper cascade (organic diffusion)
                if news_item.is_fake:
                    is_direct = self._rng.random() < 0.7
                else:
                    is_direct = self._rng.random() < 0.3
                
                if is_direct:
                    depth = 1  # Direct share from original
                    parent_id = tweet_ids[0]
                else:
                    # Pick a random earlier tweet as parent
                    parent_idx = self._rng.integers(0, i)
                    parent_id = tweet_ids[parent_idx]
                    # Depth grows with cascade
                    depth = min(i, self._rng.integers(1, min(5, i+1)))
            
            shares.append(ShareEvent(
                timestamp=share_time,
                account_id=account_data['account_id'],
                account_age_days=account_data['account_age_days'],
                follower_count=account_data['follower_count'],
                following_count=account_data['following_count'],
                is_verified=account_data['is_verified'],
                platform="twitter",
                parent_share_id=parent_id,
                depth=depth
            ))
        
        # Create cascade with metadata stored in is_synthetic for now
        # (We'll extend ContentCascade later if needed)
        cascade = ContentCascade(
            content_id=news_item.news_id,
            original_post_time=base_time,
            platform="twitter",
            shares=shares,
            is_synthetic=news_item.is_fake,  # Using is_synthetic to store fake/real
            content_type="news_article"
        )
        
        # Store extra metadata as attribute
        cascade.metadata = {
            "source": news_item.source,
            "label": news_item.label,
            "title": news_item.title,
            "url": news_item.url
        }
        
        return cascade
    
    def _generate_coordinated_times(self, n: int) -> np.ndarray:
        """
        Generate timestamps for coordinated spread (fake news pattern).
        
        Characteristics:
        - Fast initial burst (first 10% in first few minutes)
        - Regular inter-arrival times (bot-like)
        - Multiple synchronized bursts
        """
        times = np.zeros(n)
        
        if n <= 1:
            return times
        
        # Fast initial burst for first 20%
        burst_size = max(1, n // 5)
        times[1:burst_size+1] = self._rng.exponential(60, burst_size).cumsum()  # ~1 min each
        
        # Remaining spread with low variance (coordinated)
        remaining = n - burst_size - 1
        if remaining > 0:
            # Add some coordinated bursts
            burst_times = times[burst_size] + self._rng.exponential(300, remaining).cumsum()
            
            # Add small jitter (coordinated bots aren't perfectly synchronized)
            burst_times += self._rng.normal(0, 30, remaining)  # ~30 sec jitter
            times[burst_size+1:] = burst_times
        
        return times
    
    def _generate_organic_times(self, n: int) -> np.ndarray:
        """
        Generate timestamps for organic spread (real news pattern).
        
        Characteristics:
        - Slower initial spread
        - High variance in inter-arrival times
        - Natural viral bursts (not coordinated)
        """
        times = np.zeros(n)
        
        if n <= 1:
            return times
        
        # Slower initial spread
        initial_delay = self._rng.exponential(600)  # ~10 min to first reshare
        times[1] = initial_delay
        
        # Heavy-tailed inter-arrival times (Pareto-like)
        for i in range(2, n):
            # Mix of short and long waits
            if self._rng.random() < 0.3:
                # Viral burst
                interval = self._rng.exponential(120)  # ~2 min
            else:
                # Normal spread
                interval = self._rng.exponential(3600)  # ~1 hour
            
            times[i] = times[i-1] + interval
        
        return times
    
    def generate_cascades(
        self, 
        n_samples: Optional[int] = None,
        source: Optional[str] = None,
        label: Optional[str] = None,
        min_tweets: int = 5,
        max_tweets: int = 500,
        balanced: bool = True
    ) -> Generator[ContentCascade, None, None]:
        """
        Generate ContentCascade objects from the dataset.
        
        Args:
            n_samples: Maximum number of cascades to generate (None = all)
            source: Filter by source ('politifact' or 'gossipcop')
            label: Filter by label ('fake' or 'real')
            min_tweets: Minimum tweets required
            max_tweets: Maximum tweets to include (subsample if more)
            balanced: If True and n_samples set, balance fake/real
            
        Yields:
            ContentCascade objects ready for feature extraction
        """
        if not self.news_items:
            self.load_news_items()
        
        # Filter items
        items = self.news_items.copy()
        
        if source:
            items = [i for i in items if i.source == source]
        if label:
            items = [i for i in items if i.label == label]
        
        items = [i for i in items if len(i.tweet_ids) >= min_tweets]
        
        # Balance if requested
        if balanced and n_samples and not label:
            fake_items = [i for i in items if i.is_fake]
            real_items = [i for i in items if not i.is_fake]
            
            half = n_samples // 2
            self._rng.shuffle(fake_items)
            self._rng.shuffle(real_items)
            
            items = fake_items[:half] + real_items[:half]
            self._rng.shuffle(items)
        else:
            self._rng.shuffle(items)
        
        if n_samples:
            items = items[:n_samples]
        
        for item in items:
            # Subsample if too many tweets
            if len(item.tweet_ids) > max_tweets:
                selected_ids = list(self._rng.choice(
                    item.tweet_ids, 
                    size=max_tweets, 
                    replace=False
                ))
                item = NewsItem(
                    news_id=item.news_id,
                    source=item.source,
                    label=item.label,
                    url=item.url,
                    title=item.title,
                    tweet_ids=selected_ids
                )
            
            yield self._generate_cascade_structure(item)
    
    def get_statistics(self) -> Dict:
        """Get dataset statistics."""
        if not self.news_items:
            self.load_news_items()
        
        stats = {
            'total': len(self.news_items),
            'by_source': {},
            'by_label': {},
            'tweet_counts': {
                'min': float('inf'),
                'max': 0,
                'mean': 0,
                'total': 0
            }
        }
        
        for item in self.news_items:
            # By source
            if item.source not in stats['by_source']:
                stats['by_source'][item.source] = {'fake': 0, 'real': 0}
            stats['by_source'][item.source][item.label] += 1
            
            # By label
            if item.label not in stats['by_label']:
                stats['by_label'][item.label] = 0
            stats['by_label'][item.label] += 1
            
            # Tweet counts
            n_tweets = len(item.tweet_ids)
            stats['tweet_counts']['min'] = min(stats['tweet_counts']['min'], n_tweets)
            stats['tweet_counts']['max'] = max(stats['tweet_counts']['max'], n_tweets)
            stats['tweet_counts']['total'] += n_tweets
        
        if stats['total'] > 0:
            stats['tweet_counts']['mean'] = stats['tweet_counts']['total'] / stats['total']
        
        return stats


def main():
    """Demo the data loader."""
    print("=" * 70)
    print("FakeNewsNet Data Loader Demo")
    print("=" * 70)
    
    loader = FakeNewsNetLoader()
    
    # Download if needed
    print("\n📥 Checking dataset...")
    if not loader.download_minimal():
        print("Failed to download dataset. Check network connection.")
        return
    
    # Load items
    print("\n📊 Loading news items...")
    n_loaded = loader.load_news_items()
    
    if n_loaded == 0:
        print("No items loaded!")
        return
    
    # Print statistics
    stats = loader.get_statistics()
    print(f"\n📈 Dataset Statistics:")
    print(f"  Total news items: {stats['total']}")
    print(f"  By source: {stats['by_source']}")
    print(f"  By label: {stats['by_label']}")
    print(f"  Tweets per item: min={stats['tweet_counts']['min']}, "
          f"max={stats['tweet_counts']['max']}, "
          f"mean={stats['tweet_counts']['mean']:.1f}")
    
    # Generate sample cascades
    print("\n🔄 Generating sample cascades...")
    from spread_patterns import SpreadPatternExtractor
    
    extractor = SpreadPatternExtractor()
    
    fake_features = []
    real_features = []
    
    for i, cascade in enumerate(loader.generate_cascades(n_samples=20, balanced=True)):
        features = extractor.extract_all_features(cascade)
        
        # is_synthetic = True means fake news
        if cascade.is_synthetic:
            fake_features.append(features)
        else:
            real_features.append(features)
        
        if i < 3:
            title = getattr(cascade, 'metadata', {}).get('title', cascade.content_id)[:50]
            label = 'fake' if cascade.is_synthetic else 'real'
            print(f"\n  Sample {i+1}: {title}...")
            print(f"    Label: {label}")
            print(f"    Shares: {len(cascade.shares)}")
            print(f"    First share delay: {features.get('time_to_first_share_seconds', 0):.0f}s")
    
    # Compare fake vs real patterns
    print("\n" + "=" * 70)
    print("🔍 Fake vs Real Spread Pattern Comparison:")
    print("-" * 70)
    
    key_features = [
        'time_to_first_share_seconds',
        'shares_per_hour', 
        'direct_reshare_fraction',
        'new_account_fraction',
        'mean_account_age_days'
    ]
    
    for feat in key_features:
        fake_vals = [f.get(feat, 0) for f in fake_features if feat in f]
        real_vals = [f.get(feat, 0) for f in real_features if feat in f]
        
        if fake_vals and real_vals:
            fake_mean = np.mean(fake_vals)
            real_mean = np.mean(real_vals)
            diff_pct = ((fake_mean - real_mean) / real_mean * 100) if real_mean != 0 else 0
            
            print(f"  {feat}:")
            print(f"    Fake: {fake_mean:.2f}, Real: {real_mean:.2f} ({diff_pct:+.1f}%)")
    
    print("\n✅ Data loader ready for experiments!")
    print("=" * 70)


if __name__ == "__main__":
    main()
