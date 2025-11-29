import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import numpy as np
from datetime import datetime, timedelta

# --- Configuration & Constants ---
st.set_page_config(
    page_title="StandX 收益测算器",
    page_icon="�",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
BOOST_END_DATE = datetime(2025, 12, 11)
RATE_BOOST = 1.5
RATE_BASE = 1.2
BONUS_DAILY = 10
DAILY_INFLATION = 0.015  # 1.5% daily growth

# API Configuration
API_URL = "https://api.standx.com/v1/offchain/perps-campaign/rank"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://standx.com",
    "Referer": "https://standx.com/"
}

# Professional Color Scheme (Light Mode)
DARK_BLUE_GRAY = "#0F172A"
ROYAL_BLUE = "#2563EB"
EMERALD_GREEN = "#10B981"
LIGHT_BLUE = "#3B82F6"

# Custom CSS for enhanced card styling and larger fonts
st.markdown("""
<style>
    /* 1. 放大核心指标 (Metric) 的数字 */
    div[data-testid="stMetricValue"] > div {
        font-size: 48px !important;
        font-weight: 800 !important;
        padding-top: 10px;
    }
    
    /* 2. 放大指标标题 (Metric Label) */
    div[data-testid="stMetricLabel"] > label {
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #64748B !important;
    }
    
    /* 3. 优化卡片间距和阴影 */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F1F5F9;
        padding: 25px 20px;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
    }

    /* 4. 调整副标题字号 */
    .stCaption {
        font-size: 18px !important;
    }
    
    /* 5. 标题样式 */
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
    
    /* 6. Logo 容器居中 */
    .logo-container {
        text-align: center;
        padding: 20px 0;
    }
    
    /* 7. 侧边栏字体放大 */
    .css-1d391kg, [data-testid="stSidebar"] {
        font-size: 16px !important;
    }
    
    [data-testid="stSidebar"] label {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
    }
    
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stCheckbox label,
    [data-testid="stSidebar"] .stSelectSlider label {
        font-size: 18px !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stSidebar"] input {
        font-size: 16px !important;
    }
    
    [data-testid="stSidebar"] h2 {
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    
    /* 8. 放大所有文本 */
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
        
        # Sum top 200 and multiply by 1.3 to estimate total
        top_200_sum = sum(float(item.get("points", 0)) / 1_000_000 for item in data)
        estimated_total = top_200_sum * 1.3
        return estimated_total
    except requests.exceptions.Timeout:
        st.warning("API 请求超时，使用默认估算值")
        return 500_000_000
    except Exception as e:
        st.warning(f"无法获取实时数据，使用默认估算值")
        return 500_000_000

def calculate_points(capital, days, is_active):
    """
    精确的分段积分计算
    Returns: (total_points, daily_breakdown)
    """
    current_date = datetime.now()
    daily_breakdown = []
    total_points = 0
    
    for day in range(days):
        day_date = current_date + timedelta(days=day)
        
        # 根据加速期判断倍率
        if day_date <= BOOST_END_DATE:
            rate = RATE_BOOST
            period = "加速期"
        else:
            rate = RATE_BASE
            period = "基础期"
        
        # 计算每日积分
        daily_points = capital * rate
        
        # 活跃任务奖励
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

def calculate_roi(my_points, duration_days, capital, fdv, airdrop_pct, current_global_points):
    """计算收益指标"""
    # 预测期末全网积分
    projected_global = current_global_points * ((1 + DAILY_INFLATION) ** duration_days)
    
    # 我的份额
    my_share = my_points / projected_global if projected_global > 0 else 0
    
    # 预期空投价值
    est_value = fdv * (airdrop_pct / 100) * my_share
    
    # 净利润 (空投价值即为净利润，本金可取回)
    net_profit = est_value
    
    # ROI (投资回报率)
    roi = (est_value / capital * 100) if capital > 0 else 0
    
    # APY (年化收益率)
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
        step=1000,
        help="您计划投入的 DUSD 数量"
    )
    
    days = st.sidebar.slider(
        "📅 挖矿时长 (天)",
        min_value=1,
        max_value=90,
        value=30,
        help="计划参与积分挖矿的天数"
    )
    
    is_active = st.sidebar.checkbox(
        "✅ 每日活跃任务 (+10分/天)",
        value=False,
        help="是否完成每日交易任务获得额外积分"
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
        step=0.5,
        help="空投占代币总量的百分比"
    )
    
    return capital, days, is_active, fdv, airdrop_pct

def render_kpis(my_points, metrics):
    """渲染核心指标卡片"""
    col1, col2, col3, col4 = st.columns(4)
    
    # Format ROI with + prefix and emoji
    roi_display = f"+{metrics['roi']:.1f}%" if metrics['roi'] > 0 else f"{metrics['roi']:.1f}%"
    apy_display = f"+{metrics['apy']:.1f}%" if metrics['apy'] > 0 else f"{metrics['apy']:.1f}%"
    apy_emoji = " 🔥" if metrics['apy'] > 100 else ""
    
    with col1:
        st.metric(
            label="预期空投价值",
            value=f"${metrics['est_value']:,.2f}",
            delta=f"ROI: {roi_display}",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            label="净利润",
            value=f"${metrics['net_profit']:,.2f}",
            delta="纯收益" if metrics['net_profit'] > 0 else "亏损",
            delta_color="normal" if metrics['net_profit'] > 0 else "inverse"
        )
    
    with col3:
        st.metric(
            label="隐含年化 (APY)",
            value=f"{apy_display}{apy_emoji}",
            delta="高收益" if metrics['apy'] > 100 else "中等收益",
            delta_color="normal"
        )
    
    with col4:
        st.metric(
            label="累计积分",
            value=f"{my_points:,.0f}",
            delta=f"占比: {metrics['my_share']:.4f}%"
        )

def render_accumulation_chart(daily_breakdown):
    """渲染积分增长曲线"""
    df = pd.DataFrame(daily_breakdown)
    
    fig = go.Figure()
    
    # 面积图
    fig.add_trace(go.Scatter(
        x=df['天数'],
        y=df['累计积分'],
        fill='tozeroy',
        mode='lines',
        line=dict(color=LIGHT_BLUE, width=2),
        fillcolor=f'rgba(59, 130, 246, 0.2)',
        name='累计积分'
    ))
    
    # 加速期结束标记
    boost_end_day = None
    for idx, row in df.iterrows():
        if row['日期'] > BOOST_END_DATE and boost_end_day is None:
            boost_end_day = row['天数']
            break
    
    if boost_end_day:
        fig.add_vline(
            x=boost_end_day,
            line_dash="dash",
            line_color=ROYAL_BLUE,
            line_width=2,
            annotation_text="1.5x 加速结束",
            annotation_position="top",
            annotation_font_color=ROYAL_BLUE,
            annotation_font_size=12
        )
    
    fig.update_layout(
        title="积分增长曲线",
        xaxis_title="天数",
        yaxis_title="累计积分",
        font=dict(family="Arial, sans-serif", color=DARK_BLUE_GRAY),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=400,
        hovermode='x unified',
        xaxis=dict(showgrid=True, gridcolor='#E5E7EB'),
        yaxis=dict(showgrid=True, gridcolor='#E5E7EB')
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_sensitivity_heatmap(capital, is_active, airdrop_pct, current_global_points):
    """渲染敏感度矩阵"""
    # 创建网格
    fdv_range = np.linspace(100_000_000, 3_000_000_000, 10)
    days_range = np.arange(15, 91, 5)
    
    # 计算每个组合的净利润
    results = []
    for fdv in fdv_range:
        for days in days_range:
            points, _ = calculate_points(capital, days, is_active)
            metrics = calculate_roi(points, days, capital, fdv, airdrop_pct, current_global_points)
            net_profit = metrics['net_profit']
            results.append({
                'FDV': fdv,
                '天数': days,
                '净利润': net_profit
            })
    
    df = pd.DataFrame(results)
    pivot = df.pivot(index='天数', columns='FDV', values='净利润')
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"${x/1e9:.1f}B" for x in pivot.columns],
        y=pivot.index,
        colorscale='Teal',
        colorbar=dict(
            title=dict(
                text="净利润 ($)",
                font=dict(color=DARK_BLUE_GRAY, size=12)
            )
        ),
        hovertemplate='市值: %{x}<br>天数: %{y}<br>净利润: $%{z:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="敏感度矩阵：净利润分析",
        xaxis_title="StandX 预期市值",
        yaxis_title="投入天数",
        font=dict(family="Arial, sans-serif", color=DARK_BLUE_GRAY),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=450,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# --- Main App ---

def main():
    # Header with Logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Load official StandX logo
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
    
    # Section 1: Core Metrics
    st.subheader("📈 核心指标")
    render_kpis(my_points, metrics)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Section 2: Charts
    col1, col2 = st.columns(2)
    
    with col1:
        render_accumulation_chart(daily_breakdown)
    
    with col2:
        render_sensitivity_heatmap(capital, is_active, airdrop_pct, current_global_points)
    
    # Section 3: Detailed Breakdown
    with st.expander("� 详细数据"):
        st.dataframe(
            pd.DataFrame(daily_breakdown),
            use_container_width=True,
            hide_index=True
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("您的积分占比", f"{metrics['my_share']:.4f}%")
        with col2:
            st.metric("预测期末全网积分", f"{metrics['projected_global']:,.0f}")
    
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
