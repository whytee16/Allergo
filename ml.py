import math
from datetime import datetime

import numpy as np

from data.allergens import POLLEN_ALLERGENS

def get_pollen_concentration(date: datetime, allergen: str) -> float:
    """Синтетическая концентрация пыльцы (зёрен/м³) для данной даты и аллергена."""
    info = POLLEN_ALLERGENS.get(allergen)
    if not info:
        return 0.0
    peak = info["peak_month"]
    month_frac = date.month + date.day / 31
    distance = min(abs(month_frac - peak), 12 - abs(month_frac - peak))
    seasonal = max(0.0, 1 - distance / 3.0)
    base = 500 * info["danger"] * seasonal
    daily_noise = 1 + 0.3 * math.sin(date.timetuple().tm_yday)
    return round(max(base * daily_noise, 0), 1)


def estimate_threshold(entries: list, allergen: str):
    if len(entries) < 5:
        return None, None

    x, y = [], []
    for e in entries:
        dt = datetime.fromisoformat(e["logged_at"])
        conc = get_pollen_concentration(dt, allergen)
        x.append(conc)
        y.append(e["severity"])

    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    if x.std() == 0:
        return None, None

    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    if slope <= 0:
        return None, round(r2, 2)
    threshold = (3 - intercept) / slope
    return max(round(threshold), 0), round(r2, 2)
