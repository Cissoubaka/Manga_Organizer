#!/usr/bin/env python3
"""
Analytics Profiler
Profiles the performance of AudioAnalytics aggregation methods
"""

import time
import cProfile
import pstats
import io
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def profile_analytics(test_data_file='data/audit_logs_test.txt'):
    """Profile analytics performance"""
    
    print("=" * 70)
    print("📊 ANALYTICS PERFORMANCE PROFILER")
    print("=" * 70 + "\n")
    
    # Check if test data exists
    if not Path(test_data_file).exists():
        print(f"❌ Test data file not found: {test_data_file}")
        print("   Generate test data first with: python test_data_generator.py")
        return False
    
    print(f"📁 Loading test data from {test_data_file}...\n")
    
    # Import after path is set
    from blueprints.audit.analytics import ActivityAnalytics
    from audit_log import read_audit_logs
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Benchmark each method
    analytics = ActivityAnalytics()
    results = {}
    
    methods_to_profile = [
        ('get_quick_stats', lambda: analytics.get_quick_stats()),
        ('get_activity_trend', lambda: analytics.get_activity_trend(days=7)),
        ('get_failed_login_stats', lambda: analytics.get_failed_login_stats(days=7)),
        ('get_user_activity_chart', lambda: analytics.get_user_activity_chart(limit=10)),
        ('get_ip_statistics', lambda: analytics.get_ip_statistics(limit=10)),
        ('get_recent_activity', lambda: analytics.get_recent_activity(limit=50)),
        ('get_action_distribution', lambda: analytics.get_action_distribution()),
    ]
    
    print("📈 Profiling individual methods:\n")
    
    for method_name, method_call in methods_to_profile:
        print(f"  🔍 {method_name}...", end=" ", flush=True)
        
        # Warmup
        try:
            method_call()
        except:
            pass
        
        # Profile
        times = []
        for _ in range(3):
            start = time.time()
            try:
                method_call()
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
            except Exception as e:
                print(f"❌ Error: {e}")
                break
        
        if times:
            avg_time = sum(times) / len(times)
            results[method_name] = avg_time
            print(f"✅ {avg_time:.0f}ms (avg of 3 runs)")
    
    print("\n")
    
    # Profile all methods together
    print("📊 Profiling all methods combined:\n")
    
    profiler.enable()
    
    for _ in range(3):
        analytics.get_quick_stats()
        analytics.get_activity_trend(days=7)
        analytics.get_failed_login_stats(days=7)
        analytics.get_user_activity_chart(limit=10)
        analytics.get_ip_statistics(limit=10)
        analytics.get_recent_activity(limit=50)
        analytics.get_action_distribution()
    
    profiler.disable()
    
    # Print profiler stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(15)  # Top 15 functions
    
    print("Top 15 functions by cumulative time:\n")
    print(s.getvalue())
    
    # Memory analysis
    print("\n" + "=" * 70)
    print("💾 MEMORY ANALYSIS")
    print("=" * 70 + "\n")
    
    import json
    
    file_size = Path(test_data_file).stat().st_size / (1024 * 1024)
    
    with open(test_data_file, 'r') as f:
        lines = f.readlines()
        log_count = len(lines)
    
    print(f"Test data file: {file_size:.2f} MB ({log_count:,} logs)")
    print()
    
    # Estimate memory usage
    sample_log = json.loads(lines[0])
    single_log_size = len(json.dumps(sample_log).encode('utf-8'))
    all_logs_size = single_log_size * log_count / (1024 * 1024)
    
    print(f"Single log size: ~{single_log_size} bytes")
    print(f"All logs in memory: ~{all_logs_size:.2f} MB")
    print()
    
    return True

def main():
    """Main execution"""
    import sys
    
    if len(sys.argv) > 1:
        test_data_file = sys.argv[1]
    else:
        test_data_file = 'data/audit_logs_test.txt'
    
    if not profile_analytics(test_data_file):
        sys.exit(1)
    
    print("\n✅ Profiling complete\n")

if __name__ == '__main__':
    main()
