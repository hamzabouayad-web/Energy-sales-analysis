import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
warnings.filterwarnings('ignore')

np.random.seed(42)

conn = sqlite3.connect(':memory:')
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT,
    category TEXT,
    unit_cost REAL
);
CREATE TABLE regions (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT,
    state TEXT
);
CREATE TABLE clients (
    client_id INTEGER PRIMARY KEY,
    client_name TEXT,
    client_type TEXT,
    region_id INTEGER
);
CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY,
    product_id INTEGER,
    client_id INTEGER,
    region_id INTEGER,
    sale_date TEXT,
    quantity REAL,
    unit_price REAL,
    discount REAL
);
""")

products = [
    (1,'Crude Oil (Barrel)','Upstream',42.00),
    (2,'Natural Gas (MMBtu)','Upstream',2.10),
    (3,'Refined Diesel','Downstream',1.85),
    (4,'Jet Fuel','Downstream',1.92),
    (5,'Lubricants & Specialty Oils','Downstream',3.40),
    (6,'Pipeline Inspection Services','Services',800.00),
    (7,'Drilling Equipment Rental','Services',1200.00),
    (8,'LNG (Liquefied Natural Gas)','Upstream',4.50),
    (9,'Petrochemicals','Downstream',0.95),
    (10,'Safety & Compliance Audit','Services',2500.00),
]
cur.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

regions = [
    (1,'Gulf Coast','TX'),
    (2,'Permian Basin','TX'),
    (3,'Appalachian','PA'),
    (4,'Mid-Continent','OK'),
    (5,'Rocky Mountain','CO'),
]
cur.executemany("INSERT INTO regions VALUES (?,?,?)", regions)

clients = [
    (1,'Lone Star Energy Corp','Refinery',1),
    (2,'Gulf Petrotech LLC','Distributor',1),
    (3,'Permian Resources Inc','E&P Company',2),
    (4,'West Texas Drilling Co','E&P Company',2),
    (5,'Appalachian Gas Partners','Pipeline Ops',3),
    (6,'Keystone Industrial Supply','Distributor',3),
    (7,'Midland Energy Solutions','Refinery',4),
    (8,'Oklahoma Basin Operators','E&P Company',4),
    (9,'Rocky Fuel Services','Distributor',5),
    (10,'Continental Energy Group','Pipeline Ops',5),
]
cur.executemany("INSERT INTO clients VALUES (?,?,?,?)", clients)

cost_map = {r[0]: r[3] for r in products}
cat_map  = {r[0]: r[2] for r in products}
prod_weights = [0.22,0.18,0.14,0.10,0.08,0.07,0.07,0.06,0.05,0.03]
dates = pd.date_range('2023-01-01','2024-12-31',freq='D')

sales_rows = []
for i in range(1, 1801):
    prod_id  = int(np.random.choice(range(1,11), p=prod_weights))
    client_id= int(np.random.randint(1,11))
    region_id= int(np.random.randint(1,6))
    date     = pd.Timestamp(np.random.choice(dates)).strftime('%Y-%m-%d')
    cost     = cost_map[prod_id]
    if prod_id in [1,2,8]:
        qty = round(float(np.random.uniform(500,50000)),1)
    elif prod_id in [3,4,5,9]:
        qty = round(float(np.random.uniform(100,5000)),1)
    else:
        qty = float(np.random.randint(1,15))
    price    = round(cost * float(np.random.uniform(1.15,1.85)), 4)
    discount = round(float(np.random.choice(
        [0,0,0,0.02,0.05,0.08,0.10],
        p=[0.45,0.20,0.10,0.10,0.07,0.05,0.03]
    )), 2)
    sales_rows.append((i, prod_id, client_id, region_id, date, qty, price, discount))

cur.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?)", sales_rows)
conn.commit()

# Verify data loaded
check = pd.read_sql_query("SELECT COUNT(*) as cnt FROM sales s JOIN products p ON s.product_id=p.product_id", conn)
print(f"JOIN check: {check['cnt'].values[0]} rows")

# Query 1 — Revenue by category
q1 = """
SELECT p.category,
       COUNT(s.sale_id) AS transactions,
       ROUND(SUM(s.quantity * s.unit_price * (1-s.discount)),0) AS gross_revenue,
       ROUND(AVG((s.unit_price*(1-s.discount) - p.unit_cost) /
                  NULLIF(s.unit_price*(1-s.discount),0) * 100),1) AS avg_margin_pct
FROM sales s
INNER JOIN products p ON s.product_id = p.product_id
GROUP BY p.category
ORDER BY gross_revenue DESC
"""
df_cat = pd.read_sql_query(q1, conn)
print("Category results:"); print(df_cat)

# Query 2 — Top 5 products
q2 = """
SELECT p.product_name, p.category,
       COUNT(s.sale_id) AS orders,
       ROUND(SUM(s.quantity * s.unit_price * (1-s.discount)),0) AS net_revenue
FROM sales s
INNER JOIN products p ON s.product_id = p.product_id
GROUP BY p.product_name, p.category
ORDER BY net_revenue DESC LIMIT 5
"""
df_top = pd.read_sql_query(q2, conn)
print("Top products:"); print(df_top)

# Query 3 — Regional
q3 = """
SELECT r.region_name, r.state,
       COUNT(s.sale_id) AS transactions,
       ROUND(SUM(s.quantity * s.unit_price * (1-s.discount)),0) AS net_revenue,
       ROUND(SUM(s.quantity * s.unit_price * (1-s.discount))/COUNT(s.sale_id),0) AS avg_deal_size
FROM sales s
INNER JOIN regions r ON s.region_id = r.region_id
GROUP BY r.region_name, r.state
ORDER BY net_revenue DESC
"""
df_region = pd.read_sql_query(q3, conn)

# Query 4 — Monthly 2024
q4 = """
SELECT SUBSTR(sale_date,1,7) AS month,
       COUNT(sale_id) AS transactions,
       ROUND(SUM(quantity * unit_price * (1-discount)),0) AS monthly_revenue
FROM sales WHERE sale_date LIKE '2024%'
GROUP BY month ORDER BY month
"""
df_monthly = pd.read_sql_query(q4, conn)

# Query 5 — Client type
q5 = """
SELECT c.client_type,
       COUNT(DISTINCT c.client_id) AS clients,
       ROUND(SUM(s.quantity * s.unit_price * (1-s.discount)),0) AS total_revenue
FROM sales s
INNER JOIN clients c ON s.client_id = c.client_id
GROUP BY c.client_type ORDER BY total_revenue DESC
"""
df_clients = pd.read_sql_query(q5, conn)

# CHARTS
NAVY='#1B2A4A'; TEAL='#00897B'; GOLD='#F4A623'
CORAL='#E05C4B'; LAVENDER='#7B68EE'; MGRAY='#888888'
palette = [NAVY, TEAL, CORAL, GOLD, LAVENDER]

fig = plt.figure(figsize=(14,10))
fig.patch.set_facecolor('white')
gs = gridspec.GridSpec(2,3,figure=fig,hspace=0.42,wspace=0.38)
fig.suptitle('Energy Sector Sales & Operations Dashboard  |  2023–2024\nSQL Analysis by Hamza Bouayad',
             fontsize=13,fontweight='bold',y=0.98,color=NAVY)

# Chart 1 — Revenue by category
ax1 = fig.add_subplot(gs[0,0])
cats = df_cat['category'].tolist()
revs = (df_cat['gross_revenue']/1e6).tolist()
bars = ax1.bar(cats, revs, color=palette[:len(cats)], edgecolor='white', linewidth=1.5)
ax1.set_title('Revenue by Category ($M)', fontweight='bold', fontsize=9, color=NAVY)
ax1.set_ylabel('Revenue ($M)', fontsize=8)
ax1.tick_params(labelsize=8)
for bar in bars:
    h = bar.get_height()
    ax1.text(bar.get_x()+bar.get_width()/2, h+0.3,
             f'${h:.0f}M', ha='center', fontsize=7.5, fontweight='bold', color=NAVY)
ax1.spines[['top','right']].set_visible(False)

# Chart 2 — Margin by category
ax2 = fig.add_subplot(gs[0,1])
margins = df_cat['avg_margin_pct'].tolist()
ax2.barh(cats, margins, color=[TEAL,GOLD,LAVENDER], edgecolor='white', linewidth=1.2)
ax2.set_title('Avg Profit Margin % by Category', fontweight='bold', fontsize=9, color=NAVY)
ax2.set_xlabel('Margin %', fontsize=8)
ax2.tick_params(labelsize=8)
for i,v in enumerate(margins):
    ax2.text(v+0.2, i, f'{v:.1f}%', va='center', fontsize=8, fontweight='bold')
ax2.spines[['top','right']].set_visible(False)

# Chart 3 — Top 5 products
ax3 = fig.add_subplot(gs[0,2])
short = [n.split('(')[0].strip()[:18] for n in df_top['product_name']]
revs3 = (df_top['net_revenue']/1e6).tolist()
ax3.barh(short[::-1], revs3[::-1], color=palette[::-1], edgecolor='white', linewidth=1.2)
ax3.set_title('Top 5 Products ($M)', fontweight='bold', fontsize=9, color=NAVY)
ax3.set_xlabel('Revenue ($M)', fontsize=8)
ax3.tick_params(labelsize=7.5)
ax3.spines[['top','right']].set_visible(False)

# Chart 4 — Monthly trend
ax4 = fig.add_subplot(gs[1,0:2])
months = [m[-2:] for m in df_monthly['month'].tolist()]
rev_m  = (df_monthly['monthly_revenue']/1e6).tolist()
ax4.plot(months, rev_m, marker='o', color=NAVY, linewidth=2.5,
         markersize=7, markerfacecolor=GOLD, markeredgecolor=NAVY, markeredgewidth=1.5)
ax4.fill_between(range(len(months)), rev_m, alpha=0.07, color=NAVY)
peak_i = rev_m.index(max(rev_m))
ax4.annotate(f'Peak: ${rev_m[peak_i]:.1f}M',
             xy=(peak_i, rev_m[peak_i]),
             xytext=(peak_i+0.5, rev_m[peak_i]+0.5),
             fontsize=8, color=CORAL, fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=CORAL, lw=1.2))
ax4.set_title('2024 Monthly Revenue Trend ($M)', fontweight='bold', fontsize=9, color=NAVY)
ax4.set_xlabel('Month (2024)', fontsize=8)
ax4.set_ylabel('Revenue ($M)', fontsize=8)
ax4.set_xticks(range(len(months)))
ax4.set_xticklabels(months, fontsize=8)
ax4.spines[['top','right']].set_visible(False)

# Chart 5 — Regional pie
ax5 = fig.add_subplot(gs[1,2])
wedges,texts,autotexts = ax5.pie(
    df_region['net_revenue'].tolist(),
    labels=df_region['region_name'].tolist(),
    autopct='%1.1f%%', colors=palette, startangle=90,
    wedgeprops={'edgecolor':'white','linewidth':2})
for at in autotexts: at.set_fontsize(8); at.set_fontweight('bold')
for t in texts: t.set_fontsize(7.5)
ax5.set_title('Revenue Share by Region', fontweight='bold', fontsize=9, color=NAVY)

plt.savefig('/home/claude/projects/energy_dashboard_v2.png',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("Chart saved successfully")
