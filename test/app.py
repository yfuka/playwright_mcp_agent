import streamlit as st
import pandas as pd

st.set_page_config(page_title="MCP Agent Test App", page_icon="🧪")

st.title("🧪 MCP Agent Test App (TODO)")

if "tasks" not in st.session_state:
    st.session_state.tasks = []

with st.form("add_task"):
    title = st.text_input("タスク名", key="task_title")
    priority = st.selectbox("優先度", ["高", "中", "低"], key="task_priority")
    submitted = st.form_submit_button("追加")

    if submitted and title:
        st.session_state.tasks.append(
            {"title": title, "priority": priority, "done": False}
        )
        st.success(f"タスクを追加しました: {title}")

st.divider()

st.subheader("タスク一覧")

if st.session_state.tasks:
    # フィルタ
    selected_priority = st.selectbox(
        "表示する優先度",
        ["すべて", "高", "中", "低"],
        key="filter_priority",
    )

    df = pd.DataFrame(st.session_state.tasks)

    if selected_priority != "すべて":
        df = df[df["priority"] == selected_priority]

    # チェックボックスで完了にできるようにする
    for i, row in df.reset_index().iterrows():
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        with col1:
            st.write(row["title"])
        with col2:
            st.write(row["priority"])
        with col3:
            done = st.checkbox("完了", value=row["done"], key=f"done_{row['index']}")
        with col4:
            if done != st.session_state.tasks[row["index"]]["done"]:
                st.session_state.tasks[row["index"]]["done"] = done

    remaining = sum(1 for t in st.session_state.tasks if not t["done"])
    st.info(f"未完了タスク数: {remaining}")
else:
    st.write("まだタスクがありません。上のフォームから追加してください。")
