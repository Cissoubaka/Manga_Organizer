#!/usr/bin/env python3
"""
Benchmark Runner for Audit API
Measures performance of audit endpoints and generates report
"""

import time
import json
import requests
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Configuration
BASE_URL = "http://localhost:5000"
AUDIT_ENDPOINTS = [
    '/audit/dashboard-data',
    '/audit/activity-trend',
    '/audit/ip-statistics',
    '/audit/quick-stats',
    '/audit/recent-activity',
]

EXPORT_ENDPOINTS = [
    ('/audit/export/preview', 'POST', {'filters': {}, 'limit': 100}),
    ('/audit/export/csv', 'POST', {'filters': {}}),
    ('/audit/export/json', 'POST', {'filters': {}}),
]

class BenchmarkRunner:
    """Benchmark runner for audit API endpoints"""
    
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.results = defaultdict(list)
        self.errors = defaultdict(list)
        self.start_time = None
        self.session = requests.Session()
        
    def check_server(self):
        """Check if server is running"""
        try:
            response = self.session.get(f"{self.base_url}/auth/current-user", timeout=2)
            if response.status_code in [200, 401]:  # 401 is OK if not authenticated
                return True
        except:
            pass
        return False
    
    def benchmark_endpoint(self, endpoint, method='GET', data=None, iterations=5):
        """
        Benchmark a single endpoint
        
        Args:
            endpoint: URL path (e.g., '/audit/dashboard-data')
            method: HTTP method ('GET' or 'POST')
            data: Request body data (for POST)
            iterations: Number of times to call the endpoint
        """
        times = []
        errors = 0
        
        print(f"  📍 {method} {endpoint}...", end=" ", flush=True)
        
        for i in range(iterations):
            try:
                url = f"{self.base_url}{endpoint}"
                start = time.time()
                
                if method == 'POST':
                    response = self.session.post(
                        url,
                        json=data,
                        timeout=10,
                        headers={'Content-Type': 'application/json'}
                    )
                else:
                    response = self.session.get(url, timeout=10)
                
                elapsed = (time.time() - start) * 1000  # Convert to ms
                
                if response.status_code in [200, 401]:
                    times.append(elapsed)
                else:
                    errors += 1
                    self.errors[endpoint].append(f"Status: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                errors += 1
                self.errors[endpoint].append("Timeout")
            except Exception as e:
                errors += 1
                self.errors[endpoint].append(str(e))
        
        # Calculate statistics
        if times:
            min_ms = min(times)
            max_ms = max(times)
            avg_ms = statistics.mean(times)
            
            self.results[endpoint] = {
                'method': method,
                'iterations': iterations,
                'successes': len(times),
                'errors': errors,
                'min_ms': min_ms,
                'max_ms': max_ms,
                'avg_ms': avg_ms,
                'times': times
            }
            
            # Print result
            status = "✅" if errors == 0 else "⚠️"
            print(f"{status} {avg_ms:.0f}ms (min: {min_ms:.0f}ms, max: {max_ms:.0f}ms)")
        else:
            print(f"❌ All requests failed")
            self.results[endpoint] = {
                'method': method,
                'iterations': iterations,
                'successes': 0,
                'errors': errors
            }
    
    def run_benchmarks(self):
        """Run all benchmarks"""
        print("\n" + "=" * 70)
        print("🔍 AUDIT API PERFORMANCE BENCHMARK")
        print("=" * 70 + "\n")
        
        # Check server
        print("🔌 Checking server connection...", end=" ", flush=True)
        if not self.check_server():
            print("❌ Server not responding at", self.base_url)
            print("   Start the server with: python run.py")
            return False
        print("✅ Connected\n")
        
        # Benchmark GET endpoints
        print("📊 Benchmarking Dashboard Endpoints:")
        for endpoint in AUDIT_ENDPOINTS:
            self.benchmark_endpoint(endpoint, 'GET', iterations=5)
        
        print("\n📁 Benchmarking Export Endpoints:")
        for endpoint, method, data in EXPORT_ENDPOINTS:
            self.benchmark_endpoint(endpoint, method, data, iterations=3)
        
        return True
    
    def generate_report(self, output_file='BENCHMARK_RESULTS.md'):
        """Generate markdown report"""
        print(f"\n📝 Generating report...")
        
        report = []
        report.append("# Sprint 4.2: Performance Benchmark Report\n")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**Server**: {self.base_url}\n\n")
        
        # Summary
        report.append("## 📊 Summary\n")
        
        total_requests = sum(r.get('iterations', 0) for r in self.results.values())
        total_successes = sum(r.get('successes', 0) for r in self.results.values())
        total_errors = sum(r.get('errors', 0) for r in self.results.values())
        
        report.append(f"- **Total Requests**: {total_requests}\n")
        report.append(f"- **Successful**: {total_successes} ✅\n")
        report.append(f"- **Failed**: {total_errors} ❌\n")
        report.append(f"- **Success Rate**: {(total_successes/total_requests*100):.1f}%\n\n")
        
        # Detailed results table
        report.append("## 📈 Detailed Results\n\n")
        report.append("| Endpoint | Method | Avg (ms) | Min (ms) | Max (ms) | Status |\n")
        report.append("|----------|--------|----------|----------|----------|--------|\n")
        
        for endpoint, result in sorted(self.results.items()):
            if 'avg_ms' in result:
                method = result['method']
                avg = result['avg_ms']
                min_ms = result['min_ms']
                max_ms = result['max_ms']
                errors = result['errors']
                
                # Status based on average time
                if avg < 100:
                    status = "🟢 Excellent"
                elif avg < 500:
                    status = "🟡 Good"
                elif avg < 1000:
                    status = "🟠 Acceptable"
                else:
                    status = "🔴 Slow"
                
                if errors > 0:
                    status = "❌ Errors"
                
                report.append(f"| {endpoint} | {method} | {avg:.0f} | {min_ms:.0f} | {max_ms:.0f} | {status} |\n")
            else:
                report.append(f"| {endpoint} | ? | N/A | N/A | N/A | ❌ Failed |\n")
        
        report.append("\n")
        
        # Performance targets
        report.append("## 🎯 Performance Targets\n\n")
        
        targets = {
            '/audit/dashboard-data': 500,
            '/audit/activity-trend': 200,
            '/audit/ip-statistics': 150,
            '/audit/quick-stats': 100,
            '/audit/recent-activity': 100,
            '/audit/export/preview': 1000,
            '/audit/export/csv': 2000,
            '/audit/export/json': 2000,
        }
        
        report.append("| Endpoint | Target (ms) | Actual (ms) | Status |\n")
        report.append("|----------|------------|------------|--------|\n")
        
        for endpoint, target in targets.items():
            if endpoint in self.results and 'avg_ms' in self.results[endpoint]:
                actual = self.results[endpoint]['avg_ms']
                meets = "✅ PASS" if actual <= target else "❌ FAIL"
                report.append(f"| {endpoint} | {target} | {actual:.0f} | {meets} |\n")
            else:
                report.append(f"| {endpoint} | {target} | N/A | ⏭️ SKIP |\n")
        
        report.append("\n")
        
        # Errors
        if self.errors:
            report.append("## ⚠️ Errors\n\n")
            for endpoint, error_list in self.errors.items():
                report.append(f"### {endpoint}\n")
                for error in error_list:
                    report.append(f"- {error}\n")
                report.append("\n")
        
        # Recommendations
        report.append("## 💡 Recommendations\n\n")
        
        slow_endpoints = [
            (ep, res['avg_ms']) for ep, res in self.results.items()
            if 'avg_ms' in res and res['avg_ms'] > 500
        ]
        
        if slow_endpoints:
            report.append("### Slow Endpoints (> 500ms)\n")
            for endpoint, avg in sorted(slow_endpoints, key=lambda x: x[1], reverse=True):
                report.append(f"- **{endpoint}**: {avg:.0f}ms\n")
                report.append(f"  - Consider implementing caching\n")
                report.append(f"  - Profile the analytics aggregation\n")
                report.append(f"  - Consider pagination for large datasets\n")
            report.append("\n")
        else:
            report.append("✅ All endpoints meet performance targets!\n\n")
        
        # Write report
        report_text = "".join(report)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"✅ Report saved to {output_file}\n")
        
        # Print to console
        print("=" * 70)
        print(report_text)
        print("=" * 70 + "\n")
        
        return output_file

def main():
    """Main execution"""
    runner = BenchmarkRunner()
    
    if runner.run_benchmarks():
        runner.generate_report()
    else:
        print("\n❌ Benchmark failed")
        print("\nTo start the server, run:")
        print("  python run.py")

if __name__ == '__main__':
    main()
