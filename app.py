import streamlit as st
import pandas as pd
import io

# --- 页面设置 ---
st.set_page_config(page_title="EPR 精细化核算工具", page_icon="📊", layout="wide")

st.title("🌍 亚马逊 EPR 包装法申报表格生成器 (全中文版)")
st.markdown("### 上传 CSV -> 选择国家 -> 生成【全材质细分】申报表")
st.markdown("支持材质：纸、塑料、玻璃、铝、铁、木头、其他")

# --- 0. 定义国家代码映射字典 (全局通用) ---
# 放在这里，侧边栏和表格生成都能用到
COUNTRY_MAP = {
    'DE': '德国 (DE)',
    'FR': '法国 (FR)',
    'ES': '西班牙 (ES)',
    'IT': '意大利 (IT)',
    'GB': '英国 (GB)',
    'UK': '英国 (UK)',
    'PL': '波兰 (PL)',
    'SE': '瑞典 (SE)',
    'NL': '荷兰 (NL)',
    'BE': '比利时 (BE)',
    'AT': '奥地利 (AT)',
    'US': '美国 (US)',
    'CA': '加拿大 (CA)',
    'JP': '日本 (JP)',
    'AU': '澳大利亚 (AU)',
    'AE': '阿联酋 (AE)',
    'SA': '沙特 (SA)',
    'SG': '新加坡 (SG)',
    'IE': '爱尔兰 (IE)',
    'PT': '葡萄牙 (PT)',
    'TR': '土耳其 (TR)',
    'MX': '墨西哥 (MX)',
    'BR': '巴西 (BR)',
    'IN': '印度 (IN)'
}

# --- 侧边栏 ---
with st.sidebar:
    st.header("📂 1. 文件上传")
    uploaded_file = st.file_uploader("请上传 Amazon EPR 原始数据.csv", type=["csv"])

# --- 辅助函数：尝试多种编码读取 CSV ---
def load_csv_safe(file):
    """尝试使用不同的编码读取 CSV 文件，解决 Excel 导出乱码问题"""
    encodings = ['utf-8', 'gbk', 'gb18030', 'cp1252', 'latin1']
    
    for encoding in encodings:
        try:
            file.seek(0) # 每次重试前，将文件指针重置到开头
            return pd.read_csv(file, encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    return None, None

# --- 核心逻辑 ---
if uploaded_file is not None:
    try:
        # 1. 使用增强的读取函数
        df, loaded_encoding = load_csv_safe(uploaded_file)

        if df is None:
            st.error("❌ 无法读取文件编码。请尝试在 Excel 中将文件另存为 'CSV UTF-8 (逗号分隔)' 格式。")
            st.stop()
        
        # 检查必要的列是否存在
        if 'SHIP_TO_COUNTRY_CODE' not in df.columns:
            st.error(f"❌ 错误：读取成功 (编码: {loaded_encoding})，但找不到 'SHIP_TO_COUNTRY_CODE' 列。")
            st.stop()

        # 2. 获取文件包含的所有国家代码
        available_countries = df['SHIP_TO_COUNTRY_CODE'].dropna().unique().tolist()
        available_countries.sort()

        if not available_countries:
            st.error("❌ 错误：文件中没有有效的国家代码数据。")
        else:
            # --- 侧边栏增加国家选择 (此处修改了显示逻辑) ---
            st.sidebar.header("🌍 2. 选择站点")
            
            # 默认选中德国(DE)，如果文件里没有DE，就选第一个
            default_index = available_countries.index('DE') if 'DE' in available_countries else 0
            
            # format_func 负责把 'DE' 显示成 '德国 (DE)'
            selected_country = st.sidebar.selectbox(
                "请选择要核算的国家:", 
                available_countries, 
                index=default_index,
                format_func=lambda x: COUNTRY_MAP.get(x, x)  # ✨ 这里的魔法让下拉菜单显示中文
            )

            # 3. 根据选择的国家筛选数据
            df_target = df[df['SHIP_TO_COUNTRY_CODE'] == selected_country].copy()
            
            # 获取当前选中的中文名用于展示
            display_country_name = COUNTRY_MAP.get(selected_country, selected_country)

            st.info(f"读取成功 | 当前站点: **{display_country_name}** | 记录数: {len(df_target)}")

            # 4. 数据预处理
            material_cols = [
                'PAPER_KG', 'PLASTIC_KG', 
                'GLASS_KG', 'ALUMINUM_KG', 'STEEL_KG', 'WOOD_KG', 'OTHER_KG'
            ]
            
            # 确保列存在并填充0
            for col in material_cols:
                if col not in df_target.columns:
                    df_target[col] = 0.0
                df_target[col] = df_target[col].fillna(0.0)

            # 5. 计算逻辑
            
            # 6. 构建强制结构表
            target_categories = ['Primary Packaging', 'Secondary Packaging']
            
            cols_to_sum = ['TOTAL_UNITS_SOLD'] + material_cols
            
            grouped = df_target.groupby('EPR_CATEGORY')[cols_to_sum].sum()
            df_final = grouped.reindex(target_categories, fill_value=0)

            # 7. 计算总重量
            df_final['Total_Weight_KG'] = df_final[material_cols].sum(axis=1)

            # 8. 添加总计
            grand_total_row = df_final.sum()
            grand_total_row.name = '总计 (Grand Total)'
            df_final = pd.concat([df_final, grand_total_row.to_frame().T])

            # 9. 格式化表格
            row_mapping = {
                'Primary Packaging': 'Primary Packaging (一级/产品包装)',
                'Secondary Packaging': 'Secondary Packaging (二级/运输包装)'
            }
            df_final = df_final.rename(index=row_mapping)
            
            # 重置索引
            df_display = df_final.reset_index()

            # 插入带中文的国家列
            df_display.insert(0, '国家/站点 (Country)', display_country_name)

            # 列名映射
            col_mapping = {
                'index': '申报类别 (EPR Category)',
                'TOTAL_UNITS_SOLD': '申报总件数 (Units)',
                'PAPER_KG': '纸质 (Paper) kg',
                'PLASTIC_KG': '塑料 (Plastic) kg',
                'GLASS_KG': '玻璃 (Glass) kg',
                'ALUMINUM_KG': '铝 (Aluminum) kg',
                'STEEL_KG': '铁 (Steel) kg',
                'WOOD_KG': '木头 (Wood) kg',
                'OTHER_KG': '其他 (Other) kg',
                'Total_Weight_KG': '总重量 (Total Weight) kg'
            }
            df_display = df_display.rename(columns=col_mapping)

            # 10. 展示
            st.divider()
            st.success(f"✅ {display_country_name} 站点核算完成！")
            
            format_dict = {
                '申报总件数 (Units)': '{:.0f}',
                '纸质 (Paper) kg': '{:.3f}',
                '塑料 (Plastic) kg': '{:.3f}',
                '玻璃 (Glass) kg': '{:.3f}',
                '铝 (Aluminum) kg': '{:.3f}',
                '铁 (Steel) kg': '{:.3f}',
                '木头 (Wood) kg': '{:.3f}',
                '其他 (Other) kg': '{:.3f}',
                '总重量 (Total Weight) kg': '{:.3f}'
            }

            st.dataframe(
                df_display.style.format(format_dict), 
                use_container_width=True,
                hide_index=True
            )

            # 11. 导出
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                sheet_name = f'{selected_country}_明细数据'
                df_display.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                
                # 调整列宽
                worksheet.set_column('A:A', 20) 
                worksheet.set_column('B:B', 35) 
                worksheet.set_column('C:K', 15) 

            file_name = f"{display_country_name}_包装法_明细申报表.xlsx"
            
            st.download_button(
                label=f"📥 下载表格: {file_name}",
                data=buffer.getvalue(),
                file_name=file_name,
                mime="application/vnd.ms-excel"
            )

    except Exception as e:
        st.error(f"❌ 发生程序错误: {e}")
        import traceback
        st.text(traceback.format_exc())

else:
    st.info("👈 请在左侧上传 CSV 文件。")