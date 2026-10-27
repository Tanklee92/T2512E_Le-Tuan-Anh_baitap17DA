import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px

# 1. Cấu hình trang
st.set_page_config(
    page_title="Dashboard Bán Hàng E-Commerce",
    page_icon="📊",
    layout="wide",
)

MONEY_UNIT = "USD"
CACHE_TTL = 60  

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    connection = None
    cursor = None
    try:
        cfg = st.secrets["mysql"]
        connection = mysql.connector.connect(
            host=cfg["host"],
            port=int(cfg["port"]),
            database=cfg["database"],
            user=cfg["username"],
            password=cfg["password"],
            connection_timeout=10,
        )
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, params)
        columns = cursor.column_names
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


st.title("📊 Báo Cáo Doanh Thu Bán Hàng (E-Commerce)")
st.caption("Bài 17 · MySQL + Pandas + Plotly + Streamlit")

st.sidebar.header("🔍 Bộ lọc dữ liệu")
if st.sidebar.button("🔄 Làm mới dữ liệu"):
    run_query.clear()
    st.rerun()

try:
    categories_df = run_query(
        "SELECT DISTINCT category_name FROM Categories "
        "WHERE category_name IS NOT NULL ORDER BY category_name"
    )
    cities_df = run_query(
        "SELECT DISTINCT city FROM Customers "
        "WHERE city IS NOT NULL ORDER BY city"
    )
    statuses_df = run_query(
        "SELECT DISTINCT status FROM Orders "
        "WHERE status IS NOT NULL ORDER BY status"
    )
    bounds_df = run_query(
        "SELECT MIN(DATE(order_date)) AS min_date, "
        "MAX(DATE(order_date)) AS max_date FROM Orders"
    )
except Exception as exc:
    st.error(f"Không thể lấy bộ lọc từ MySQL: {exc}")
    st.info("Kiểm tra file .streamlit/secrets.toml và tên bảng/cột trong phpMyAdmin.")
    st.stop()

if bounds_df.empty or pd.isna(bounds_df.at[0, "min_date"]):
    st.warning("Bảng Orders chưa có đơn hàng nên chưa thể hiển thị Dashboard.")
    st.stop()

min_date = pd.to_datetime(bounds_df.at[0, "min_date"]).date()
max_date = pd.to_datetime(bounds_df.at[0, "max_date"]).date()

start_date = st.sidebar.date_input(
    "Từ ngày", value=min_date, min_value=min_date, max_value=max_date
)
end_date = st.sidebar.date_input(
    "Đến ngày", value=max_date, min_value=min_date, max_value=max_date
)

if start_date > end_date:
    st.error("Ngày bắt đầu không được lớn hơn ngày kết thúc.")
    st.stop()

status_options = statuses_df["status"].dropna().astype(str).tolist()
status_default = ["Completed"] if "Completed" in status_options else status_options
selected_statuses = st.sidebar.multiselect(
    "Trạng thái đơn hàng", status_options, default=status_default
)

category_options = ["Tất cả"] + categories_df["category_name"].dropna().astype(str).tolist()
selected_category = st.sidebar.selectbox("Danh mục sản phẩm", category_options)

city_options = ["Tất cả"] + cities_df["city"].dropna().astype(str).tolist()
selected_city = st.sidebar.selectbox("Thành phố", city_options)

if not selected_statuses:
    st.warning("Hãy chọn ít nhất một trạng thái đơn hàng ở thanh bên trái.")
    st.stop()

placeholders = ", ".join(["%s"] * len(selected_statuses))
sql = f"""
    SELECT
        o.order_id,
        o.order_date,
        o.status,
        cu.city,
        c.category_name,
        p.product_name,
        od.quantity,
        od.unit_price,
        (od.quantity * od.unit_price) AS total_price
    FROM Orders AS o
    INNER JOIN Customers AS cu ON o.customer_id = cu.customer_id
    INNER JOIN OrderDetails AS od ON o.order_id = od.order_id
    INNER JOIN Products AS p ON od.product_id = p.product_id
    INNER JOIN Categories AS c ON p.category_id = c.category_id
    WHERE o.order_date >= %s
      AND o.order_date < DATE_ADD(%s, INTERVAL 1 DAY)
      AND o.status IN ({placeholders})
"""
params = [start_date, end_date, *selected_statuses]

if selected_category != "Tất cả":
    sql += " AND c.category_name = %s"
    params.append(selected_category)
if selected_city != "Tất cả":
    sql += " AND cu.city = %s"
    params.append(selected_city)
sql += " ORDER BY o.order_date DESC, o.order_id DESC"

try:
    df = run_query(sql, tuple(params))
except Exception as exc:
    st.error(f"Truy vấn dữ liệu thất bại: {exc}")
    st.info("Kiểm tra đặc biệt các cột Customers.city, Orders.customer_id, OrderDetails.unit_price.")
    st.stop()

if df.empty:
    st.warning("Không tìm thấy chi tiết đơn hàng phù hợp với bộ lọc đang chọn.")
    st.stop()

df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce").fillna(0)

completed = df[df["status"].astype(str).str.casefold() == "completed"].copy()
revenue = float(completed["total_price"].sum())
order_count = int(df["order_id"].nunique())
completed_orders = int(completed["order_id"].nunique())
aov = revenue / completed_orders if completed_orders else 0
units_sold = int(completed["quantity"].sum())


k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Tổng doanh thu", f"{revenue:,.2f} {MONEY_UNIT}")
k2.metric("🧾 Số đơn hàng", f"{order_count:,}")
k3.metric("📈 AOV / đơn hoàn thành", f"{aov:,.2f} {MONEY_UNIT}")
k4.metric("📦 Sản phẩm đã bán", f"{units_sold:,}")
st.caption("Doanh thu, AOV và số sản phẩm chỉ tính đơn Completed. "
           "Số đơn hàng đếm các trạng thái đang lọc.")

st.divider()


left_chart, right_chart = st.columns(2)
with left_chart:
    st.subheader("📈 Doanh thu theo ngày")
    if not completed.empty:
        completed["ngay"] = completed["order_date"].dt.date
        daily = (
            completed.dropna(subset=["ngay"])
            .groupby("ngay", as_index=False)["total_price"].sum()
            .sort_values("ngay")
        )
        if not daily.empty:
            fig_line = px.line(
                daily, x="ngay", y="total_price", markers=True,
                labels={"ngay": "Ngày đặt hàng", "total_price": f"Doanh thu ({MONEY_UNIT})"},
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Không có ngày hợp lệ để vẽ biểu đồ.")
    else:
        st.info("Không có đơn Completed trong bộ lọc.")

with right_chart:
    st.subheader("🏆 Top 5 sản phẩm bán chạy")
    if not completed.empty:
        top5 = (
            completed.groupby("product_name", as_index=False)["quantity"].sum()
            .nlargest(5, "quantity")
            .sort_values("quantity", ascending=True)
        )
        fig_bar = px.bar(
            top5, x="quantity", y="product_name", orientation="h",
            labels={"quantity": "Số lượng", "product_name": "Sản phẩm"},
            text="quantity",
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Không có sản phẩm thuộc đơn Completed để xếp hạng.")


st.subheader("📄 Bảng dữ liệu chi tiết")
visible_columns = [
    "order_id", "order_date", "status", "city", "category_name",
    "product_name", "quantity", "unit_price", "total_price",
]
table_df = df[visible_columns].copy()
st.dataframe(table_df, use_container_width=True, hide_index=True)

csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="⬇️ Tải dữ liệu đã lọc (CSV)",
    data=csv_bytes,
    file_name="bao_cao_ecommerce_bai17.csv",
    mime="text/csv",
)
st.caption("CSV xuất các dòng theo bộ lọc hiện tại, bao gồm cả trạng thái không Completed nếu được chọn.")