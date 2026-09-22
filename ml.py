"""
Оценка персонального порога чувствительности к пыльце.

В MVP нет доступа к реальной сети мониторинга пыльцы (KazNARU), поэтому
концентрация пыльцы на каждый день дневника моделируется синусоидой вокруг
пикового месяца аллергена (data/allergens.py) + случайный шум. Это тот же
принцип, что и в реальных данных сети — сезонная кривая с суточным разбросом.
На эту синтетическую концентрацию накладывается регрессия по реальным
записям пользователя (симптомы 1–5), чтобы найти уровень пыльцы, начиная
с которого у пользователя устойчиво появляются симптомы.
Замена на реальный API (Open-Meteo / KazNARU) — вопрос одной функции
(get_pollen_concentration), остальной пайплайн не меняется.
"""
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
    seasonal = max(0.0, 1 - distance / 3.0)  # спад до 0 за ~3 месяца от пика
    base = 500 * info["danger"] * seasonal
    daily_noise = 1 + 0.3 * math.sin(date.timetuple().tm_yday)
    return round(max(base * daily_noise, 0), 1)


def estimate_threshold(entries: list, allergen: str):
    """
    entries: список словарей из db.get_all_entries(), уже отфильтрованных по allergen.
    Возвращает (threshold, r2) или (None, None), если данных недостаточно.
    """
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

    # Порог = концентрация, при которой прогнозируемая тяжесть симптомов достигает 3/5
    slope, intercept = model.coef_[0], model.intercept_
    if slope <= 0:
        return None, r2
    threshold = (3 - intercept) / slope
    return max(round(threshold), 0), round(r2, 2)
