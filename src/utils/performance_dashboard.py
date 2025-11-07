"""
Performance Dashboard for Amazon Recommender System
Monitors system performance, user engagement, and recommendation quality
"""

import time
import psutil
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import logging

class PerformanceDashboard:
    """
    Real-time performance monitoring and analytics dashboard
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.metrics = defaultdict(deque)
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times = deque(maxlen=1000)
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)
        
        # Recommendation quality metrics
        self.recommendation_stats = {
            'total_generated': 0,
            'user_clicks': 0,
            'conversions': 0,
            'avg_relevance_score': 0.0
        }
        
        # Search performance metrics
        self.search_stats = {
            'total_queries': 0,
            'avg_response_time': 0.0,
            'zero_results_count': 0,
            'popular_queries': defaultdict(int)
        }
        
        self.logger = logging.getLogger(__name__)
    
    def log_request(self, endpoint, response_time, status_code=200):
        """Log API request metrics"""
        self.request_count += 1
        self.response_times.append(response_time)
        
        if status_code >= 400:
            self.error_count += 1
        
        # Store endpoint-specific metrics
        self.metrics[f"{endpoint}_response_time"].append(response_time)
        self.metrics[f"{endpoint}_requests"].append(time.time())
        
        self.logger.info(f"Request: {endpoint}, Time: {response_time:.3f}s, Status: {status_code}")
    
    def log_recommendation(self, user_id, item_ids, relevance_scores=None):
        """Log recommendation generation"""
        self.recommendation_stats['total_generated'] += 1
        
        if relevance_scores:
            avg_relevance = np.mean(relevance_scores)
            self.recommendation_stats['avg_relevance_score'] = (
                (self.recommendation_stats['avg_relevance_score'] * 
                 (self.recommendation_stats['total_generated'] - 1) + avg_relevance) /
                self.recommendation_stats['total_generated']
            )
        
        self.logger.info(f"Recommendations generated for user {user_id}: {len(item_ids)} items")
    
    def log_search(self, query, response_time, result_count):
        """Log search query metrics"""
        self.search_stats['total_queries'] += 1
        self.search_stats['popular_queries'][query.lower()] += 1
        
        # Update average response time
        total_time = (self.search_stats['avg_response_time'] * 
                     (self.search_stats['total_queries'] - 1) + response_time)
        self.search_stats['avg_response_time'] = total_time / self.search_stats['total_queries']
        
        if result_count == 0:
            self.search_stats['zero_results_count'] += 1
        
        self.logger.info(f"Search: '{query}' - {result_count} results in {response_time:.3f}s")
    
    def log_user_interaction(self, user_id, item_id, interaction_type):
        """Log user interactions (click, purchase, etc.)"""
        if interaction_type == 'click':
            self.recommendation_stats['user_clicks'] += 1
        elif interaction_type == 'purchase':
            self.recommendation_stats['conversions'] += 1
        
        self.logger.info(f"User {user_id} {interaction_type} on item {item_id}")
    
    def update_system_metrics(self):
        """Update system resource metrics"""
        # Memory usage
        memory = psutil.virtual_memory()
        self.memory_usage.append(memory.percent)
        
        # CPU usage
        cpu = psutil.cpu_percent(interval=1)
        self.cpu_usage.append(cpu)
        
        self.logger.debug(f"System metrics - Memory: {memory.percent:.1f}%, CPU: {cpu:.1f}%")
    
    def get_dashboard_data(self):
        """Get comprehensive dashboard data"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # Calculate rates
        requests_per_minute = (self.request_count / uptime) * 60 if uptime > 0 else 0
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        
        # Response time statistics
        response_times_list = list(self.response_times)
        avg_response_time = np.mean(response_times_list) if response_times_list else 0
        p95_response_time = np.percentile(response_times_list, 95) if response_times_list else 0
        
        # Memory and CPU averages
        avg_memory = np.mean(list(self.memory_usage)) if self.memory_usage else 0
        avg_cpu = np.mean(list(self.cpu_usage)) if self.cpu_usage else 0
        
        # Top search queries
        top_queries = sorted(
            self.search_stats['popular_queries'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        dashboard_data = {
            'system_overview': {
                'uptime_hours': uptime / 3600,
                'total_requests': self.request_count,
                'requests_per_minute': round(requests_per_minute, 2),
                'error_rate_percent': round(error_rate, 2),
                'avg_response_time_ms': round(avg_response_time * 1000, 2),
                'p95_response_time_ms': round(p95_response_time * 1000, 2)
            },
            'resource_usage': {
                'memory_usage_percent': round(avg_memory, 1),
                'cpu_usage_percent': round(avg_cpu, 1),
                'memory_history': list(self.memory_usage),
                'cpu_history': list(self.cpu_usage)
            },
            'recommendation_metrics': {
                'total_recommendations': self.recommendation_stats['total_generated'],
                'user_clicks': self.recommendation_stats['user_clicks'],
                'conversions': self.recommendation_stats['conversions'],
                'click_through_rate': (
                    (self.recommendation_stats['user_clicks'] / 
                     self.recommendation_stats['total_generated'] * 100)
                    if self.recommendation_stats['total_generated'] > 0 else 0
                ),
                'conversion_rate': (
                    (self.recommendation_stats['conversions'] / 
                     self.recommendation_stats['user_clicks'] * 100)
                    if self.recommendation_stats['user_clicks'] > 0 else 0
                ),
                'avg_relevance_score': round(self.recommendation_stats['avg_relevance_score'], 3)
            },
            'search_metrics': {
                'total_searches': self.search_stats['total_queries'],
                'avg_search_time_ms': round(self.search_stats['avg_response_time'] * 1000, 2),
                'zero_results_rate': (
                    (self.search_stats['zero_results_count'] / 
                     self.search_stats['total_queries'] * 100)
                    if self.search_stats['total_queries'] > 0 else 0
                ),
                'top_queries': top_queries
            },
            'performance_trends': {
                'response_times': list(self.response_times)[-50:],  # Last 50 requests
                'requests_over_time': self._get_requests_over_time(),
                'errors_over_time': self._get_errors_over_time()
            },
            'health_status': self._get_health_status()
        }
        
        return dashboard_data
    
    def _get_requests_over_time(self):
        """Get request count over time (last hour)"""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Count requests in 5-minute buckets
        buckets = defaultdict(int)
        for endpoint in self.metrics:
            if endpoint.endswith('_requests'):
                for timestamp in self.metrics[endpoint]:
                    if timestamp >= hour_ago:
                        bucket = int((timestamp - hour_ago) // 300)  # 5-minute buckets
                        buckets[bucket] += 1
        
        return dict(buckets)
    
    def _get_errors_over_time(self):
        """Get error count over time"""
        # This would require storing error timestamps
        # For now, return a simple metric
        return {'last_hour': self.error_count}
    
    def _get_health_status(self):
        """Determine overall system health"""
        health_score = 100
        status = "Healthy"
        issues = []
        
        # Check error rate
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        if error_rate > 5:
            health_score -= 20
            issues.append(f"High error rate: {error_rate:.1f}%")
        
        # Check response time
        if self.response_times:
            avg_time = np.mean(list(self.response_times))
            if avg_time > 1.0:  # > 1 second
                health_score -= 15
                issues.append(f"Slow response time: {avg_time:.2f}s")
        
        # Check memory usage
        if self.memory_usage:
            current_memory = self.memory_usage[-1]
            if current_memory > 80:
                health_score -= 20
                issues.append(f"High memory usage: {current_memory:.1f}%")
        
        # Check CPU usage
        if self.cpu_usage:
            current_cpu = self.cpu_usage[-1]
            if current_cpu > 80:
                health_score -= 15
                issues.append(f"High CPU usage: {current_cpu:.1f}%")
        
        # Determine status
        if health_score >= 90:
            status = "Healthy"
        elif health_score >= 70:
            status = "Warning"
        else:
            status = "Critical"
        
        return {
            'score': health_score,
            'status': status,
            'issues': issues
        }
    
    def export_metrics(self, filepath=None):
        """Export metrics to JSON file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"metrics_export_{timestamp}.json"
        
        data = self.get_dashboard_data()
        data['export_timestamp'] = datetime.now().isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Metrics exported to {filepath}")
        return filepath
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        self.metrics.clear()
        self.request_count = 0
        self.error_count = 0
        self.response_times.clear()
        self.memory_usage.clear()
        self.cpu_usage.clear()
        self.recommendation_stats = {
            'total_generated': 0,
            'user_clicks': 0,
            'conversions': 0,
            'avg_relevance_score': 0.0
        }
        self.search_stats = {
            'total_queries': 0,
            'avg_response_time': 0.0,
            'zero_results_count': 0,
            'popular_queries': defaultdict(int)
        }
        self.start_time = time.time()
        
        self.logger.info("Metrics reset successfully")

# Global dashboard instance
dashboard = PerformanceDashboard()

def get_dashboard():
    """Get the global dashboard instance"""
    return dashboard

# Decorator for monitoring function performance
def monitor_performance(endpoint_name):
    """Decorator to monitor function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                dashboard.log_request(endpoint_name, end_time - start_time, 200)
                return result
            except Exception as e:
                end_time = time.time()
                dashboard.log_request(endpoint_name, end_time - start_time, 500)
                raise e
        return wrapper
    return decorator

if __name__ == "__main__":
    # Example usage
    dashboard = PerformanceDashboard()
    
    # Simulate some metrics
    dashboard.log_request("/api/search", 0.125, 200)
    dashboard.log_request("/api/recommendations", 0.089, 200)
    dashboard.log_search("wireless headphones", 0.095, 25)
    dashboard.log_recommendation("user123", ["item1", "item2", "item3"], [0.9, 0.8, 0.7])
    dashboard.update_system_metrics()
    
    # Get dashboard data
    data = dashboard.get_dashboard_data()
    print(json.dumps(data, indent=2))