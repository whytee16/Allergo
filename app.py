import streamlit as st
import pandas as pd
from datetime import datetime, date, time

import db
from data.allergens import POLLEN_ALLERGENS, HOUSEHOLD_ALLERGENS, FOOD_ALLERGENS, ALL_ALLERGEN_NAMES
from data.food_cross_reactions import CROSS_REACTIONS
from data.symptoms import SYMPTOMS_BY_ZONE, EMERGENCY_ZONE
from ml import estimate_threshold, get_pollen_concentration

st.set_page_config(page_title="Алерго — дневник аллергика", page_icon="🌿", layout="wide")
db.init_db()

# ---------- сессия: подписка (демо-переключатель для питча) ----------
if "premium" not in st.session_state:
    st.session_state.premium = db.get_setting("premium", "0") == "1"

with st.sidebar:
    st.markdown("## 🌿 Алерго")
    st.caption("Персональный дневник для аллергиков · VentureHack 2026 · MedTech")
    page = st.radio(
        "Раздел",
        ["📔 Дневник", "🧬 Мои аллергены", "🍽️ Перекрёстная аллергия", "📊 Аналитика", "💳 Подписка"],
        label_visibility="collapsed",
    )
    st.divider()
    plan = "Premium ✨" if st.session_state.premium else "Free"
    st.markdown(f"**Тариф:** {plan}")

MY_ALLERGENS_KEY = "my_allergens"


def get_my_allergens():
    raw = db.get_setting(MY_ALLERGENS_KEY, "")
    return [a for a in raw.split("|") if a]


def set_my_allergens(allergens):
    db.set_setting(MY_ALLERGENS_KEY, "|".join(allergens))


# =========================================================
# 📔 ДНЕВНИК
# =========================================================
if page == "📔 Дневник":
    st.title("Дневник симптомов")
    st.caption("Фиксируйте, что случилось, когда и на что — это основа персональных рекомендаций.")

    with st.form("new_entry", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            entry_date = st.date_input("Дата", value=date.today())
            entry_time = st.time_input("Время", value=datetime.now().time().replace(second=0, microsecond=0))
            zone = st.selectbox("Зона тела", list(SYMPTOMS_BY_ZONE.keys()))
        with c2:
            symptom = st.selectbox("Симптом", SYMPTOMS_BY_ZONE[zone])
            severity = st.slider("Тяжесть (1 — лёгкая, 5 — тяжёлая)", 1, 5, 2)
            allergen = st.selectbox("Подозреваемый аллерген (опционально)", ["Не знаю"] + ALL_ALLERGEN_NAMES)
        note = st.text_input("Заметка (необязательно)", placeholder="например: ела дыню, было ветрено")

        submitted = st.form_submit_button("Добавить запись", type="primary")
        if submitted:
            if zone == EMERGENCY_ZONE:
                severity = 5
                st.warning("Отмечена острая реакция. При анафилаксии или отёке Квинке — немедленно звоните 103.")
            logged_at = datetime.combine(entry_date, entry_time).isoformat(timespec="minutes")
            db.add_entry(zone, symptom, severity, None if allergen == "Не знаю" else allergen, note, logged_at)
            st.success("Запись добавлена.")

    st.divider()
    entries = db.get_all_entries()
    if not entries:
        st.info("Пока нет записей — добавьте первую выше.")
    else:
        df = pd.DataFrame(entries)
        show = df[["logged_at", "body_zone", "symptom", "severity", "allergen", "note"]].rename(
            columns={"logged_at": "Когда", "body_zone": "Зона", "symptom": "Симптом",
                     "severity": "Тяжесть", "allergen": "Аллерген", "note": "Заметка"}
        )
        st.dataframe(show, use_container_width=True, hide_index=True)

        with st.expander("Удалить запись"):
            to_delete = st.selectbox("Выберите ID для удаления", df["id"].tolist())
            if st.button("Удалить"):
                db.delete_entry(int(to_delete))
                st.rerun()

# =========================================================
# 🧬 МОИ АЛЛЕРГЕНЫ
# =========================================================
elif page == "🧬 Мои аллергены":
    st.title("Мои аллергены")
    st.caption("Отметьте подтверждённые или подозреваемые аллергены — это включит персональные уведомления.")

    current = get_my_allergens()

    st.subheader("Пыльцевые")
    pollen_selected = st.multiselect("Пыльца", list(POLLEN_ALLERGENS.keys()),
                                      default=[a for a in current if a in POLLEN_ALLERGENS])
    st.subheader("Бытовые")
    household_selected = st.multiselect("Бытовые аллергены", list(HOUSEHOLD_ALLERGENS.keys()),
                                         default=[a for a in current if a in HOUSEHOLD_ALLERGENS])
    st.subheader("Пищевые")
    food_selected = st.multiselect("Пищевые аллергены", list(FOOD_ALLERGENS.keys()),
                                    default=[a for a in current if a in FOOD_ALLERGENS])

    if st.button("Сохранить", type="primary"):
        set_my_allergens(pollen_selected + household_selected + food_selected)
        st.success("Сохранено.")

    st.divider()
    st.subheader("Календарь пыления (по месяцам)")
    cal_rows = []
    for name, info in POLLEN_ALLERGENS.items():
        cal_rows.append({"Аллерген": name, "Сезон": info["season"], "Пик": info["peak_month"],
                          "Опасность": "🔴" * info["danger"], "Регион": info["region"]})
    st.dataframe(pd.DataFrame(cal_rows), use_container_width=True, hide_index=True)

# =========================================================
# 🍽️ ПЕРЕКРЁСТНАЯ АЛЛЕРГИЯ
# =========================================================
elif page == "🍽️ Перекрёстная аллергия":
    st.title("Навигатор перекрёстной пищевой аллергии")
    st.caption("Если у вас поллиноз, часть продуктов может вызывать реакцию из-за похожих белков.")

    my_allergens = [a for a in get_my_allergens() if a in CROSS_REACTIONS]
    options = list(CROSS_REACTIONS.keys())
    default_allergen = my_allergens[0] if my_allergens else options[0]
    allergen = st.selectbox("Ваш аллерген", options, index=options.index(default_allergen))

    current_month = date.today().month
    peak = POLLEN_ALLERGENS.get(allergen, {}).get("peak_month")
    if peak and abs(current_month - peak) <= 1:
        st.warning(f"⚠️ Сейчас активен сезон «{allergen}» — будьте особенно внимательны к продуктам ниже.")

    rows = CROSS_REACTIONS[allergen]
    df = pd.DataFrame(rows, columns=["Продукт", "Категория", "Частота реакций", "Опасность", "Примечание"])
    df["Опасность"] = df["Опасность"].apply(lambda d: "🔴" * d)

    if st.session_state.premium:
        st.dataframe(df.sort_values("Продукт"), use_container_width=True, hide_index=True)
    else:
        st.dataframe(df.head(4), use_container_width=True, hide_index=True)
        st.info(f"Free-тариф показывает 4 из {len(df)} продуктов. "
                "Оформите Premium, чтобы видеть полный список по каждому аллергену.")

    st.divider()
    st.subheader("🔍 Проверить конкретный продукт")
    product_query = st.text_input("Название продукта")
    if product_query:
        hits = []
        for alg, rows in CROSS_REACTIONS.items():
            for r in rows:
                if product_query.strip().lower() in r[0].lower():
                    hits.append((alg, *r))
        if hits:
            hdf = pd.DataFrame(hits, columns=["Аллерген", "Продукт", "Категория", "Частота", "Опасность", "Примечание"])
            st.dataframe(hdf, use_container_width=True, hide_index=True)
        else:
            st.write("Перекрёстных реакций для этого продукта в базе не найдено.")

# =========================================================
# 📊 АНАЛИТИКА
# =========================================================
elif page == "📊 Аналитика":
    st.title("Аналитика")
    entries = db.get_all_entries()
    if not entries:
        st.info("Добавьте записи в дневник, чтобы увидеть аналитику.")
    else:
        df = pd.DataFrame(entries)
        df["logged_at"] = pd.to_datetime(df["logged_at"])
        df["date"] = df["logged_at"].dt.date

        c1, c2, c3 = st.columns(3)
        c1.metric("Всего записей", len(df))
        c2.metric("Средняя тяжесть", round(df["severity"].mean(), 1))
        c3.metric("Дней с симптомами", df["date"].nunique())

        st.subheader("Тяжесть симптомов по дням")
        daily = df.groupby("date")["severity"].mean()
        st.line_chart(daily)

        st.subheader("Частота по зонам тела")
        st.bar_chart(df["body_zone"].value_counts())

        st.divider()
        st.subheader("🎯 Персональный порог чувствительности")
        if not st.session_state.premium:
            st.info("Расчёт персонального порога доступен в Premium.")
        else:
            allergen_options = [a for a in df["allergen"].dropna().unique() if a in POLLEN_ALLERGENS]
            if not allergen_options:
                st.write("Отметьте пыльцевой аллерген у ваших записей в дневнике, чтобы рассчитать порог.")
            else:
                chosen = st.selectbox("Аллерген для расчёта", allergen_options)
                subset = [e for e in entries if e["allergen"] == chosen]
                threshold, r2 = estimate_threshold(subset, chosen)
                if threshold is None:
                    st.write("Недостаточно данных (нужно минимум 5 записей с этим аллергеном) "
                             "или связь пыльца/симптомы пока не выявлена.")
                else:
                    today_conc = get_pollen_concentration(datetime.now(), chosen)
                    st.metric(f"Ваш порог для «{chosen}»", f"{threshold} зёрен/м³", help=f"R² модели: {r2}")
                    st.metric("Оценка концентрации сегодня", f"{today_conc} зёрен/м³")
                    if today_conc >= threshold:
                        st.error("⚠️ Сегодняшняя концентрация выше вашего порога — вероятны симптомы. "
                                 "Рассмотрите приём антигистаминного заранее.")
                    else:
                        st.success("Концентрация ниже вашего обычного порога.")

# =========================================================
# 💳 ПОДПИСКА
# =========================================================
elif page == "💳 Подписка":
    st.title("Подписка")
    st.caption("Демо переключателя тарифа — для питча и демонстрации бизнес-модели жюри.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Free — 0 ₸")
        st.markdown(
            "- Дневник симптомов без ограничений\n"
            "- Календарь пыления\n"
            "- Перекрёстная аллергия: превью (4 продукта на аллерген)\n"
        )
    with col2:
        st.subheader("Premium — 990 ₸/мес")
        st.markdown(
            "- Полная база перекрёстных аллергенов\n"
            "- Персональный порог чувствительности (ML)\n"
            "- Расширенная аналитика и экспорт\n"
            "- Приоритетные уведомления в сезон\n"
        )

    st.divider()
    toggle = st.toggle("Включить Premium (демо-режим для жюри)", value=st.session_state.premium)
    if toggle != st.session_state.premium:
        st.session_state.premium = toggle
        db.set_setting("premium", "1" if toggle else "0")
        st.rerun()

    st.divider()
    st.subheader("Другие источники дохода")
    st.markdown(
        "- **Партнёрство с аптеками** — реферальные ссылки на антигистаминные препараты (комиссия с продаж)\n"
        "- **B2B API** — доступ к агрегированным (обезличенным) данным для страховых компаний и телемед-платформ\n"
        "- **Корпоративные подписки** — для клиник и аллергологов, ведущих пациентов удалённо\n"
    )
