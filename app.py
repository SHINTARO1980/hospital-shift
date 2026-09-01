import calendar
from datetime import date
import pandas as pd
from pulp import LpBinary, LpMinimize, LpProblem, LpStatus, LpVariable, lpSum
import streamlit as st

# ページ設定（スマホ・PC対応）
st.set_page_config(page_title="病院勤務表 自動作成ツール", layout="wide")

st.title("🏥 病院勤務表 自動作成ツール")

# 2026年 祝日定義
HOLIDAYS_2026 = [
    (1, 1), (1, 12), (2, 11), (2, 23), (3, 20), (4, 29),
    (5, 3), (5, 4), (5, 5), (5, 6), (7, 20), (8, 11),
    (9, 21), (9, 22), (9, 23), (10, 12), (11, 3), (11, 23)
]

STAFF_MEMBERS = ["濱本", "藤井", "横光", "橋本", "堀内", "三木", "前田", "園田"]

def parse_days(day_str):
    days = []
    if day_str:
        for d in str(day_str).replace("、", ",").split(","):
            d = d.strip()
            if d.isdigit():
                days.append(int(d))
    return days

# 入力エリア
st.header("1. 基本設定・希望休の入力")
col_year, col_month = st.columns(2)
with col_year:
    target_year = st.number_input("対象年", value=2026)
with col_month:
    target_month = st.number_input("対象月", min_value=1, max_value=12, value=10)

st.subheader("各スタッフの希望日（カンマ区切りで入力。例: 5, 12）")
off_days_dict = {}

cols = st.columns(2)
for idx, staff in enumerate(STAFF_MEMBERS):
    with cols[idx % 2]:
        input_str = st.text_input(f"{staff} の希望日", value="")
        off_days_dict[staff] = parse_days(input_str)

# 実行ボタン
if st.button("🚀 勤務表を自動生成する", type="primary"):
    roles = ["カF", "処①", "処②", "AF", "CFF", "OFF", "D", "A", "B"]
    _, num_days = calendar.monthrange(target_year, target_month)
    days = list(range(1, num_days + 1))

    prob = LpProblem("Hospital_Shift", LpMinimize)
    x = LpVariable.dicts("shift", [(s, d, r) for s in STAFF_MEMBERS for d in days for r in roles], cat=LpBinary)

    for d in days:
        dt = date(target_year, target_month, d)
        is_holiday = (target_month, d) in HOLIDAYS_2026 or dt.weekday() == 6

        if is_holiday:
            for s in STAFF_MEMBERS:
                for r in roles:
                    prob += x[(s, d, r)] == 0
            continue

        for s in STAFF_MEMBERS:
            if d in off_days_dict.get(s, []):
                for r in roles:
                    prob += x[(s, d, r)] == 0
            else:
                prob += lpSum([x[(s, d, r)] for r in roles]) == 1

        working_staff = [s for s in STAFF_MEMBERS if d not in off_days_dict.get(s, [])]
        for r in ["カF", "処①", "処②", "AF", "CFF"]:
            if len(working_staff) >= 5:
                prob += lpSum([x[(s, d, r)] for s in working_staff]) >= 1

    prob.solve()

    weekdays_jp = ["月", "火", "水", "木", "金", "土", "日"]
    schedule_data = []

    for d in days:
        dt = date(target_year, target_month, d)
        w_str = weekdays_jp[dt.weekday()]
        is_holiday = (target_month, d) in HOLIDAYS_2026 or dt.weekday() == 6
        
        row_dict = {"日付": f"{d}日({w_str})"}
        for s in STAFF_MEMBERS:
            if is_holiday:
                row_dict[s] = "休診"
            elif d in off_days_dict.get(s, []):
                row_dict[s] = "希望休"
            else:
                assigned = [r for r in roles if x[(s, d, r)].varValue == 1]
                row_dict[s] = assigned[0] if assigned else "-"
        schedule_data.append(row_dict)

    df_out = pd.DataFrame(schedule_data).set_index("日付")

    st.success("作成が完了しました！")
    st.dataframe(df_out, use_container_width=True)
