import pandas as pd
import streamlit as st
import re

# --- 학교 일과 시간표 세팅 ---
CLASS_TIMES = {
    1: "08:50~09:40",
    2: "09:50~10:40",
    3: "10:50~11:40",
    4: "11:50~12:40",
    5: "13:40~14:30",
    6: "14:40~15:30",
    7: "15:40~16:30"
}

# --- 1. AI 엑셀 구조 자동 탐지 함수 ---
@st.cache_data
def find_excel_structure(df_raw):
    day_mapping = {'월':[], '화':[], '수':[], '목':[], '금':[]}
    day_row_idx = -1
    
    for i in range(min(15, len(df_raw))):
        row_str = "".join(df_raw.iloc[i].fillna("").astype(str))
        if '월' in row_str and '화' in row_str:
            day_row_idx = i
            break
            
    if day_row_idx == -1:
        return None, -1, "요일(월,화,수...) 행을 찾을 수 없습니다."

    current_day = None
    for col_idx in range(len(df_raw.columns)):
        val = str(df_raw.iloc[day_row_idx, col_idx]).strip().replace('요일', '')
        for day_key in day_mapping.keys():
            if val == day_key:
                current_day = day_key
                break
        if current_day is not None:
            day_mapping[current_day].append(col_idx)
            
    period_row_idx = day_row_idx + 1
    cleaned_mapping = {}
    for day, cols in day_mapping.items():
        valid_cols = []
        for c in cols:
            if period_row_idx < len(df_raw):
                val = str(df_raw.iloc[period_row_idx, c]).strip()
                if val.isdigit() or val.replace('교시','').isdigit():
                    valid_cols.append(c)
        cleaned_mapping[day] = valid_cols if valid_cols else cols

    cleaned_mapping = {k: v for k, v in cleaned_mapping.items() if len(v) > 0}
    return cleaned_mapping, day_row_idx, "성공"

# --- 2. 데이터 파싱(변환) 함수 ---
@st.cache_data
def parse_smart_schedule(df_raw, start_row, teacher_col, rows_per_teacher, day_mapping, data_type):
    parsed_data = []
    for i in range(start_row, len(df_raw), rows_per_teacher):
        if i >= len(df_raw): break
        
        teacher_name = str(df_raw.iloc[i, teacher_col]).strip()
        if pd.isna(teacher_name) or teacher_name in ['', 'nan'] or str(teacher_name).isdigit(): 
            continue
            
        for day, cols in day_mapping.items():
            for p_idx, col in enumerate(cols):
                period = p_idx + 1
                subject = ""
                target_class = ""
                
                if data_type == '3줄 (과목 / 학급 / 빈칸)' or data_type == '2줄 (과목 / 학급)':
                    subject = str(df_raw.iloc[i, col]).strip() if pd.notna(df_raw.iloc[i, col]) else ""
                    target_class = str(df_raw.iloc[i+1, col]).strip() if i+1 < len(df_raw) and pd.notna(df_raw.iloc[i+1, col]) else ""
                elif data_type == '1줄 (한 칸에 모두 기입, 예: 국어(1-1))':
                    cell_val = str(df_raw.iloc[i, col]).strip() if pd.notna(df_raw.iloc[i, col]) else ""
                    subject = cell_val
                    match = re.search(r'$(.*?)$', cell_val)
                    target_class = match.group(1) if match else cell_val

                if subject and subject != 'nan' and not subject.replace('.', '').isdigit():
                    parsed_data.append({
                        "교사명": teacher_name,
                        "요일": day,
                        "교시": period,
                        "과목": subject,
                        "학급": target_class
                    })

    return pd.DataFrame(parsed_data)

# --- 3. 요일별 전체 공강(빈 시간) 분석 함수 ---
def find_all_free_times(teacher_schedule, day_mapping):
    recommendations = []
    days = ['월', '화', '수', '목', '금']
    
    for day in days:
        if day not in day_mapping: continue
        total_periods = len(day_mapping[day])
        busy_periods = teacher_schedule[teacher_schedule['요일'] == day]['교시'].tolist()
        
        if not busy_periods:
            recommendations.append({"요일": day, "빈 시간": "✨ 하루 전체 (전일 공강)"})
            continue
            
        free_periods = [p for p in range(1, total_periods + 1) if p not in busy_periods]
        
        if free_periods:
            time_strings = []
            for p in free_periods:
                time_txt = CLASS_TIMES.get(p, "")
                if time_txt:
                    time_strings.append(f"{p}교시 ({time_txt})")
                else:
                    time_strings.append(f"{p}교시")
            
            recommendations.append({"요일": day, "빈 시간": ", ".join(time_strings)})

    return pd.DataFrame(recommendations)

# --- 4. 프로그램 화면 UI ---
st.set_page_config(page_title="수업 교체 & 출장 도우미", layout="wide")
st.title("🔄 수업 교체 시스템")

uploaded_file = st.file_uploader("학교 시간표 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    day_mapping, day_row_idx, msg = find_excel_structure(df_raw)
    
    if day_mapping is None:
        st.error(f"엑셀 파일을 분석할 수 없습니다. 사유: {msg}")
    else:
        with st.expander("🤖 AI 엑셀 스캐너 분석 결과 (설정)", expanded=False):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.success("✅ 시간표 구조 발견")
                for day, cols in day_mapping.items(): st.write(f"- **{day}요일:** {len(cols)}교시")
            with col2:
                start_row = st.number_input("1️⃣ 시작 줄", value=day_row_idx + 2, min_value=0)
                teacher_col = st.number_input("2️⃣ 이름 열(A=0, B=1)", value=1, min_value=0)
                data_type = st.selectbox("3️⃣ 엑셀 기입 방식", ['3줄 (과목 / 학급 / 빈칸)', '2줄 (과목 / 학급)', '1줄 (한 칸에 모두 기입, 예: 국어(1-1))'])
                rows_per_teacher = int(data_type[0])

        df = parse_smart_schedule(df_raw, start_row, teacher_col, rows_per_teacher, day_mapping, data_type)
        
        if df.empty:
            st.warning("분석된 수업 데이터가 없습니다. 위의 AI 스캐너 설정을 조절해 보세요.")
        else:
            st.sidebar.header("🔍 검색 조건 입력")
            all_teachers = sorted(df['교사명'].unique())
            target_teacher = st.sidebar.selectbox("선생님 선택", all_teachers)
            teacher_schedule = df[df['교사명'] == target_teacher]
            
            if not teacher_schedule.empty:
                # --- 💡 공강 시간 찾기 ---
                st.sidebar.divider()
                st.sidebar.markdown("### ✈️ 수업 없는 시간 확인")
                st.sidebar.caption("요일별로 수업이 없는 모든 시간(공강)을 보여줍니다.")
                
                if st.sidebar.button("요일별 빈 시간 전체 보기", type="primary", use_container_width=True):
                    st.subheader(f"💡 {target_teacher} 선생님의 요일별 공강(출장 가능) 시간표")
                    st.divider()
                    
                    rec_df = find_all_free_times(teacher_schedule, day_mapping)
                    if not rec_df.empty:
                        st.dataframe(rec_df, hide_index=True, use_container_width=True)
                    else:
                        st.info("현재 수업이 없는 빈 시간(공강)이 전혀 없습니다. (풀타임 수업 중이십니다.)")
                    
                    # (수정됨) 아래의 st.stop()을 제거하여 사이드바가 끝까지 렌더링되게 만들었습니다!

                # --- 💡 수업 교체/보강 선생님 찾기 ---
                st.sidebar.divider()
                st.sidebar.markdown("### 🔄 수업 교체 선생님 찾기")
                target_day = st.sidebar.selectbox("결강 요일", ['월', '화', '수', '목', '금'])
                periods_available = sorted(teacher_schedule[teacher_schedule['요일'] == target_day]['교시'].unique())
                
                if len(periods_available) == 0:
                    st.sidebar.warning("해당 요일에는 배정된 수업이 없습니다.")
                else:
                    quick_select = st.sidebar.radio("⏱️ 빠른 선택", ["직접 선택", "전일 출장", "오전 반가", "오후 반가"])
                    if quick_select == "전일 출장": default_periods = periods_available
                    elif quick_select == "오전 반가": default_periods = [p for p in periods_available if p <= 4]
                    elif quick_select == "오후 반가": default_periods = [p for p in periods_available if p >= 5]
                    else: default_periods = []

                    target_periods = st.sidebar.multiselect("결강 교시", periods_available, default=default_periods)
                    
                    if st.sidebar.button("보강/교체 선생님 찾기", use_container_width=True):
                        if not target_periods:
                            st.warning("결강 교시를 하나 이상 선택해 주세요.")
                        else:
                            st.subheader(f"📅 {target_teacher} 선생님의 {target_day}요일 출장/연가 보강표")
                            st.divider()
                            for period in sorted(target_periods):
                                target_class_info = teacher_schedule[(teacher_schedule['요일'] == target_day) & (teacher_schedule['교시'] == period)].iloc[0]
                                target_class_name = target_class_info['학급']
                                subject_name = target_class_info['과목']
                                
                                with st.expander(f"📌 [ {period}교시 ] {subject_name} ({target_class_name})", expanded=True):
                                    busy_teachers = df[(df['요일'] == target_day) & (df['교시'] == period)]['교사명'].unique()
                                    free_teachers = [t for t in all_teachers if t not in busy_teachers and t != target_teacher]
                                    
                                    swap_results = []
                                    for free_t in free_teachers:
                                        free_t_schedule = df[df['교사명'] == free_t]
                                        possible_swaps = []
                                        for _, row in free_t_schedule.iterrows():
                                            if row['학급'] == target_class_name: 
                                                day_b = row['요일']
                                                period_b = row['교시']
                                                conflict = teacher_schedule[(teacher_schedule['요일'] == day_b) & (teacher_schedule['교시'] == period_b)]
                                                if conflict.empty: 
                                                    possible_swaps.append(f"{day_b} {period_b}교시")
                                        
                                        if possible_swaps:
                                            swap_results.append({"교사명": free_t, f"교체 (추후 들어갈 시간)": " / ".join(possible_swaps)})
                                    
                                    col1, col2 = st.columns([1.5, 1])
                                    with col1:
                                        st.markdown(f"**🥇 1순위: '{target_class_name}' 교체 가능**")
                                        if swap_results:
                                            st.dataframe(pd.DataFrame(swap_results), hide_index=True, use_container_width=True)
                                        else:
                                            st.info("교체 가능한 선생님이 없습니다.")
                                    with col2:
                                        st.markdown(f"**🥈 2순위: 단순 보강 (총 {len(free_teachers)}명)**")
                                        st.success(", ".join(free_teachers))
