import streamlit as st
import pandas as pd
import numpy as np
import io
import os

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

# Люстры и светильники (второй уровень сортировки)
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

def get_priority(row):
    rating = row['Рейтинг_число']
    prev_rating = row['Предыдущий_рейтинг_число']
    reviews = row['Отзывы_число']
    
    if pd.notna(rating) and rating <= 3.9:
        return 1
    if pd.notna(rating) and rating >= 4.0 and pd.notna(prev_rating) and rating < prev_rating:
        return 2
    if pd.notna(rating) and rating <= 4.5 and (pd.isna(reviews) or reviews <= 5):
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

# ==================== ИНТЕРФЕЙС ====================
st.set_page_config(page_title="Аналитика Рейтингов 4.5+", layout="wide")
st.title("⚡ Автоматизация отбора артикулов для работы с рейтингом")
st.caption("Цель: 4.5+ на всех площадках | Чёрный список: " + str(len(BLACKLIST)) + " артикулов")

uploaded_file = st.file_uploader("📁 Загрузите еженедельный отчет (CSV или Excel)", type=['csv', 'xlsx'])
st.image("logo.png", use_container_width=True)

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

        required_cols = ['Артикул поставщика', 'Статус', 'Площадка', 'Рейтинг', 'Кол-во отзывов', 'Предыдущий рейтинг', 'Наименование']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.error(f"❌ Не найдены колонки: {', '.join(missing_cols)}")
        else:
            with st.spinner("🔄 Анализируем данные..."):
                df['Рейтинг_число'] = df['Рейтинг'].apply(clean_numeric)
                df['Отзывы_число'] = df['Кол-во отзывов'].apply(clean_numeric)
                df['Предыдущий_рейтинг_число'] = df['Предыдущий рейтинг'].apply(clean_numeric)

                df_filtered = df[df['Статус'].apply(check_status)].copy()
                df_filtered = df_filtered[df_filtered['Площадка'].astype(str).str.strip().str.lower().isin(VALID_PLATFORMS)]
                df_filtered = df_filtered[~df_filtered['Артикул поставщика'].isin(BLACKLIST)]

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

                                        # Сезонность
                    df_problems['Сезонный'] = df_problems['Наименование'].astype(str).str.lower().apply(
                        lambda name: any(kw in name for kw in SEASONAL_KEYWORDS)
                    )

                    # Новая сортировка для приоритета 4
                    def get_sort_key(row):
                        if row['Приоритет'] != 4:
                            return 0
                        name = str(row['Наименование']).lower()
                        
                        # 1. Сезонные товары (весна-лето)
                        if any(kw in name for kw in SEASONAL_KEYWORDS):
                            return 1
                        
                        # 2. Люстры и светильники
                        if any(kw in name for kw in LAMP_KEYWORDS):
                            return 2
                        
                        # 3. Остальное
                        return 3

                    df_problems['Сортировка_4'] = df_problems.apply(get_sort_key, axis=1)

                    # Сортировка
                    df_problems.sort_values(
                        by=['Приоритет', 'Сортировка_4', 'Рейтинг_число'], 
                        ascending=[True, True, True], 
                        inplace=True
                    )

                    unique_skus = df_problems['Артикул поставщика'].unique()[:150]
                    final_df = df_problems[df_problems['Артикул поставщика'].isin(unique_skus)].copy()

                    final_df['Рекомендация'] = final_df.apply(get_recommendation, axis=1)

                    # ==================== ДАШБОРД ====================
                    st.markdown("---")
                    st.subheader("📊 Дашборд")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🔴 Приоритет 1 (≤3.9)", len(final_df[final_df['Приоритет'] == 1]))
                    with col2:
                        st.metric("🟠 Приоритет 2 (спад)", len(final_df[final_df['Приоритет'] == 2]))
                    with col3:
                        st.metric("🟡 Приоритет 3 (≤4.5 + мало отзывов)", len(final_df[final_df['Приоритет'] == 3]))
                    with col4:
                        st.metric("🔵 Приоритет 4 (риск/сезон)", len(final_df[final_df['Приоритет'] == 4]))

                    st.write(f"**Всего уникальных артикулов в работе:** {len(unique_skus)} | **Исключено из чёрного списка:** {len(BLACKLIST)}")

                    # ==================== ТАБЛИЦА ====================
                    st.markdown("---")
                    st.subheader("📋 План работы")

                    display_cols = required_cols + ['Приоритет', 'Сезонный', 'Рекомендация']
                    output_df = final_df[display_cols].copy()

                    # Цветовая индикация через эмодзи
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

                    # Кнопка скачивания
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
