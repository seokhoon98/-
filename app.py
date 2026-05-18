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
st.title("🔄 학교 수업 맞교환 & 보강 추천 시스템")
st.markdown("**해당 반(학급)**의 수업을 서로 맞바꿀 수 있는 선생님을 찾아줍니다.")

uploaded_file = st.file_uploader("시간표 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    df = load_schedule_data(uploaded_file)
    
    st.sidebar.header("🔍 결강 정보 입력")
    all_teachers = sorted(df['교사명'].unique())
    
    target_teacher = st.sidebar.selectbox("출장/결강 가시는 선생님", all_teachers)
    teacher_schedule = df[df['교사명'] == target_teacher]
    
    if not teacher_schedule.empty:
        target_day = st.sidebar.selectbox("결강 요일", ['월', '화', '수', '목', '금'])
        periods_available = teacher_schedule[teacher_schedule['요일'] == target_day]['교시'].unique()
        
        if len(periods_available) == 0:
            st.sidebar.warning("해당 요일에는 배정된 수업이 없습니다.")
        else:
            target_period = st.sidebar.selectbox("결강 교시", sorted(periods_available))
            
            if st.sidebar.button("교체 가능한 선생님 찾기", type="primary"):
                target_class_info = teacher_schedule[(teacher_schedule['요일'] == target_day) & (teacher_schedule['교시'] == target_period)].iloc[0]
                target_class_name = target_class_info['학급'] # 빠지는 수업의 '반(학급)' 정보 저장
                
                st.subheader(f"📌 {target_teacher} 선생님의 {target_day}요일 {target_period}교시 결강")
                st.markdown(f"**진행 예정이었던 수업:** {target_class_info['과목']} (**{target_class_name}**)")
                st.divider()
                
                # [로직 1] 해당 결강 시간에 수업이 있는 사람/없는 사람 분류
                busy_teachers = df[(df['요일'] == target_day) & (df['교시'] == target_period)]['교사명'].unique()
                free_teachers = [t for t in all_teachers if t not in busy_teachers and t != target_teacher]
                
                # [로직 2] 1:1 맞교환 로직 (동일한 반 수업만 추출!)
                swap_results = []
                for free_t in free_teachers:
                    free_t_schedule = df[df['교사명'] == free_t]
                    
                    possible_swaps = []
                    for _, row in free_t_schedule.iterrows():
                        # 핵심 수정: 상대방 선생님의 수업 중 '결강하는 반'과 완벽히 똑같은 반일 경우에만 체크!
                        if row['학급'] == target_class_name:
                            day_b = row['요일']
                            period_b = row['교시']
                            
                            conflict = teacher_schedule[(teacher_schedule['요일'] == day_b) & (teacher_schedule['교시'] == period_b)]
                            if conflict.empty: 
                                possible_swaps.append(f"{day_b}요일 {period_b}교시({row['과목']})")
                    
                    if possible_swaps:
                        swap_results.append({
                            "교사명": free_t,
                            f"맞교환 가능 시간 (추후 내가 {target_class_name}에 들어갈 시간)": " / ".join(possible_swaps)
                        })
                
                # --- 화면 출력부 ---
                st.subheader(f"🥇 1순위: '{target_class_name}' 완벽 맞교환 가능한 선생님")
                st.caption(f"해당 결강 시간에 공강이시며, 추후 다른 요일에 있는 선생님의 '{target_class_name}' 수업과 내 공강 시간을 바꿀 수 있는 명단입니다.")
                
                if swap_results:
                    res_df = pd.DataFrame(swap_results)
                    st.dataframe(res_df, hide_index=True, use_container_width=True)
                else:
                    st.info(f"현재 완벽하게 '{target_class_name}' 수업을 맞교환할 수 있는 선생님이 없습니다.")
                
                st.write("")
                st.write("")
                
                st.subheader(f"🥈 2순위: 단순 보강 가능 선생님 (총 {len(free_teachers)}명)")
                st.caption("결강 시간에 수업이 없는(공강인) 선생님들입니다. (동일 반 맞교환은 아니지만 보강 부탁이 가능합니다.)")
                st.success(", ".join(free_teachers))
