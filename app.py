import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os

# 페이지 설정
st.set_page_config(page_title="학생 체형 분석 대시보드", layout="wide")

# 1. 데이터 로드 및 정제 함수 (캐싱 적용)
@st.cache_data
def prepare_integrated_data():
    try:
        # 파일명은 이전 단계에서 GitHub에 올린 이름과 일치해야 합니다.
        file1 = 'school_data_1학기_cleaned.csv'
        file2 = 'school_data_2학기_cleaned.csv'
        
        if os.path.exists(file1) and os.path.exists(file2):
            df1 = pd.read_csv(file1)
            df2 = pd.read_csv(file2)
            df1['학기'] = '1학기'
            df2['학기'] = '2학기'
            full_df = pd.concat([df1, df2], ignore_index=True)
            
            parts = ['목', '어깨', '허리', '엉덩', '무릎', '발목']
            for p in parts:
                full_df[p] = pd.to_numeric(full_df[p], errors='coerce')

            def standardize_grade(row):
                school, grade = str(row['학교']), str(row['학년'])
                num = re.search(r'(\d+)', grade).group(1) if re.search(r'(\d+)', grade) else "0"
                if '초' in school: return f"초등 {num}학년", "초등"
                elif '중' in school: return f"중등 {num}학년", "중등"
                elif '고' in school: return f"고등 {num}학년", "고등"
                return f"초등 {num}학년", "초등"

            full_df[['표준학년', '학교급']] = full_df.apply(lambda x: pd.Series(standardize_grade(x)), axis=1)
            full_df = full_df[~full_df['자세 세부 유형'].isin(['자세 세부 유형', 'nan', 'None'])].copy()
            return full_df, parts
    except Exception as e:
        st.error(f"데이터 로딩 중 오류 발생: {e}")
    return pd.DataFrame(), []

# 데이터 초기화
df, body_parts = prepare_integrated_data()

# 타이틀
st.title("📊 학생 체형 분석 통합 대시보드")

if df.empty:
    st.warning("데이터 파일을 찾을 수 없습니다. GitHub 저장소에 CSV 파일이 있는지 확인해주세요.")
else:
    # 2. 사이드바 컨트롤러 (Dash의 컨트롤러 섹션)
    st.sidebar.header("🔍 필터 설정")
    level = st.sidebar.radio("🏫 학교급 선택", ["전체", "초등", "중등", "고등"], horizontal=True)
    
    # 학교급에 따른 학년 필터링
    dff_filtered = df if level == '전체' else df[df['학교급'] == level]
    grade_options = ["전체 학년"] + sorted(dff_filtered['표준학년'].unique().tolist())
    grade = st.sidebar.selectbox("📅 상세 학년 선택", grade_options)
    
    # 최종 데이터 필터링
    if grade != "전체 학년":
        dff_filtered = dff_filtered[dff_filtered['표준학년'] == grade]

    # 3. 데이터 계산
    avg_data = dff_filtered.groupby('학기')[body_parts].mean().T
    
    # 4. 메인 레이아웃 (2x2 그리드)
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    # --- 1. Bar Chart ---
    with row1_col1:
        st.subheader("💪 부위별 균형도 변화")
        fig_main = go.Figure()
        for sem, col in [('1학기', "#A4C3E6"), ('2학기', '#3B82F6')]:
            if sem in avg_data.columns:
                fig_main.add_trace(go.Bar(name=sem, x=body_parts, y=avg_data[sem], marker_color=col))
        fig_main.update_layout(barmode='group', margin=dict(t=30, b=0, l=30, r=30))
        st.plotly_chart(fig_main, use_container_width=True)
        
        # Insight
        if '1학기' in avg_data.columns and '2학기' in avg_data.columns:
            diff = avg_data['2학기'] - avg_data['1학기']
            st.info(f"💡 가장 개선된 부위: **{diff.idxmax()}** (+{diff.max():.1f}점)")

# --- 2. Radar Chart ---
    with row1_col2:
        st.subheader("🕸️ 전신 균형 밸런스")
        fig_radar = go.Figure()
        
        # 색상 리스트: 1학기(빨강), 2학기(파랑)
        semester_colors = ['rgba(255, 99, 132, 0.5)', 'rgba(59, 130, 246, 0.5)']
        
        for sem, color in zip(['1학기', '2학기'], semester_colors):
            if sem in avg_data.columns:
                fig_radar.add_trace(go.Scatterpolar(
                    r=avg_data[sem], 
                    theta=body_parts, 
                    fill='toself', 
                    name=sem,
                    fillcolor=color,           # 도형 내부 채우기 색상
                    line=dict(color=color)      # 테두리 선 색상
                ))
        
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])), 
            margin=dict(t=40, b=40, l=40, r=40)
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        st.info("💡 도형의 면적이 넓을수록 전반적인 체형 균형이 우수함을 나타냅니다.")

    # --- 3. Pie Chart Subplots ---
    with row2_col1:
        st.subheader("🚨 학기별 위험군 분포 비교")
        fig_pie = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]], subplot_titles=['1학기', '2학기'])
        for i, sem in enumerate(['1학기', '2학기']):
            sem_df = dff_filtered[dff_filtered['학기'] == sem]
            if not sem_df.empty:
                counts = sem_df['자세 세부 유형'].value_counts()
                mask = (counts / counts.sum()) < 0.02
                processed = counts[~mask].to_dict()
                if mask.any(): processed['기타'] = counts[mask].sum()
                fig_pie.add_trace(go.Pie(labels=list(processed.keys()), values=list(processed.values()), hole=0.4), 1, i+1)
        fig_pie.update_layout(margin=dict(t=50, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)
        st.info("💡 2% 미만 유형은 '기타'로 통합되었습니다.")

    # --- 4. Heatmap ---
    with row2_col2:
        st.subheader("🔗 신체 부위별 연관성 (2학기)")
        d2 = dff_filtered[dff_filtered['학기'] == '2학기']
        if not d2.empty:
            corr = d2[body_parts].corr()
            fig_heat = px.imshow(corr, text_auto=".2f", color_continuous_scale='Blues')
            fig_heat.update_layout(margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_heat, use_container_width=True)
            st.info("💡 수치가 1에 가까울수록 두 부위의 불균형이 연동될 가능성이 높습니다.")
        else:
            st.write("2학기 데이터가 없습니다.")