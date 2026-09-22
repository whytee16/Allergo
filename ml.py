import math
from datetime import datetime

import numpy as np
from sklearn.linear_model import LinearRegression

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

    X = np.array(x).reshape(-1, 1)
    Y = np.array(y)
    if X.std() == 0:
        return None, None

    model = LinearRegression().fit(X, Y)
    r2 = model.score(X, Y)

    slope, intercept = model.coef_[0], model.intercept_
    if slope <= 0:
        return None, r2
    threshold = (3 - intercept) / slope
    return max(round(threshold), 0), round(r2, 2)
