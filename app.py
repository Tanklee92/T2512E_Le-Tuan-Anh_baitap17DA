import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px

# ---------------------------------------------------------
# 1. Cấu hình Trang Web
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Bán Hàng Realtime",
    page_icon="📊",
    layout="wide"
)

# ---------------------------------------------------------
# 2. Tạo kết nối CSDL & Caching dữ liệu
# ---------------------------------------------------------
# Sử dụng @st.cache_resource để giữ kết nối CSDL không bị khởi tạo lại mỗi lần tương tác
@st.cache_resource
def init_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["username"],
        password=st.secrets["mysql"]["password"]
    )

conn = init_connection()

# Sử dụng @st.cache_data với ttl (Time To Live) để lưu kết quả truy vấn trong 10 phút
@st.cache_data(ttl=600)
def run_query(query, params=None):
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute(query, params or ())
        result = cursor.fetchall()
    return pd.DataFrame(result)

# ---------------------------------------------------------
# 3. Giao diện Sidebar - Các Bộ Lọc (Filters)
# ---------------------------------------------------------
st.sidebar.header("🔍 Bộ Lọc Dữ Liệu")

# Lấy danh sách danh mục sản phẩm từ CSDL để làm Dropdown
try:
    categories_df = run_query("SELECT category_name FROM Categories")
    category_list = ["Tất cả"] + categories_df['category_name'].tolist()
except Exception as e:
    st.error(f"Không thể kết nối CSDL: {e}")
    st.stop()

selected_category = st.sidebar.selectbox("Chọn Danh mục Sản phẩm:", category_list)

# ---------------------------------------------------------
# 4. Truy vấn Dữ liệu theo Bộ Lọc & Hiển thị
# ---------------------------------------------------------
st.title("📊 Báo Cáo Doanh Thu Bán Hàng (E-Commerce)")

# Xây dựng câu lệnh SQL linh hoạt dựa theo Filter
base_sql = """
    SELECT 
        o.order_id,
        o.order_date,
        o.status,
        c.category_name,
        p.product_name,
        od.quantity,
        (od.quantity * od.unit_price) AS total_price
    FROM Orders o
    JOIN OrderDetails od ON o.order_id = od.order_id
    JOIN Products p ON od.product_id = p.product_id
    JOIN Categories c ON p.category_id = c.category_id
    WHERE o.status = 'Completed'
"""

if selected_category != "Tất cả":
    base_sql += " AND c.category_name = %s"
    df = run_query(base_sql, (selected_category,))
else:
    df = run_query(base_sql)

# ---------------------------------------------------------
# 5. Hiển thị Các Chỉ Số Quan Trọng (KPI Metrics)
# ---------------------------------------------------------
if not df.empty:
    col1, col2, col3 = st.columns(3)
    
    total_revenue = df['total_price'].sum()
    total_orders = df['order_id'].nunique()
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    col1.metric("Tổng Doanh Thu", f"{total_revenue:,.0f} USD")
    col2.metric("Tổng Số Đơn Hàng", f"{total_orders} đơn")
    col3.metric("Giá Trị Trung Bình/Đơn", f"{avg_order_value:,.2f} USD")

    st.markdown("---")

    # ---------------------------------------------------------
    # 6. Biểu đồ Trực quan hóa (Plotly Chart)
    # ---------------------------------------------------------
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Doanh Thu Theo Ngày")
        df_daily = df.groupby('order_date')['total_price'].sum().reset_index()
        fig_line = px.line(df_daily, x='order_date', y='total_price', markers=True,
                           labels={'order_date': 'Ngày', 'total_price': 'Doanh Thu ($)'})
        st.plotly_chart(fig_line, use_container_width=True)

    with col_chart2:
        st.subheader("Top Sản Phẩm Bán Chạy")
        df_product = df.groupby('product_name')['quantity'].sum().reset_index()
        fig_bar = px.bar(df_product, x='quantity', y='product_name', orientation='h',
                         labels={'quantity': 'Số Lượng', 'product_name': 'Sản Phẩm'})
        st.plotly_chart(fig_bar, use_container_width=True)

    # ---------------------------------------------------------
    # 7. Bảng Dữ liệu Chi tiết
    # ---------------------------------------------------------
    with st.expander("📄 Xem Bảng Dữ Liệu Chi Tiết"):
        st.dataframe(df, use_container_width=True)
else:
    st.warning("Không tìm thấy dữ liệu phù hợp với bộ lọc!")

