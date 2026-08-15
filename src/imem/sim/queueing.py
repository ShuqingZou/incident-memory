def latency_from_utilization(base_ms, u):
    u = min(u, 0.95)
    return base_ms * (1 / (1 - u))


if __name__ == "__main__":
    for u in [0.1, 0.3, 0.5, 0.7, 0.9, 0.95]:
        print(u, "->", round(latency_from_utilization(60, u)), "ms")