"""Baseline traffic shape: what a normal day looks like."""
import math

def diurnal(hour: float) -> float:
    """Traffic multiplier by hour of day. 1.0 is roughly average."""
    return (
        0.55
            + 0.45 * math.exp(-((hour - 14) ** 2) / 40)
            + 0.25 * math.exp(-((hour - 20) ** 2) / 12)
    )

if __name__ == "__main__":
    for hour in range(24):
        print(f"{hour:2d}h  {diurnal(hour):.2f}  " + "#" * int(diurnal(hour) * 40))