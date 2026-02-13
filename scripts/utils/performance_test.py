"""
API 性能测试脚本

对比新旧 API 的性能，使用 Locust 进行负载测试
"""

import asyncio
import time
import statistics
from datetime import datetime
import httpx

# 测试配置
BASE_URL = "http://localhost:28000"
OLD_API_PREFIX = "/api/v1"  # 旧版 API
NEW_API_PREFIX = "/api/v1"  # 新版 ORM API

# 测试用例
TEST_SCENARIOS = [
    {
        "name": "获取技能列表",
        "endpoint": "/skills",
        "method": "GET",
        "description": "分页获取技能列表",
        "weight": 3  # 频率权重
    },
    {
        "name": "获取待审核技能",
        "endpoint": "/pending",
        "method": "GET",
        "description": "管理员获取待审核列表",
        "weight": 2
    },
    {
        "name": "获取统计信息",
        "endpoint": "/stats",
        "method": "GET",
        "description": "获取总体统计数据",
        "weight": 1
    },
    {
        "name": "热门技能",
        "endpoint": "/stats/hot",
        "method": "GET",
        "description": "获取热门技能统计",
        "weight": 2
    },
    {
        "name": "用户登录",
        "endpoint": "/auth/login",
        "method": "POST",
        "description": "用户登录认证",
        "weight": 1
    },
]


async def test_endpoint(client: httpx.AsyncClient, endpoint: str, method: str, data: dict = None):
    """测试单个端点性能"""
    url = f"{BASE_URL}{endpoint}"

    start_time = time.time()
    try:
        if method == "GET":
            response = await client.get(url, params=data)
        elif method == "POST":
            response = await client.post(url, json=data)

        elapsed = time.time() - start_time
        success = response.status_code == 200

        return {
            "endpoint": endpoint,
            "method": method,
            "success": success,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed * 1000, 2),
            "response_size": len(response.content) if success else 0
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "endpoint": endpoint,
            "method": method,
            "success": False,
            "error": str(e),
            "elapsed_ms": round(elapsed * 1000, 2)
        }


async def run_performance_test(rounds: int = 10, concurrent_users: int = 10):
    """运行性能测试"""
    print(f"\n{'='*60}")
    print(f"性能测试 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"配置: {rounds} 轮次, {concurrent_users} 并发用户")
    print(f"{'='*60}")

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for round_num in range(1, rounds + 1):
            print(f"\n第 {round_num} 轮:")
            round_results = []

            # 并发执行所有测试场景
            tasks = []
            for scenario in TEST_SCENARIOS:
                for _ in range(concurrent_users):
                    task = test_endpoint(
                        client,
                        scenario["endpoint"],
                        scenario["method"],
                        {"page": 1, "per_page": 20} if scenario["method"] == "GET" and "page" in scenario["endpoint"] else None
                    )
                    tasks.append(task)

            # 执行本轮测试
            round_start = time.time()
            round_responses = await asyncio.gather(*tasks)
            round_elapsed = time.time() - round_start

            # 统计本轮结果
            success_count = sum(1 for r in round_responses if r["success"])
            avg_response_time = statistics.mean([r["elapsed_ms"] for r in round_responses if r["success"]])

            print(f"  完成: {round_elapsed:.2f}秒")
            print(f"  成功率: {success_count}/{len(round_responses)} ({success_count/len(round_responses)*100:.1f}%)")
            print(f"  平均响应时间: {avg_response_time:.0f}ms")

            round_results.extend(round_responses)
            results.extend(round_results)

            # 避免请求过快
            await asyncio.sleep(0.5)

    # 生成报告
    generate_performance_report(results, rounds, concurrent_users)
    print(f"\n{'='*60}")
    print("性能测试完成！报告已生成")


def generate_performance_report(results: list, rounds: int, concurrent: int):
    """生成性能测试报告"""
    # 按端点统计
    endpoint_stats = {}
    for result in results:
        endpoint = result["endpoint"]
        if endpoint not in endpoint_stats:
            endpoint_stats[endpoint] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "total_time": 0,
                "avg_time": 0,
                "max_time": 0,
                "min_time": 0
            }

        stats = endpoint_stats[endpoint]
        stats["total"] += 1
        if result["success"]:
            stats["success"] += 1
            stats["total_time"] += result["elapsed_ms"]
            stats["avg_time"] = stats["total_time"] / stats["success"]
            if result["elapsed_ms"] > stats["max_time"]:
                stats["max_time"] = result["elapsed_ms"]
            if result["elapsed_ms"] < stats["min_time"] or stats["min_time"] == 0:
                stats["min_time"] = result["elapsed_ms"]
        else:
            stats["failed"] += 1

    # 打印详细报告
    print(f"\n{'='*60}")
    print("=" * 80)
    print("性能测试报告")
    print("=" * 80)
    print(f"\n测试配置:")
    print(f"  总轮次: {rounds}")
    print(f"  并发用户: {concurrent_users}")
    print(f"  测试端点数: {len(TEST_SCENARIOS)}")
    print(f"  总请求数: {len(results)}")

    print(f"\n端点性能统计:")
    print("-" * 80)

    for endpoint, stats in sorted(endpoint_stats.items(), key=lambda x: x[0]):
        success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"\n{endpoint}:")
        print(f"  总请求: {stats['total']}")
        print(f"  成功: {stats['success']}")
        print(f"  失败: {stats['failed']}")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  平均响应时间: {stats['avg_time']:.0f}ms")
        print(f"  最大响应时间: {stats['max_time']:.0f}ms")
        print(f"  最小响应时间: {stats['min_time']:.0f}ms")

    # 性能建议
    print(f"\n{'-'*80}")
    print("性能建议:")
    for endpoint, stats in sorted(endpoint_stats.items(), key=lambda x: x[0]):
        if stats["avg_time"] > 500:
            print(f"  ⚠️  {endpoint}: 平均响应时间较慢 ({stats['avg_time']:.0f}ms)，建议优化查询或添加缓存")
        if stats["success"] < 90:
            print(f"  ⚠️  {endpoint}: 成功率较低 ({stats['success']}/{stats['total']})，建议检查错误处理")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    import sys

    # 解析参数
    rounds = 10
    concurrent = 10

    if len(sys.argv) > 1:
        try:
            rounds = int(sys.argv[1])
        except ValueError:
            pass

    if len(sys.argv) > 2:
        try:
            concurrent = int(sys.argv[2])
        except ValueError:
            pass

    asyncio.run(run_performance_test(rounds, concurrent))
