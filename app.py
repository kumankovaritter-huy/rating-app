import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import math

# ==================== НАСТРОЙКИ ====================
VALID_PLATFORMS = [
    'лемана про', 'лемана про мп', 'мегастрой', 
    'максидом', 'петрович', 'все инструменты'
]

SEASONAL_KEYWORDS = [
    'светильник светодиодный', 'на солнечной батарее', 'на солнечных батареях',
    'солар', 'solar', 'прожектор', 'светильник настенный', 'сад', 'столб',
    'уличный', 'датчик', 'таймер', 'садовый', 'налобный', 'кемпинговый',
    'ручной', 'перчатка', 'перчатки', 'фонарь'
]

LAMP_KEYWORDS = [
    'люстра', 'люстр', 'потолочный', 'бра', 'светильник',
    'светильник потолочный', 'подвесной', 'торшер', 'спот', 'ночник'
]

# ==================== ЧЁРНЫЙ СПИСОК ====================
def load_blacklist():
    blacklist = set()
    try:
        if os.path.exists('blacklist.txt'):
            with open('blacklist.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    sku = line.strip()
                    if sku:
                        blacklist.add(sku)
        return blacklist
    except:
        return set()

BLACKLIST = load_blacklist()

# ==================== ФУНКЦИИ ====================
def clean_numeric(val):
    if pd.isna(val):
        return np.nan
    val_str = str(val).replace(' ', '').replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return np.nan

def check_status(status):
    if pd.isna(status):
        return True
    s = str(status).strip().lower()
    if s == '':
        return True
    if 'закрыт к' in s:
        return False
    if s.startswith('открыт к заказам'):
        return True
    return True

def is_clearance(status):
    if pd.isna(status):
        return False
    s = str(status).strip().lower()
    return 'распродажа' in s and 'вывод' in s

def get_priority(row):
    rating = row['Рейтинг_число']
    prev_rating = row['Предыдущий_рейтинг_число']
    reviews = row['Отзывы_число']
    
    if pd.notna(rating) and rating <= 3.9:
        return 1
    if pd.notna(rating) and rating >= 4.0 and pd.notna(prev_rating) and rating < prev_rating:
        return 2
    if pd.notna(rating) and rating <= 4.5 and (pd.isna(reviews) or reviews < 3):
        return 3
    if (pd.isna(rating) or rating > 4.3) and (pd.isna(reviews) or reviews <= 1):
        return 4
    return 99

def get_recommendation(row):
    rating = row['Рейтинг_число']
    reviews = row['Отзывы_число']
    if pd.notna(rating) and rating >= 4.0 and pd.notna(reviews) and reviews == 1:
        return "⚠️ Риск падения: написать 1-2 отзыва"
    if pd.notna(rating) and rating < 4.0 and pd.notna(reviews) and reviews >= 10:
        return "📅 Долгосрочная работа: 3-5 отзывов постепенно"
    return "✅ Стандартная проработка"

def calculate_needed_fives(row):
    rating = row['Рейтинг_число']
    reviews = row['Отзывы_число']
    
    if pd.isna(rating) or pd.isna(reviews):
        return 0
    
    if rating < 4.0:
        needed = math.ceil(reviews * (4 - rating))
        return max(needed, 1)
    else:
        if reviews == 1:
            if rating >= 4.9:
                return 1
            else:
                return 2
        else:
            return 1

# ==================== ИНТЕРФЕЙС ====================
st.set_page_config(page_title="Аналитика Рейтингов 4.5+", layout="wide")

st.markdown("""
<style>
.main .block-container {
    max-width: 1200px !important;
    padding-top: 2rem;
}
h1 {
    text-align: center;
    font-size: 2.2rem !important;
}
.stFileUploader > div:first-child {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #4a4a6a;
    border-radius: 16px;
    padding: 24px 32px;
    transition: all 0.3s ease;
}
.stFileUploader > div:first-child:hover {
    border-color: #ff6b35;
    box-shadow: 0 4px 20px rgba(255, 107, 53, 0.2);
    transform: translateY(-2px);
}
.stFileUploader button {
    background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 12px 28px !important;
    border-radius: 10px !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(255, 107, 53, 0.4) !important;
}
.stFileUploader button:hover {
    box-shadow: 0 6px 20px rgba(255, 107, 53, 0.6) !important;
    transform: translateY(-2px) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>Автоматизация отбора артикулов для работы с рейтингом</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; font-size: 2rem; margin-top: -10px;'>⚡</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("", type=['csv', 'xlsx'], label_visibility="collapsed")

st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.image("logo.png", width=500)
with col2:
    st.image("второе_фото.png", width=500)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            xl = pd.ExcelFile(uploaded_file)
            sheet_names = xl.sheet_names
            default_index = 0
            for i, name in enumerate(sheet_names):
                if 'текущ' in name.lower():
                    default_index = i
                    break
            selected_sheet = st.selectbox("📂 Выберите лист:", sheet_names, index=default_index)
            df = xl.parse(selected_sheet)

        st.success("✅ Файл успешно прочитан!")

        df.columns = df.columns.astype(str).str.strip()

        required_cols = ['Артикул поставщика', 'Статус', 'Площадка', 'Ссылка', 'Рейтинг', 'Кол-во отзывов', 'Предыдущий рейтинг', 'Наименование']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.error(f"❌ Не найдены колонки: {', '.join(missing_cols)}")
        else:
            with st.spinner("🔄 Анализируем данные..."):
                df['Рейтинг_число'] = df['Рейтинг'].apply(clean_numeric)
                df['Отзывы_число'] = df['Кол-во отзывов'].apply(clean_numeric)
                df['Предыдущий_рейтинг_число'] = df['Предыдущий рейтинг'].apply(clean_numeric)
                df['is_clearance'] = df['Статус'].apply(is_clearance)

                df_filtered = df[df['Статус'].apply(check_status)].copy()
                df_filtered = df_filtered[df_filtered['Площадка'].astype(str).str.strip().str.lower().isin(VALID_PLATFORMS)]
                df_filtered = df_filtered[~df_filtered['Артикул поставщика'].isin(BLACKLIST)]

                def should_include_clearance(row):
                    if row['is_clearance']:
                        reviews = row['Отзывы_число']
                        rating = row['Рейтинг_число']
                        if pd.notna(reviews) and reviews > 2:
                            return False
                        if pd.notna(rating) and rating > 3.9:
                            return False
                    return True

                df_filtered = df_filtered[df_filtered.apply(should_include_clearance, axis=1)]

                df_filtered['Приоритет'] = df_filtered.apply(get_priority, axis=1)
                df_problems = df_filtered[df_filtered['Приоритет'] <= 4].copy()

                if df_problems.empty:
                    st.warning("⚠️ Проблемных артикулов не обнаружено.")
                else:
                    sku_priority = df_problems.groupby('Артикул поставщика')['Приоритет'].min().reset_index()
                    sku_priority.rename(columns={'Приоритет': 'Финальный_Приоритет'}, inplace=True)
                    df_problems = df_problems.merge(sku_priority, on='Артикул поставщика')
                    df_problems['Приоритет'] = df_problems['Финальный_Приоритет']

                    df_problems['Сезонный'] = df_problems['Наименование'].astype(str).str.lower().apply(
                        lambda name: any(kw in name for kw in SEASONAL_KEYWORDS)
                    )

                    def get_sort_key(row):
                        if row['Приоритет'] != 4:
                            return 0
                        name = str(row['Наименование']).lower()
                        if any(kw in name for kw in SEASONAL_KEYWORDS):
                            return 1
                        if any(kw in name for kw in LAMP_KEYWORDS):
                            return 2
                        return 3

                    df_problems['Сортировка_4'] = df_problems.apply(get_sort_key, axis=1)

                    df_problems.sort_values(
                        by=['Приоритет', 'Сортировка_4', 'Рейтинг_число'], 
                        ascending=[True, True, True], 
                        inplace=True
                    )

                    final_df = df_problems.head(100).copy()
                    final_df['Рекомендация'] = final_df.apply(get_recommendation, axis=1)
                    final_df['В общем нужно'] = final_df.apply(calculate_needed_fives, axis=1)

                    # ==================== ДАШБОРД ====================
                    st.markdown("---")
                    st.subheader("📊 Дашборд")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🔴 Приоритет 1 (≤3.9)", len(final_df[final_df['Приоритет'] == 1]))
                    with col2:
                        st.metric("🟠 Приоритет 2 (спад)", len(final_df[final_df['Приоритет'] == 2]))
                    with col3:
                        st.metric("🟡 Приоритет 3 (≤4.5 + <3 отзывов)", len(final_df[final_df['Приоритет'] == 3]))
                    with col4:
                        st.metric("🔵 Приоритет 4 (риск/сезон)", len(final_df[final_df['Приоритет'] == 4]))

                    st.write(f"**Всего проблемных площадок в работе:** {len(final_df)} | **Исключено из чёрного списка:** {len(BLACKLIST)}")

                    # ==================== ТАБЛИЦА ====================
                    st.markdown("---")
                    st.subheader("📋 План работы")

                    display_cols = [
                        'Артикул поставщика',
                        'Площадка',
                        'Ссылка',
                        'Наименование',
                        'Статус',
                        'Рейтинг',
                        'Кол-во отзывов',
                        'Приоритет',
                        'Сезонный',
                        'Рекомендация',
                        'В общем нужно'
                    ]
                    output_df = final_df[display_cols].copy()

                    def add_color_emoji(p):
                        if p == 1:
                            return "🔴 1"
                        elif p == 2:
                            return "🟠 2"
                        elif p == 3:
                            return "🟡 3"
                        elif p == 4:
                            return "🔵 4"
                        return str(p)

                    output_df['Приоритет'] = output_df['Приоритет'].apply(add_color_emoji)

                    st.dataframe(output_df, use_container_width=True, height=600)

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        output_df.to_excel(writer, index=False, sheet_name='План Отзывов')
                    st.download_button(
                        label="📥 Скачать план в Excel",
                        data=buffer.getvalue(),
                        file_name="План_работ_по_рейтингам.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

    except Exception as e:
        st.error(f"Ошибка: {e}")
