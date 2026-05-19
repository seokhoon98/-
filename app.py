import pandas as pd
import streamlit as st
import re

# --- 1. AI 엑셀 구조 자동 탐지 함수 ---
@st.cache_data
def find_excel_structure(df_raw):
    day_mapping = {'월':[], '화':[], '수':[], '목':[], '금':[]}
    day_row_idx = -1
    
    # 1. '월', '화' 글자가 포함된 행 찾기 (상위 15줄 이내)
    for i in range(min(15, len(df_raw))):
        row_str = "".join(df_raw.iloc[i].fillna("").astype(str))
        if '월' in row_str and '화' in row_str:
            day_row_idx = i
            break
            
    if day_row_idx == -1:
        return None, -1, "요일(월,화,수...) 행을 찾을 수 없습니다."

    # 2. 요일별 열(Column) 인덱스 매핑
    current_day = None
    for col_idx in range(len(df_raw.columns)):
        val = str(df_raw.iloc[day_row_idx, col_idx]).strip().replace('요일', '')
        for day_key in day_mapping.keys():
            if val == day_key:
                current_day = day_key
                break
        
        if current_day is not None:
            day_mapping[current_day].append(col_idx)
            
    # 3. 빈 칸 및 교시가 아닌 열 필터링 (바로 밑 줄에 숫자가 있는지 확인)
    period_row_idx = day_row_idx + 1
    cleaned_mapping = {}
    for day, cols in day_mapping.items():
        valid_cols = []
        for c in cols:
            if period_row_idx < len(df_raw):
                val = str(df_raw.iloc[period_row_idx, c]).strip()
                if val.isdigit() or val.replace('교시','').isdigit():
                    valid_cols.append(c)
        
        # 숫자를 못 찾았으면 일단 전체 열을 다 넣음 (예외 처리)
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
                
                # 엑셀 기입 방식에 따른 처리
                if data_type == '3줄 (과목 / 학급 / 빈칸)':
                    subject = str(df_raw.iloc[i, col]).strip() if pd.notna(df_raw.iloc[i, col]) else ""
                    target_class = str(df_raw.iloc[i+1, col]).strip() if i+1 < len(df_raw) and pd.notna(df_raw.iloc[i+1, col]) else ""
                elif data_type == '2줄 (과목 / 학급)':
                    subject = str(df_raw.iloc[i, col]).strip() if pd.notna(df_raw.iloc[i, col]) else ""
                    target_class = str(df_raw.iloc[i+1, col]).strip() if i+1 < len(df_raw) and pd.notna(df_raw.iloc[i+1, col]) else ""
                elif data_type == '1줄 (한 칸에 모두 기입, 예: 국어(1-1))':
                    cell_val = str(df_raw.iloc[i, col]).strip() if pd.notna(df_raw.iloc[i, col]) else ""
                    subject = cell_val
                    # 괄호 안의 글자(반) 추출
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


# --- 3. 프로그램 화면 UI ---
st.set_page_config(page_title="전국 단위 수업 교체 도우미", layout="wide")
st.title("🔄 학교 수업 맞교환 추천 시스템 (AI 스캐너 탑재)")
st.markdown("전국 어느 학교의 시간표든 업로드만 하세요. AI가 엑셀 구조를 스스로 파악합니다.")

uploaded_file = st.file_uploader("학교 시간표 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    
    # AI 구조 탐지 실행
    day_mapping, day_row_idx, msg = find_excel_structure(df_raw)
    
    if day_mapping is None:
        st.error(f"엑셀 파일을 분석할 수 없습니다. 사유: {msg}")
    else:
        # --- 스캐너 분석 결과 및 설정 영역 ---
        with st.expander("🤖 AI 엑셀 스캐너 분석 결과 (수정 가능)", expanded=True):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.success("✅ 시간표 기본 구조를 성공적으로 찾았습니다!")
                for day, cols in day_mapping.items():
                    st.write(f"- **{day}요일:** 총 {len(cols)}교시 발견")
            
            with col2:
                st.info("⚠️ 학교마다 서식이 다르므로 아래 내용을 맞게 설정해 주세요.")
                start_row = st.number_input("1️⃣ 첫 번째 선생님의 데이터가 시작되는 줄(Row)", value=day_row_idx + 2, min_value=0)
                teacher_col = st.number_input("2️⃣ 선생님 이름이 적혀있는 열(Column, A열=0, B열=1)", value=1, min_value=0)
                
                data_type = st.selectbox("3️⃣ 엑셀표 1칸에 적힌 방식 (한 명당 줄 수)", [
                    '3줄 (과목 / 학급 / 빈칸)',
                    '2줄 (과목 / 학급)',
                    '1줄 (한 칸에 모두 기입, 예: 국어(1-1))'
                ])
                rows_per_teacher = int(data_type[0]) # 첫 글자 숫자(3,2,1) 추출

        st.divider()

        # 분석된 데이터 파싱
        df = parse_smart_schedule(df_raw, start_row, teacher_col, rows_per_teacher, day_mapping, data_type)
        
        if df.empty:
            st.warning("분석된 수업 데이터가 없습니다. 위의 AI 스캐너 설정(시작 줄, 이름 열)을 조절해 보세요.")
        else:
            # --- 메인 로직 (기존과 동일) ---
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
                    quick_select = st.sidebar.radio("⏱️ 빠른 선택", ["직접 선택", "전일 출장", "오전 반가", "오후 반가"])
                    
                    if quick_select == "전일 출장": default_periods = periods_available
                    elif quick_select == "오전 반가": default_periods = [p for p in periods_available if p <= 4]
                    elif quick_select == "오후 반가": default_periods = [p for p in periods_available if p >= 5]
                    else: default_periods = []

                    target_periods = st.sidebar.multiselect("결강 교시", periods_available, default=default_periods)
                    
                    if st.sidebar.button("결과 한눈에 보기", type="primary"):
                        if not target_periods:
                            st.warning("결강 교시를 하나 이상 선택해 주세요.")
                        else:
                            st.subheader(f"📅 {target_teacher} 선생님의 {target_day}요일 출장/연가 대강표")
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
                                            swap_results.append({"교사명": free_t, f"맞교환 (추후 들어갈 시간)": " / ".join(possible_swaps)})
                                    
                                    col1, col2 = st.columns([1.5, 1])
                                    with col1:
                                        st.markdown(f"**🥇 1순위: '{target_class_name}' 맞교환 가능**")
                                        if swap_results:
                                            st.dataframe(pd.DataFrame(swap_results), hide_index=True, use_container_width=True)
                                        else:
                                            st.info("맞교환 가능한 선생님이 없습니다.")
                                    with col2:
                                        st.markdown(f"**🥈 2순위: 단순 대강 (총 {len(free_teachers)}명)**")
                                        st.success(", ".join(free_teachers))
