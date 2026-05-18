import pandas as pd
import streamlit as st

# --- 1. 엑셀 시간표 데이터 분석 로직 ---
@st.cache_data
def load_schedule_data(file_path):
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None)
    
    days_cols = {
        '월': list(range(2, 9)),
        '화': list(range(9, 16)),
        '수': list(range(16, 23)),
        '목': list(range(23, 29)),
        '금': list(range(29, 34))
    }

    parsed_data = []
    
    for i in range(4, len(df_raw), 3):
        row_subject = df_raw.iloc[i]
        if i + 1 >= len(df_raw):
            break
        row_class = df_raw.iloc[i+1]
        
        teacher_name = str(row_subject[1]).strip()
        if pd.isna(teacher_name) or teacher_name == '' or teacher_name == 'nan':
            continue
            
        for day, cols in days_cols.items():
            for period_idx, col in enumerate(cols):
                period = period_idx + 1
                subject = str(row_subject[col]).strip() if pd.notna(row_subject[col]) else ""
                target_class = str(row_class[col]).strip() if pd.notna(row_class[col]) else ""
                
                if subject and subject != 'nan':
                    parsed_data.append({
                        "교사명": teacher_name,
                        "요일": day,
                        "교시": period,
                        "과목": subject,
                        "학급": target_class
                    })

    return pd.DataFrame(parsed_data)


# --- 2. 프로그램 화면 및 교체 추천 알고리즘 ---
st.set_page_config(page_title="수업 교체 도우미", layout="wide")
st.title("🔄 다중 수업 교체 추천 시스템")
st.markdown("전일 출장, 반일 연가 등 **여러 개의 수업을 한 번에** 선택하고 교체 가능한 선생님을 확인하세요.")

uploaded_file = st.file_uploader("시간표 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    df = load_schedule_data(uploaded_file)
    
    st.sidebar.header("🔍 결강 정보 입력")
    all_teachers = sorted(df['교사명'].unique())
    
    target_teacher = st.sidebar.selectbox("출장/결강 가시는 선생님", all_teachers)
    teacher_schedule = df[df['교사명'] == target_teacher]
    
    if not teacher_schedule.empty:
        target_day = st.sidebar.selectbox("결강 요일", ['월', '화', '수', '목', '금'])
        periods_available = sorted(teacher_schedule[teacher_schedule['요일'] == target_day]['교시'].unique())
        
        if len(periods_available) == 0:
            st.sidebar.warning("해당 요일에는 배정된 수업이 없습니다.")
        else:
            # 💡 추가된 기능: 빠른 선택 라디오 버튼
            quick_select = st.sidebar.radio(
                "⏱️ 빠른 선택 (자동 체크)", 
                ["직접 선택", "전일 출장 (전체)", "오전 반가 (1~4교시)", "오후 반가 (5교시~)"]
            )
            
            # 라디오 버튼 선택에 따른 기본값 세팅
            if quick_select == "전일 출장 (전체)":
                default_periods = periods_available
            elif quick_select == "오전 반가 (1~4교시)":
                default_periods = [p for p in periods_available if p <= 4]
            elif quick_select == "오후 반가 (5교시~)":
                default_periods = [p for p in periods_available if p >= 5]
            else:
                default_periods = []

            # 💡 다중 선택 체크박스 (여러 개 선택 가능)
            target_periods = st.sidebar.multiselect(
                "결강 교시 (여러 개 선택 가능)", 
                periods_available, 
                default=default_periods
            )
            
            if st.sidebar.button("결과 한눈에 보기", type="primary"):
                if not target_periods:
                    st.warning("결강 교시를 하나 이상 선택해 주세요.")
                else:
                    st.subheader(f"📅 {target_teacher} 선생님의 {target_day}요일 출장/연가 대강표")
                    st.divider()
                    
                    # 💡 선택한 각 교시별로 반복(Loop)하여 결과 출력
                    for period in sorted(target_periods):
                        target_class_info = teacher_schedule[(teacher_schedule['요일'] == target_day) & (teacher_schedule['교시'] == period)].iloc[0]
                        target_class_name = target_class_info['학급']
                        subject_name = target_class_info['과목']
                        
                        # 💡 아코디언(Expander) 방식으로 교시별 묶어서 보여주기
                        with st.expander(f"📌 [ {period}교시 ] {subject_name} ({target_class_name})", expanded=True):
                            
                            busy_teachers = df[(df['요일'] == target_day) & (df['교시'] == period)]['교사명'].unique()
                            free_teachers = [t for t in all_teachers if t not in busy_teachers and t != target_teacher]
                            
                            swap_results = []
                            for free_t in free_teachers:
                                free_t_schedule = df[df['교사명'] == free_t]
                                possible_swaps = []
                                
                                for _, row in free_t_schedule.iterrows():
                                    if row['학급'] == target_class_name: # 동일 반 맞교환 확인
                                        day_b = row['요일']
                                        period_b = row['교시']
                                        
                                        conflict = teacher_schedule[(teacher_schedule['요일'] == day_b) & (teacher_schedule['교시'] == period_b)]
                                        if conflict.empty: 
                                            possible_swaps.append(f"{day_b} {period_b}교시({row['과목']})")
                                
                                if possible_swaps:
                                    swap_results.append({
                                        "교사명": free_t,
                                        f"맞교환 (추후 들어갈 시간)": " / ".join(possible_swaps)
                                    })
                            
                            # 화면 좌우 분할 배치
                            col1, col2 = st.columns([1.5, 1])
                            
                            with col1:
                                st.markdown(f"**🥇 1순위: '{target_class_name}' 맞교환 가능**")
                                if swap_results:
                                    res_df = pd.DataFrame(swap_results)
                                    st.dataframe(res_df, hide_index=True, use_container_width=True)
                                else:
                                    st.info("맞교환 가능한 선생님이 없습니다.")
                            
                            with col2:
                                st.markdown(f"**🥈 2순위: 단순 대강 (총 {len(free_teachers)}명)**")
                                st.success(", ".join(free_teachers))
