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
    (1, 1),
    (1, 12),
    (2, 11),
    (2, 23),
    (3, 20),
    (4, 29),
    (5, 3),
    (5, 4),
    (5, 5),
    (5, 6),
    (7, 20),
    (8, 11),
    (9, 21),
    (9, 22),
    (9, 23),
    (10, 12),
    (11, 3),
    (11, 23),
]

STAFF_MEMBERS = ["濱本", "藤井", "横光", "橋本", "堀内", "三木", "前田", "園田"]
ROLES = ["カF", "処①", "処②", "AF", "CFF", "OFF", "D", "A", "B"]

# プルダウン選択肢および合計計算の対象シフト
ROLE_OPTIONS = ROLES + ["希望休", "休診", "-"]


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
  _, num_days = calendar.monthrange(target_year, target_month)
  days = list(range(1, num_days + 1))

  prob = LpProblem("Hospital_Shift", LpMinimize)
  x = LpVariable.dicts(
      "shift",
      [(s, d, r)
       for s in STAFF_MEMBERS
       for d in days
       for r in ROLES],
      cat=LpBinary,
  )

  for d in days:
    dt = date(target_year, target_month, d)
    is_holiday = (target_month, d) in HOLIDAYS_2026 or dt.weekday() == 6

    if is_holiday:
      for s in STAFF_MEMBERS:
        for r in ROLES:
          prob += x[(s, d, r)] == 0
      continue

    for s in STAFF_MEMBERS:
      if d in off_days_dict.get(s, []):
        for r in ROLES:
          prob += x[(s, d, r)] == 0
      else:
        prob += lpSum([x[(s, d, r)] for r in ROLES]) == 1

    working_staff = [
        s for s in STAFF_MEMBERS if d not in off_days_dict.get(s, [])
    ]
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
        assigned = [r for r in ROLES if x[(s, d, r)].varValue == 1]
        row_dict[s] = assigned[0] if assigned else "-"
    schedule_data.append(row_dict)

  df_out = pd.DataFrame(schedule_data).set_index("日付")
  st.session_state["schedule_df"] = df_out
  st.success("作成が完了しました！下の表で直接変更・調整ができます。")

# 勤務表が生成されている場合は編集画面および合計を表示
if "schedule_df" in st.session_state:
  st.header("2. 勤務表の確認・手動調整")
  st.info(
      "💡"
      " 変更したいセルをタップ（ダブルタップ）するとプルダウンで勤務を変更できます。"
  )

  # 全スタッフ列にプルダウン選択を設定
  column_config = {
      staff: st.column_config.SelectboxColumn(
          staff,
          options=ROLE_OPTIONS,
          required=True,
      )
      for staff in STAFF_MEMBERS
  }

  # インタラクティブ編集テーブル
  edited_df = st.data_editor(
      st.session_state["schedule_df"],
      column_config=column_config,
      use_container_width=True,
      key="shift_editor",
  )

  # --- 月間合計集計機能（縦：シフト、横：スタッフ順） ---
  st.header("3. 各スタッフの月間シフト集計")

  summary_roles = ROLES + ["希望休"]
  summary_data = {staff: [] for staff in STAFF_MEMBERS}

  for staff in STAFF_MEMBERS:
    staff_counts = edited_df[staff].value_counts()
    for role in summary_roles:
      summary_data[staff].append(int(staff_counts.get(role, 0)))

  df_summary = pd.DataFrame(
      summary_data, index=pd.Index(summary_roles, name="シフト")
  )
  st.dataframe(df_summary, use_container_width=True)

  # CSVダウンロード機能
  csv = edited_df.to_csv().encode("utf-8-sig")
  st.download_button(
      label="📥 調整後の勤務表（Excel用）をダウンロード",
      data=csv,
      file_name=f"勤務表_{target_year}年{target_month}月.csv",
      mime="text/csv",
  )
