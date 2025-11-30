import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
from datetime import datetime, timedelta

# --- Configuration & Constants ---
st.set_page_config(
    page_title="StandX 收益测算器",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
BOOST_END_DATE = datetime(2025, 12, 11)
RATE_BOOST = 1.5
RATE_BASE = 1.2
BONUS_DAILY = 10
DAILY_INFLATION = 0.03  # 每日全网积分增长率（更保守估计）

# API Configuration
API_URL = "https://api.standx.com/v1/offchain/perps-campaign/rank"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://standx.com",
    "Referer": "https://standx.com/"
}

# Professional Color Scheme
DARK_BLUE_GRAY = "#0F172A"
ROYAL_BLUE = "#2563EB"
EMERALD_GREEN = "#10B981"
LIGHT_BLUE = "#3B82F6"

# Custom CSS
st.markdown("""
<style>
    div[data-testid="stMetricValue"] > div {
        font-size: 48px !important;
        font-weight: 800 !important;
        padding-top: 10px;
    }
    
    div[data-testid="stMetricLabel"] > label {
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #64748B !important;
    }
    
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F1F5F9;
        padding: 25px 20px;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
    }

    .stCaption {
        font-size: 18px !important;
    }
    
    h1 {
        color: #0F172A !important;
        font-weight: 700 !important;
        font-size: 42px !important;
    }
    
    h2 {
        color: #0F172A !important;
        font-weight: 600 !important;
        font-size: 28px !important;
    }
    
    h3 {
        color: #0F172A !important;
        font-weight: 600 !important;
        font-size: 22px !important;
    }
    
    [data-testid="stSidebar"] label {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
    }
    
    [data-testid="stSidebar"] h2 {
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    
    .stMarkdown, p {
        font-size: 16px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Logic Functions ---

@st.cache_data(ttl=300)
def fetch_global_points():
    """获取当前全网积分估算"""
    try:
        params = {"limit": 200, "offset": 0}
        response = requests.get(API_URL, headers=HEADERS, params=params, timeout=5)
        response.raise_for_status()
        data = response.json().get("data", [])
        
        # Sum top 200 and multiply by 5.0 to estimate total (based on 210k participants)
        top_200_sum = sum(float(item.get("points", 0)) / 1_000_000 for item in data)
        estimated_total = top_200_sum * 5.0
        return estimated_total
    except:
        return 500_000_000

def calculate_points(capital, days, is_active):
    """精确的分段积分计算"""
    current_date = datetime.now()
    daily_breakdown = []
    total_points = 0
    
    for day in range(days):
        day_date = current_date + timedelta(days=day)
        
        if day_date <= BOOST_END_DATE:
            rate = RATE_BOOST
            period = "加速期"
        else:
            rate = RATE_BASE
            period = "基础期"
        
        daily_points = capital * rate
        
        if is_active:
            daily_points += BONUS_DAILY
        
        total_points += daily_points
        daily_breakdown.append({
            "天数": day + 1,
            "日期": day_date,
            "倍率": rate,
            "阶段": period,
            "当日积分": daily_points,
            "累计积分": total_points
        })
    
    return total_points, daily_breakdown

def get_daily_inflation_rate(day):
    """
    获取指定天数的全网积分增长率（递减模型）
    
    早期：高增长（新用户涌入）
    中期：增长放缓
    后期：趋于稳定
    """
    if day <= 30:
        return 0.04  # 前30天：4%（项目热度高，新用户快速增长）
    elif day <= 60:
        return 0.02  # 30-60天：2%（增长放缓）
    else:
        return 0.01  # 60天后：1%（趋于稳定）

def calculate_roi(my_points, duration_days, capital, fdv, airdrop_pct, current_global_points):
    """计算收益指标（使用递减增长率模型）"""
    # 计算未来全网积分（考虑每日不同的增长率）
    projected_global = current_global_points
    for day in range(1, duration_days + 1):
        daily_rate = get_daily_inflation_rate(day)
        projected_global *= (1 + daily_rate)
    
    my_share = my_points / projected_global if projected_global > 0 else 0
    est_value = fdv * (airdrop_pct / 100) * my_share
    net_profit = est_value
    roi = (est_value / capital * 100) if capital > 0 else 0
    apy = (roi / duration_days * 365) if duration_days > 0 else 0
    
    return {
        "est_value": est_value,
        "net_profit": net_profit,
        "roi": roi,
        "apy": apy,
        "my_share": my_share * 100,
        "projected_global": projected_global
    }

# --- UI Components ---

def render_sidebar():
    """渲染侧边栏控制面板"""
    st.sidebar.header("⚙️ 参数设置")
    
    capital = st.sidebar.number_input(
        "💰 投入本金 (DUSD)",
        min_value=100,
        max_value=1_000_000,
        value=10_000,
        step=1000
    )
    
    days = st.sidebar.slider(
        "📅 挖矿时长 (天)",
        min_value=1,
        max_value=90,
        value=30
    )
    
    is_active = st.sidebar.checkbox(
        "✅ 每日活跃任务 (+10分/天)",
        value=False
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 市场假设")
    
    fdv = st.sidebar.select_slider(
        "预期市值 (FDV)",
        options=[100_000_000, 250_000_000, 500_000_000, 1_000_000_000, 2_000_000_000, 3_000_000_000],
        value=1_000_000_000,
        format_func=lambda x: f"${x/1_000_000:.0f}M" if x < 1_000_000_000 else f"${x/1_000_000_000:.1f}B"
    )
    
    airdrop_pct = st.sidebar.slider(
        "空投占比 (%)",
        min_value=1.0,
        max_value=10.0,
        value=5.0,
        step=0.5
    )
    
    return capital, days, is_active, fdv, airdrop_pct

def render_kpis(my_points, metrics):
    """渲染核心指标卡片"""
    col1, col2, col3, col4 = st.columns(4)
    
    roi_display = f"+{metrics['roi']:.1f}%" if metrics['roi'] > 0 else f"{metrics['roi']:.1f}%"
    apy_display = f"+{metrics['apy']:.1f}%" if metrics['apy'] > 0 else f"{metrics['apy']:.1f}%"
    apy_emoji = " 🔥" if metrics['apy'] > 100 else ""
    
    with col1:
        st.metric(
            label="预期空投价值",
            value=f"${metrics['est_value']:,.2f}",
            delta=f"ROI: {roi_display}"
        )
    
    with col2:
        st.metric(
            label="净利润",
            value=f"${metrics['net_profit']:,.2f}",
            delta="纯收益" if metrics['net_profit'] > 0 else "亏损"
        )
    
    with col3:
        st.metric(
            label="隐含年化 (APY)",
            value=f"{apy_display}{apy_emoji}",
            delta="高收益" if metrics['apy'] > 100 else "中等收益"
        )
    
    with col4:
        st.metric(
            label="累计积分",
            value=f"{my_points:,.0f}",
            delta=f"占比: {metrics['my_share']:.4f}%"
        )

def render_sensitivity_heatmap(capital, days, is_active, current_global_points):
    """渲染敏感度热力图"""
    fdv_range = np.linspace(100_000_000, 3_000_000_000, 15)
    days_range = np.linspace(15, 90, 15)
    
    net_profit_matrix = []
    
    for day_val in days_range:
        row = []
        for fdv_val in fdv_range:
            my_pts, _ = calculate_points(capital, int(day_val), is_active)
            metrics = calculate_roi(my_pts, int(day_val), capital, fdv_val, 5.0, current_global_points)
            row.append(metrics['net_profit'])
        net_profit_matrix.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=net_profit_matrix,
        x=[f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M" for x in fdv_range],
        y=[f"{int(d)}天" for d in days_range],
        colorscale='Teal',
        colorbar=dict(
            title=dict(
                text="净利润 ($)",
                font=dict(size=14)
            )
        ),
        hovertemplate='FDV: %{x}<br>投资天数: %{y}<br>净利润: $%{z:,.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text="敏感度矩阵：净利润 vs FDV & 投资时长",
            font=dict(size=20, color=DARK_BLUE_GRAY, family="Arial")
        ),
        xaxis_title="预期市值 (FDV)",
        yaxis_title="投资天数",
        height=500,
        font=dict(size=14, color=DARK_BLUE_GRAY),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def render_points_chart(daily_breakdown):
    """渲染积分累积曲线"""
    df = pd.DataFrame(daily_breakdown)
    
    fig = go.Figure()
    
    # Add the main line chart
    fig.add_trace(go.Scatter(
        x=df['天数'],
        y=df['累计积分'],
        mode='lines+markers',
        fill='tozeroy',
        line=dict(color='#3B82F6', width=3),
        marker=dict(size=4, color='#3B82F6'),
        fillcolor='rgba(59, 130, 246, 0.15)',
        name='累计积分',
        showlegend=True,
        hovertemplate='第 %{x} 天<br>累计积分: %{y:,.0f}<extra></extra>'
    ))
    
    # Add boost end marker
    boost_end_day = None
    for idx, row in df.iterrows():
        if row['日期'] > BOOST_END_DATE and boost_end_day is None:
            boost_end_day = row['天数']
            break
    
    if boost_end_day:
        fig.add_vline(
            x=boost_end_day,
            line_dash="dash",
            line_color="#EF4444",
            line_width=2,
            annotation_text="1.5x 加速结束",
            annotation_position="top",
            annotation=dict(
                font=dict(size=12, color="#EF4444")
            )
        )
    
    fig.update_layout(
        title=dict(
            text="积分累积趋势",
            font=dict(size=20, color=DARK_BLUE_GRAY, family="Arial")
        ),
        xaxis=dict(
            title="天数",
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)'
        ),
        yaxis=dict(
            title="累计积分",
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)'
        ),
        height=400,
        font=dict(size=14, color=DARK_BLUE_GRAY),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
        showlegend=True
    )
    
    return fig

# --- Main App ---

def main():
    # Header with Logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("assets/standx_logo.png", width=500)
        except:
            pass
        st.markdown('<h1 style="text-align: center; margin-top: 10px;">收益测算器</h1>', unsafe_allow_html=True)
    
    st.markdown('<div style="text-align: center;"><p style="font-size: 18px; color: #64748B;">基于主网分段倍率模型的量化估算</p></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    capital, days, is_active, fdv, airdrop_pct = render_sidebar()
    
    # Fetch global data
    with st.spinner("正在获取全网数据..."):
        current_global_points = fetch_global_points()
    
    # Calculate
    my_points, daily_breakdown = calculate_points(capital, days, is_active)
    metrics = calculate_roi(my_points, days, capital, fdv, airdrop_pct, current_global_points)
    
    # Display KPIs
    st.subheader("📈 核心指标")
    render_kpis(my_points, metrics)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(render_points_chart(daily_breakdown), use_container_width=True)
    
    with col2:
        st.plotly_chart(render_sensitivity_heatmap(capital, days, is_active, current_global_points), use_container_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="color: #94A3B8; font-size: 12px; text-align: center;">'
        '注：本模型基于当前积分规则估算，仅供参考，不构成投资建议。'
        '</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
