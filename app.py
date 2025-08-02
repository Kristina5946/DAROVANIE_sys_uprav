# Import necessary libraries
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from collections import defaultdict
import uuid
import csv
from io import StringIO

# --- Configuration and Data Storage ---
# Use JSON file for persistent data storage
DATA_FILE = 'center_data.json'
MEDIA_FOLDER = 'media'
st.set_page_config(layout="wide", page_title="Детский центр - Управление")

# User authentication data (for a small, local app)
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "teacher": {"password": "teacher123", "role": "teacher"},
    "reception": {"password": "reception123", "role": "reception"}
}

# Check if the data file exists, if not, create a new one with an empty structure
if not os.path.exists(DATA_FILE):
    initial_data = {
        'news': [],
        'directions': [],
        'students': [],
        'teachers': [],
        'parents': [],
        'payments': [],
        'schedule': [],
        'materials': [],
        'attendance': {},
        'kanban_tasks': {
            'ToDo': [],
            'InProgress': [],
            'Done': []
        },
        'settings': {
            'trial_cost': 500,
            'single_cost_multiplier': 1.5
        }
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, ensure_ascii=False, indent=4)

# Ensure the media folder exists
if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)

# Load data from JSON file
def load_data():
    """Load data from the JSON file."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Save data to JSON file
def save_data(data):
    """Save data to the JSON file."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Initialize session state for the app
if 'data' not in st.session_state:
    st.session_state.data = load_data()
    # Initialize all required keys if they don't exist
    required_keys = {
        'directions': [],
        'students': [],
        'teachers': [],
        'parents': [],
        'payments': [],
        'schedule': [],
        'materials': [],
        'kanban_tasks': {'ToDo': [], 'InProgress': [], 'Done': []},
        'attendance': {},
        'settings': {'trial_cost': 500, 'single_cost_multiplier': 1.5}
    }
    
    for key, default_value in required_keys.items():
        if key not in st.session_state.data:
            st.session_state.data[key] = default_value

# Initialize other session state variables
session_vars = {
    'page': 'login',
    'authenticated': False,
    'username': None,
    'role': None,
    'selected_teacher_id': None,
    'edit_student_id': None,
    'edit_direction_id': None,
    'edit_teacher_id': None,
    'direction_view_mode': 'table',
    'selected_date': datetime.now().date(),
    'show_clear_confirm': False,
    'bulk_upload_type': 'directions'
}

for var, default in session_vars.items():
    if var not in st.session_state:
        st.session_state[var] = default

# --- Authentication Functions ---
def login(username, password):
    """Handles user login."""
    if username in USERS and USERS[username]['password'] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.role = USERS[username]['role']
        st.success(f"Добро пожаловать, {username}!")
        st.session_state.page = 'home'  
        st.rerun()
    else:
        st.error("Неверное имя пользователя или пароль.")

def logout():
    """Handles user logout."""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.page = 'login'
    st.info("Вы вышли из системы.")
    st.rerun()

# --- Helper Functions ---
def get_student_by_id(student_id):
    """Get student by ID."""
    return next((s for s in st.session_state.data['students'] if s['id'] == student_id), None)

def get_direction_by_id(direction_id):
    """Get direction by ID."""
    return next((d for d in st.session_state.data['directions'] if d['id'] == direction_id), None)

def get_teacher_by_id(teacher_id):
    """Get teacher by ID."""
    return next((t for t in st.session_state.data['teachers'] if t['id'] == teacher_id), None)

def get_parent_by_id(parent_id):
    """Get parent by ID."""
    return next((p for p in st.session_state.data['parents'] if p['id'] == parent_id), None)

def get_students_by_direction(direction_name):
    """Get students attending a specific direction."""
    return [s for s in st.session_state.data['students'] if direction_name in s['directions']]

def get_schedule_by_day(day):
    """Get schedule entries for a specific day."""
    return [s for s in st.session_state.data['schedule'] if s['day'] == day]

def calculate_age(birth_date):
    """Calculate age from birth date."""
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def suggest_directions(age, gender=None):
    """Suggest directions based on age and optional gender."""
    suitable = []
    for direction in st.session_state.data['directions']:
        min_age = direction.get('min_age', 0)
        max_age = direction.get('max_age', 18)
        if min_age <= age <= max_age:
            if not gender or not direction.get('gender') or direction.get('gender') == gender:
                suitable.append(direction)
    return suitable

# --- Page Content Functions ---
def show_home_page():
    """Главная страница с обложкой, расписанием и новостями."""
    st.header("🏠 Главная страница")
    
    # --- Обложка центра ---
    st.subheader("🏞️ Обложка центра")
    cover_folder = os.path.join(MEDIA_FOLDER, "covers")
    os.makedirs(cover_folder, exist_ok=True)
    
    # Загрузка новой обложки
    with st.expander("Изменить обложку"):
        uploaded_cover = st.file_uploader("Выберите новую обложку", type=["jpg", "jpeg", "png"])
        if uploaded_cover:
            cover_path = os.path.join(cover_folder, "current_cover.jpg")
            with open(cover_path, "wb") as f:
                f.write(uploaded_cover.getbuffer())
            st.success("Обложка обновлена!")
            st.rerun()
    
    # Отображение текущей обложки
    cover_path = os.path.join(cover_folder, "current_cover.jpg")
    if os.path.exists(cover_path):
        st.image(cover_path, use_column_width=True)
    else:
        st.info("Загрузите обложку центра")
    
    # --- Расписание на неделю ---
    st.subheader("📅 Расписание на неделю")
    
    # Группировка расписания по дням недели
    schedule_by_day = defaultdict(list)
    for lesson in st.session_state.data['schedule']:
        schedule_by_day[lesson['day']].append(lesson)
    
    days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    # Отображение расписания по дням
    for day in days_order:
        if day in schedule_by_day:
            with st.expander(f"{day}", expanded=True):
                lessons = schedule_by_day[day]
                lessons.sort(key=lambda x: x['start_time'])
                
                for lesson in lessons:
                    students_count = len([s for s in st.session_state.data['students'] 
                                       if lesson['direction'] in s['directions']])
                    st.write(f"⏰ {lesson['start_time']}-{lesson['end_time']}: "
                            f"**{lesson['direction']}** (преп. {lesson['teacher']}) "
                            f"👥 {students_count} учеников")
    
    # --- Генератор сообщений WhatsApp ---
    st.subheader("💬 Генератор сообщений WhatsApp")
    
    selected_day = st.selectbox("Выберите день для сообщения", days_order)
    sticker_options = ["🪻", "🌸", "🌼", "🌺", "🌷", "💐", "🌹", "🌻", "🌞", "🌈"]
    selected_sticker = st.selectbox("Выберите стикер", sticker_options)
    
    if st.button("Сгенерировать сообщение"):
        lessons_today = [l for l in st.session_state.data['schedule'] if l['day'] == selected_day]
        if lessons_today:
            message = f"Доброе утро!{selected_sticker}\nПриглашаем сегодня на занятия:\n"
            
            lessons_today.sort(key=lambda x: x['start_time'])
            for lesson in lessons_today:
                age_info = next((d['min_age'] for d in st.session_state.data['directions'] 
                               if d['name'] == lesson['direction']), None)
                age_text = f" (с {age_info} лет)" if age_info else ""
                message += f"{lesson['start_time']} - {lesson['direction']}{age_text}\n"
            
            st.text_area("Сообщение для WhatsApp", message, height=200)
            
            # Кнопка для копирования
            st.markdown(f"""
            <a href="https://wa.me/?text={message.replace('\n', '%0A')}" target="_blank">
                <button style="background-color:#25D366;color:white;border:none;padding:10px 20px;border-radius:5px;">
                    Открыть в WhatsApp
                </button>
            </a>
            """, unsafe_allow_html=True)
        else:
            st.warning("На выбранный день нет занятий")
    
    # --- Новостная лента ---
    st.subheader("📰 Новостная лента")
    news_folder = os.path.join(MEDIA_FOLDER, "news")
    os.makedirs(news_folder, exist_ok=True)
    
    # Загрузка новых новостей
    with st.expander("Добавить новость"):
        with st.form("news_form"):
            news_text = st.text_area("Текст новости")
            news_media = st.file_uploader("Изображение/документ", type=["jpg", "jpeg", "png", "pdf"])
            submitted = st.form_submit_button("Опубликовать")
            
            if submitted and news_text:
                news_id = str(uuid.uuid4())
                news_data = {
                    "id": news_id,
                    "text": news_text,
                    "date": str(date.today()),
                    "author": st.session_state.username
                }
                
                if news_media:
                    ext = os.path.splitext(news_media.name)[1]
                    media_path = os.path.join(news_folder, f"{news_id}{ext}")
                    with open(media_path, "wb") as f:
                        f.write(news_media.getbuffer())
                    news_data["media"] = f"{news_id}{ext}"
                
                if "news" not in st.session_state.data:
                    st.session_state.data["news"] = []
                
                st.session_state.data["news"].insert(0, news_data)
                save_data(st.session_state.data)
                st.success("Новость добавлена!")
                st.rerun()
    
    # Отображение новостей
    if "news" in st.session_state.data and st.session_state.data["news"]:
        for news in st.session_state.data["news"][:5]:  # Показываем последние 5 новостей
            with st.container(border=True):
                st.write(f"**{news['date']}** (автор: {news.get('author', 'администратор')})")
                st.write(news['text'])
                
                if "media" in news:
                    media_path = os.path.join(news_folder, news["media"])
                    if os.path.exists(media_path):
                        if news["media"].lower().endswith(('.png', '.jpg', '.jpeg')):
                            st.image(media_path, use_column_width=True)
                        elif news["media"].lower().endswith('.pdf'):
                            with open(media_path, "rb") as f:
                                st.download_button(
                                    label="📄 Скачать PDF",
                                    data=f,
                                    file_name=news["media"],
                                    mime="application/pdf"
                                )
                
                if st.button("Удалить", key=f"del_news_{news['id']}"):
                    st.session_state.data["news"] = [n for n in st.session_state.data["news"] if n['id'] != news['id']]
                    if "media" in news:
                        media_path = os.path.join(news_folder, news["media"])
                        if os.path.exists(media_path):
                            os.remove(media_path)
                    save_data(st.session_state.data)
                    st.success("Новость удалена!")
                    st.rerun()
    else:
        st.info("Пока нет новостей")
def show_directions_page():
    """Page to manage courses and directions."""
    st.header("🎨 Управление направлениями")
    
    # Add new direction form
    with st.expander("➕ Добавить новое направление", expanded=False):
        with st.form("new_direction_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                direction_name = st.text_input("Название направления*", key="new_direction_name")
                description = st.text_area("Описание", key="new_direction_description")
                cost = st.number_input("Стоимость абонемента (руб)*", min_value=0.0, step=1.0, value=3000.0)
            with col2:
                min_age = st.number_input("Минимальный возраст", min_value=0, max_value=18, value=3)
                max_age = st.number_input("Максимальный возраст", min_value=0, max_value=18, value=12)
                gender = st.selectbox("Рекомендуемый пол", ["Любой", "Мальчик", "Девочка"])
                trial_cost = st.number_input("Стоимость пробного занятия", min_value=0.0, step=1.0, value=500.0)
            
            submitted = st.form_submit_button("Добавить направление")
            if submitted:
                if direction_name:
                    new_direction = {
                        'id': str(uuid.uuid4()),
                        'name': direction_name,
                        'description': description,
                        'cost': cost,
                        'trial_cost': trial_cost,
                        'min_age': min_age,
                        'max_age': max_age,
                        'gender': gender if gender != "Любой" else None
                    }
                    st.session_state.data['directions'].append(new_direction)
                    save_data(st.session_state.data)
                    st.success(f"Направление '{direction_name}' успешно добавлено!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, заполните обязательные поля (отмечены *)")

    st.subheader("📋 Список направлений")
    view_mode = st.radio("Режим просмотра:", ["Таблица", "Карточки"], horizontal=True)
    
    if st.session_state.data['directions']:
        if view_mode == "Таблица":
            # Table view with data editor
            df_directions = pd.DataFrame(st.session_state.data['directions'])
            df_directions = df_directions.drop(columns=['id'], errors='ignore')
            edited_df = st.data_editor(df_directions, num_rows='dynamic', use_container_width=True)
            
            if st.button("💾 Сохранить изменения"):
                st.session_state.data['directions'] = edited_df.to_dict('records')
                save_data(st.session_state.data)
                st.success("Изменения сохранены!")
                st.rerun()
        
        else:  # Card view
            cols = st.columns(3)
            for i, d in enumerate(st.session_state.data['directions']):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(d['name'])
                        st.write(f"**Возраст:** {d.get('min_age', '?')}-{d.get('max_age', '?')} лет")
                        st.write(f"**Абонемент:** {d['cost']} руб.")
                        st.write(f"**Пробное:** {d.get('trial_cost', '?')} руб.")
                        
                        with st.expander("Подробнее"):
                            st.write(d['description'])
                            st.write(f"**Рекомендуемый пол:** {d.get('gender', 'Любой')}")
                            
                            # Students attending this direction
                            students = get_students_by_direction(d['name'])
                            if students:
                                st.write(f"**Учеников:** {len(students)}")
                                if st.button("Список учеников", key=f"students_{d['id']}"):
                                    st.session_state.page = 'students'
                                    st.session_state.filter_direction = d['name']
                                    st.rerun()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✏️ Ред.", key=f"edit_dir_{d['id']}"):
                                st.session_state.edit_direction_id = d['id']
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Удалить", key=f"del_dir_{d['id']}"):
                                st.session_state.data['directions'] = [item for item in st.session_state.data['directions'] if item['id'] != d['id']]
                                save_data(st.session_state.data)
                                st.success("Направление удалено!")
                                st.rerun()
    else:
        st.info("Пока нет добавленных направлений.")

    if st.session_state.edit_direction_id:
        direction = get_direction_by_id(st.session_state.edit_direction_id)
        if direction:
            with st.form("edit_direction_form"):
                st.subheader(f"Редактирование: {direction['name']}")
                new_name = st.text_input("Название", value=direction['name'])
                new_desc = st.text_area("Описание", value=direction.get('description', ''))
                new_cost = st.number_input("Стоимость", value=direction['cost'])
                
                if st.form_submit_button("Сохранить"):
                    direction['name'] = new_name
                    direction['description'] = new_desc
                    direction['cost'] = new_cost
                    save_data(st.session_state.data)
                    st.session_state.edit_direction_id = None
                    st.success("Изменения сохранены!")
                    st.rerun()
                
                if st.form_submit_button("Отмена"):
                    st.session_state.edit_direction_id = None
                    st.rerun()

def show_students_page():
    """Page to manage students and payments."""
    st.header("👦👧 Ученики и оплаты")
    
    # Filter students by direction if set
    if hasattr(st.session_state, 'filter_direction'):
        filtered_students = [s for s in st.session_state.data['students'] if st.session_state.filter_direction in s['directions']]
        st.info(f"Показаны ученики направления: {st.session_state.filter_direction}")
        if st.button("Показать всех учеников"):
            del st.session_state.filter_direction
            st.rerun()
    else:
        filtered_students = st.session_state.data['students']

    # Form to add a new student
    with st.expander("➕ Добавить нового ученика", expanded=False):
        with st.form("new_student_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input("ФИО ученика*")
                dob = st.date_input("Дата рождения*", value=date.today(), max_value=date.today())
                gender = st.selectbox("Пол", ["Мальчик", "Девочка"])
                notes = st.text_area("Дополнительная информация")
            with col2:
                # Parent selection
                parent_options = {p['id']: f"{p['name']} ({p.get('phone', 'нет телефона')})" 
                                 for p in st.session_state.data['parents']}
                selected_parent_id = st.selectbox(
                    "Выберите родителя", 
                    options=[None] + list(parent_options.keys()), 
                    format_func=lambda x: parent_options.get(x, "Новый родитель")
                )
                
                # New parent fields
                new_parent_name = st.text_input("ФИО родителя (если новый)")
                new_parent_phone = st.text_input("Телефон родителя")
                
                # Directions selection
                available_directions = [d['name'] for d in st.session_state.data['directions']]
                selected_directions = st.multiselect("Направления", available_directions)
            
            submitted = st.form_submit_button("Добавить ученика")
            if submitted:
                if student_name and dob:
                    parent_id = selected_parent_id
                    if (new_parent_name and new_parent_phone) or not parent_id:
                        new_parent = {
                            'id': str(uuid.uuid4()),
                            'name': new_parent_name if new_parent_name else f"Родитель {student_name}",
                            'phone': new_parent_phone,
                            'children_ids': []
                        }
                        st.session_state.data['parents'].append(new_parent)
                        parent_id = new_parent['id']
                    
                    new_student = {
                        'id': str(uuid.uuid4()),
                        'name': student_name,
                        'dob': str(dob),
                        'gender': gender,
                        'parent_id': parent_id,
                        'directions': selected_directions,
                        'notes': notes,
                        'registration_date': str(date.today())
                    }
                    st.session_state.data['students'].append(new_student)
                    
                    # Link child to parent
                    for p in st.session_state.data['parents']:
                        if p['id'] == parent_id:
                            p['children_ids'].append(new_student['id'])
                            break
                    
                    save_data(st.session_state.data)
                    st.success(f"Ученик '{student_name}' успешно добавлен!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, заполните обязательные поля (ФИО и дата рождения)")

    st.subheader("📋 Список учеников")
    if filtered_students:
        # Create DataFrame for display
        df_students = pd.DataFrame(filtered_students)
        
        # Map parent_id to parent_name for display
        parent_id_to_name = {p['id']: p['name'] for p in st.session_state.data['parents']}
        df_students['parent'] = df_students['parent_id'].map(parent_id_to_name)
        
        # Calculate ages
        df_students['age'] = pd.to_datetime(df_students['dob']).apply(
            lambda x: calculate_age(x.date()))
        
        # Select columns to display
        display_cols = ['name', 'age', 'gender', 'parent', 'directions', 'notes']
        df_display = df_students[display_cols].copy()
        df_display['directions'] = df_display['directions'].apply(lambda x: ', '.join(x))
        
        # Data editor
        edited_df = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": "ФИО",
                "age": "Возраст",
                "gender": "Пол",
                "parent": "Родитель",
                "directions": "Направления",
                "notes": "Заметки"
            }
        )
        
        if st.button("💾 Сохранить изменения учеников"):
            # Update student data from edited DataFrame
            for idx, row in edited_df.iterrows():
                student_id = filtered_students[idx]['id']
                for s in st.session_state.data['students']:
                    if s['id'] == student_id:
                        s['name'] = row['name']
                        s['gender'] = row['gender']
                        s['notes'] = row['notes']
                        # Directions need special handling as they're a list
                        if isinstance(row['directions'], str):
                            s['directions'] = [d.strip() for d in row['directions'].split(',') if d.strip()]
                        break
            
            save_data(st.session_state.data)
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Нет учеников для отображения.")

    # Payments section
    st.subheader("💳 Оплаты")
    if filtered_students:
        student_options = {s['id']: s['name'] for s in filtered_students}
        selected_student_id = st.selectbox(
            "Выберите ученика для добавления оплаты",
            options=list(student_options.keys()),
            format_func=lambda x: student_options[x]
        )
        
        with st.form("new_payment_form"):
            col1, col2 = st.columns(2)
            with col1:
                payment_date = st.date_input("Дата оплаты", value=date.today())
                amount = st.number_input("Сумма (руб)", min_value=0.0, step=100.0)
            with col2:
                direction = st.selectbox(
                    "Направление",
                    options=[d['name'] for d in st.session_state.data['directions']]
                )
                payment_type = st.selectbox(
                    "Тип оплаты",
                    ["Абонемент", "Пробное", "Разовое"]
                )
            
            notes = st.text_input("Примечание")
            
            if st.form_submit_button("Добавить оплату"):
                new_payment = {
                    'id': str(uuid.uuid4()),
                    'student_id': selected_student_id,
                    'date': str(payment_date),
                    'amount': amount,
                    'direction': direction,
                    'type': payment_type,
                    'notes': notes
                }
                st.session_state.data['payments'].append(new_payment)
                save_data(st.session_state.data)
                st.success("Оплата добавлена!")
                st.rerun()
    
    # Display payments for selected students
    if filtered_students:
        payments = [p for p in st.session_state.data['payments'] 
                   if p['student_id'] in [s['id'] for s in filtered_students]]
        
        if payments:
            df_payments = pd.DataFrame(payments)
            df_payments['student'] = df_payments['student_id'].apply(
                lambda x: next(s['name'] for s in st.session_state.data['students'] if s['id'] == x)
            )
            st.dataframe(
                df_payments[['student', 'date', 'amount', 'direction', 'type', 'notes']],
                use_container_width=True
            )
        else:
            st.info("Нет данных по оплатам для выбранных учеников.")

def show_teachers_page():
    """Page to manage teachers."""
    st.header("👩‍🏫 Преподаватели")
    
    # Form to add a new teacher
    with st.expander("➕ Добавить нового преподавателя", expanded=False):
        with st.form("new_teacher_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                teacher_name = st.text_input("ФИО преподавателя*")
                teacher_phone = st.text_input("Телефон")
                teacher_email = st.text_input("Email")
            with col2:
                teacher_directions = st.multiselect(
                    "Направления",
                    [d['name'] for d in st.session_state.data['directions']]
                )
                teacher_notes = st.text_area("Дополнительная информация")
            
            submitted = st.form_submit_button("Добавить преподавателя")
            if submitted:
                if teacher_name:
                    new_teacher = {
                        'id': str(uuid.uuid4()),
                        'name': teacher_name,
                        'phone': teacher_phone,
                        'email': teacher_email,
                        'directions': teacher_directions,
                        'notes': teacher_notes,
                        'hire_date': str(date.today())
                    }
                    st.session_state.data['teachers'].append(new_teacher)
                    save_data(st.session_state.data)
                    st.success(f"Преподаватель '{teacher_name}' добавлен.")
                    st.rerun()
                else:
                    st.error("Пожалуйста, введите ФИО преподавателя.")

    st.subheader("📋 Список преподавателей")
    if st.session_state.data['teachers']:
        df_teachers = pd.DataFrame(st.session_state.data['teachers'])
        
        # Convert directions list to string for display
        df_teachers['directions'] = df_teachers['directions'].apply(lambda x: ', '.join(x))
        
        # Select columns to display
        display_cols = ['name', 'phone', 'email', 'directions', 'notes']
        df_display = df_teachers[display_cols].copy()
        
        # Data editor
        edited_df = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": "ФИО",
                "phone": "Телефон",
                "email": "Email",
                "directions": "Направления",
                "notes": "Заметки"
            }
        )
        
        if st.button("💾 Сохранить изменения"):
            # Update teacher data from edited DataFrame
            for idx, row in edited_df.iterrows():
                teacher_id = st.session_state.data['teachers'][idx]['id']
                for t in st.session_state.data['teachers']:
                    if t['id'] == teacher_id:
                        t['name'] = row['name']
                        t['phone'] = row['phone']
                        t['email'] = row['email']
                        t['notes'] = row['notes']
                        # Directions need special handling as they're a list
                        if isinstance(row['directions'], str):
                            t['directions'] = [d.strip() for d in row['directions'].split(',') if d.strip()]
                        break
            
            save_data(st.session_state.data)
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Пока нет добавленных преподавателей.")

def show_schedule_page():
    """Page for schedule management, attendance, and message generation."""
    st.header("📅 Расписание и посещения")
    
    # Admin can add schedule entries
    if st.session_state.role in ['admin', 'teacher']:
        with st.expander("➕ Добавить занятие в расписание", expanded=False):
            with st.form("new_schedule_form"):
                col1, col2 = st.columns(2)
                with col1:
                    direction_name = st.selectbox(
                        "Направление*",
                        [d['name'] for d in st.session_state.data['directions']]
                    )
                    teacher = st.selectbox(
                        "Преподаватель*",
                        [t['name'] for t in st.session_state.data['teachers']]
                    )
                with col2:
                    start_time = st.time_input("Начало занятия*", value=datetime.strptime("16:00", "%H:%M").time())
                    end_time = st.time_input("Конец занятия*", value=datetime.strptime("17:00", "%H:%M").time())
                    day_of_week = st.selectbox(
                        "День недели*",
                        ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                    )
                
                submitted = st.form_submit_button("Добавить занятие")
                if submitted:
                    if direction_name and teacher and start_time and end_time and day_of_week:
                        new_schedule_entry = {
                            'id': str(uuid.uuid4()),
                            'direction': direction_name,
                            'teacher': teacher,
                            'start_time': str(start_time),
                            'end_time': str(end_time),
                            'day': day_of_week
                        }
                        st.session_state.data['schedule'].append(new_schedule_entry)
                        save_data(st.session_state.data)
                        st.success("Занятие добавлено в расписание!")
                        st.rerun()
                    else:
                        st.error("Пожалуйста, заполните все обязательные поля (отмечены *)")

    # Calendar view for attendance
    st.subheader("🗓️ Календарь занятий")
    selected_date = st.date_input("Выберите дату", value=st.session_state.selected_date)
    st.session_state.selected_date = selected_date
    day_of_week = selected_date.strftime("%A")
    
    # Translate day names to Russian
    day_translation = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }
    russian_day = day_translation.get(day_of_week, day_of_week)
    
    # Get schedule for this day
    day_schedule = [s for s in st.session_state.data['schedule'] if s['day'] == russian_day]
    
    if day_schedule:
        st.write(f"Занятия на {selected_date.strftime('%d.%m.%Y')} ({russian_day}):")
        
        for lesson in day_schedule:
            with st.expander(f"{lesson['direction']} ({lesson['start_time']}-{lesson['end_time']}, {lesson['teacher']})"):
                # Get students for this direction
                students = [s for s in st.session_state.data['students'] 
                           if lesson['direction'] in s['directions']]
                
                if students:
                    # Check if attendance record exists for this date and lesson
                    date_key = selected_date.strftime("%Y-%m-%d")
                    lesson_key = lesson['id']
                    
                    if date_key not in st.session_state.data['attendance']:
                        st.session_state.data['attendance'][date_key] = {}
                    
                    if lesson_key not in st.session_state.data['attendance'][date_key]:
                        st.session_state.data['attendance'][date_key][lesson_key] = {}
                    
                    attendance_records = st.session_state.data['attendance'][date_key][lesson_key]
                    
                    # Attendance table
                    st.write("Отметить посещения:")
                    cols = st.columns([3, 1, 1, 2])
                    cols[0].write("**Ученик**")
                    cols[1].write("**Присут.**")
                    cols[2].write("**Оплата**")
                    cols[3].write("**Примечание**")
                    
                    for student in students:
                        student_id = student['id']
                        student_name = student['name']
                        
                        # Get current attendance status
                        current_status = attendance_records.get(student_id, {'present': False, 'paid': False, 'note': ''})
                        
                        cols = st.columns([3, 1, 1, 2])
                        cols[0].write(student_name)
                        
                        # Present checkbox
                        present = cols[1].checkbox(
                            "Присутствовал",
                            value=current_status['present'],
                            key=f"present_{lesson_key}_{student_id}",
                            label_visibility="collapsed"
                        )
                        
                        # Paid checkbox
                        paid = cols[2].checkbox(
                            "Оплачено",
                            value=current_status['paid'],
                            key=f"paid_{lesson_key}_{student_id}",
                            label_visibility="collapsed"
                        )
                        
                        # Note field
                        note = cols[3].text_input(
                            "Примечание",
                            value=current_status.get('note', ''),
                            key=f"note_{lesson_key}_{student_id}",
                            label_visibility="collapsed"
                        )
                        
                        # Update attendance record
                        attendance_records[student_id] = {
                            'present': present,
                            'paid': paid,
                            'note': note
                        }
                    
                    # Save attendance button
                    if st.button("Сохранить посещения", key=f"save_att_{lesson_key}"):
                        save_data(st.session_state.data)
                        st.success("Данные посещений сохранены!")
                        st.rerun()
                else:
                    st.info("Нет учеников, записанных на это направление.")
    else:
        st.info(f"На {russian_day} нет запланированных занятий.")

def show_materials_page():
    """Page to manage materials and purchases."""
    st.header("🛍️ Материалы и закупки")
    
    # Add new material form
    with st.expander("➕ Добавить материал/закупку", expanded=False):
        with st.form("new_material_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                material_name = st.text_input("Название материала*")
                cost = st.number_input("Стоимость (руб)*", min_value=0.0, step=1.0)
                direction = st.selectbox(
                    "Направление",
                    [d['name'] for d in st.session_state.data['directions']]
                )
            with col2:
                purchase_date = st.date_input("Дата закупки*", value=date.today())
                quantity = st.number_input("Количество", min_value=1, value=1)
                supplier = st.text_input("Поставщик")
                link = st.text_input("Ссылка на заказ")
            
            submitted = st.form_submit_button("Добавить материал")
            if submitted:
                if material_name and cost and purchase_date:
                    new_material = {
                        'id': str(uuid.uuid4()),
                        'name': material_name,
                        'cost': cost,
                        'quantity': quantity,
                        'total_cost': cost * quantity,
                        'direction': direction,
                        'date': str(purchase_date),
                        'supplier': supplier,
                        'link': link
                    }
                    st.session_state.data['materials'].append(new_material)
                    save_data(st.session_state.data)
                    st.success("Материал успешно добавлен!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, заполните обязательные поля (отмечены *)")

    st.subheader("📋 Список материалов")
    if st.session_state.data['materials']:
        df_materials = pd.DataFrame(st.session_state.data['materials'])
        
        # Convert date strings to datetime for sorting
        df_materials['date'] = pd.to_datetime(df_materials['date'])
        
        # Sort by date descending
        df_materials = df_materials.sort_values('date', ascending=False)
        
        # Select columns to display
        display_cols = ['name', 'direction', 'quantity', 'cost', 'total_cost', 'date', 'supplier']
        df_display = df_materials[display_cols].copy()
        
        # Data editor
        edited_df = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": "Название",
                "direction": "Направление",
                "quantity": "Кол-во",
                "cost": "Цена",
                "total_cost": "Сумма",
                "date": "Дата",
                "supplier": "Поставщик"
            }
        )
        
        if st.button("💾 Сохранить изменения"):
            # Update material data from edited DataFrame
            for idx, row in edited_df.iterrows():
                material_id = st.session_state.data['materials'][idx]['id']
                for m in st.session_state.data['materials']:
                    if m['id'] == material_id:
                        m['name'] = row['name']
                        m['direction'] = row['direction']
                        m['quantity'] = row['quantity']
                        m['cost'] = row['cost']
                        m['total_cost'] = row['total_cost']
                        m['date'] = str(row['date'].date())
                        m['supplier'] = row['supplier']
                        break
            
            save_data(st.session_state.data)
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Пока нет добавленных материалов.")

def show_kanban_board():
    """Page to manage kanban tasks."""
    st.header("📌 Канбан-доска")
    
    # Add new task form
    with st.expander("➕ Добавить новую задачу", expanded=False):
        with st.form("new_task_form", clear_on_submit=True):
            task_title = st.text_input("Название задачи*")
            task_description = st.text_area("Описание задачи")
            task_priority = st.selectbox("Приоритет", ["Низкий", "Средний", "Высокий"])
            task_deadline = st.date_input("Срок выполнения")
            task_assignee = st.selectbox(
                "Ответственный",
                [None] + [t['name'] for t in st.session_state.data['teachers']]
            )
            
            submitted = st.form_submit_button("Добавить задачу")
            if submitted:
                if task_title:
                    new_task = {
                        'id': str(uuid.uuid4()),
                        'title': task_title,
                        'description': task_description,
                        'priority': task_priority,
                        'deadline': str(task_deadline) if task_deadline else None,
                        'assignee': task_assignee,
                        'created': str(date.today()),
                        'created_by': st.session_state.username
                    }
                    st.session_state.data['kanban_tasks']['ToDo'].append(new_task)
                    save_data(st.session_state.data)
                    st.success("Задача добавлена!")
                    st.rerun()
                else:
                    st.error("Название задачи не может быть пустым.")

    st.subheader("📋 Текущие задачи")
    cols = st.columns(3)
    status_map = {
        'ToDo': '📋 Не сделано',
        'InProgress': '🔄 В процессе',
        'Done': '✅ Готово'
    }
    
    for status, col in zip(['ToDo', 'InProgress', 'Done'], cols):
        with col:
            st.markdown(f"### {status_map[status]}")
            if st.session_state.data['kanban_tasks'][status]:
                for task in st.session_state.data['kanban_tasks'][status]:
                    with st.container(border=True):
                        # Task header with priority indicator
                        priority_colors = {
                            "Низкий": "blue",
                            "Средний": "orange",
                            "Высокий": "red"
                        }
                        st.markdown(
                            f"**{task['title']}** " 
                            f"<span style='color:{priority_colors.get(task.get('priority', 'Низкий'), 'gray')}'>"
                            f"⬤</span>",
                            unsafe_allow_html=True
                        )
                        
                        # Task details
                        with st.expander("Подробнее"):
                            st.write(task['description'])
                            
                            if task.get('assignee'):
                                st.write(f"**Ответственный:** {task['assignee']}")
                            
                            if task.get('deadline'):
                                deadline_date = datetime.strptime(task['deadline'], "%Y-%m-%d").date()
                                days_left = (deadline_date - date.today()).days
                                deadline_color = "red" if days_left < 0 else ("orange" if days_left < 3 else "green")
                                st.write(
                                    f"**Срок:** <span style='color:{deadline_color}'>"
                                    f"{deadline_date.strftime('%d.%m.%Y')} ({days_left} дн.)</span>",
                                    unsafe_allow_html=True
                                )
                            
                            st.write(f"**Создано:** {task.get('created')} ({task.get('created_by', '?')})")
                        
                        # Task actions
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            next_status = None
                            if status == 'ToDo':
                                if st.button("Начать", key=f"start_{task['id']}"):
                                    next_status = 'InProgress'
                            elif status == 'InProgress':
                                if st.button("Завершить", key=f"complete_{task['id']}"):
                                    next_status = 'Done'
                            
                            if next_status:
                                st.session_state.data['kanban_tasks'][status].remove(task)
                                st.session_state.data['kanban_tasks'][next_status].append(task)
                                save_data(st.session_state.data)
                                st.rerun()
                        with col2:
                            if st.button("🗑️", key=f"del_{task['id']}"):
                                st.session_state.data['kanban_tasks'][status].remove(task)
                                save_data(st.session_state.data)
                                st.rerun()
            else:
                st.info("Нет задач")

def show_media_gallery_page():
    """Page to manage media files."""
    st.header("🖼️ Медиа-галерея")
    
    # Create tabs for different media types
    tab_images, tab_docs, tab_videos = st.tabs(["Фотографии", "Документы", "Видео"])
    
    # Upload section
    with st.expander("⬆️ Загрузить файлы", expanded=False):
        with st.form("upload_media_form"):
            file_type = st.selectbox("Тип файла", ["Фото", "Документ", "Видео"])
            uploaded_files = st.file_uploader(
                "Выберите файлы",
                type=["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "mp4", "mov"],
                accept_multiple_files=True
            )
            
            if st.form_submit_button("Загрузить"):
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        # Create subfolder based on file type
                        subfolder = {
                            "Фото": "images",
                            "Документ": "documents",
                            "Видео": "videos"
                        }.get(file_type, "other")
                        
                        os.makedirs(os.path.join(MEDIA_FOLDER, subfolder), exist_ok=True)
                        file_path = os.path.join(MEDIA_FOLDER, subfolder, uploaded_file.name)
                        
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                    
                    st.success(f"Загружено {len(uploaded_files)} файлов!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, выберите хотя бы один файл")

    # Display media by type
    with tab_images:
        st.subheader("Фотографии мероприятий")
        image_files = []
        for root, _, files in os.walk(os.path.join(MEDIA_FOLDER, "images")):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    image_files.append(os.path.join(root, file))
        
        if image_files:
            cols = st.columns(3)
            for i, img_path in enumerate(image_files):
                with cols[i % 3]:
                    st.image(img_path, use_column_width=True)
                    st.caption(os.path.basename(img_path))
                    if st.button("Удалить", key=f"del_img_{img_path}"):
                        os.remove(img_path)
                        st.success("Файл удален!")
                        st.rerun()
        else:
            st.info("Нет фотографий в галерее.")

    with tab_docs:
        st.subheader("Документы")
        doc_files = []
        for root, _, files in os.walk(os.path.join(MEDIA_FOLDER, "documents")):
            for file in files:
                if file.lower().endswith(('.pdf', '.doc', '.docx')):
                    doc_files.append(os.path.join(root, file))
        
        if doc_files:
            for doc_path in doc_files:
                doc_name = os.path.basename(doc_path)
                st.download_button(
                    label=f"📄 {doc_name}",
                    data=open(doc_path, "rb").read(),
                    file_name=doc_name,
                    mime="application/octet-stream",
                    key=f"doc_{doc_path}"
                )
                if st.button("Удалить", key=f"del_doc_{doc_path}"):
                    os.remove(doc_path)
                    st.success("Файл удален!")
                    st.rerun()
        else:
            st.info("Нет документов в галерее.")

    with tab_videos:
        st.subheader("Видео")
        video_files = []
        for root, _, files in os.walk(os.path.join(MEDIA_FOLDER, "videos")):
            for file in files:
                if file.lower().endswith(('.mp4', '.mov')):
                    video_files.append(os.path.join(root, file))
        
        if video_files:
            for video_path in video_files:
                st.video(video_path)
                st.caption(os.path.basename(video_path))
                if st.button("Удалить", key=f"del_vid_{video_path}"):
                    os.remove(video_path)
                    st.success("Файл удален!")
                    st.rerun()
        else:
            st.info("Нет видео в галерее.")

def show_bulk_upload_page():
    """Page for bulk data upload via CSV."""
    st.header("📤 Массовая загрузка данных")
    
    # Select data type to upload
    data_type = st.selectbox(
        "Тип данных для загрузки",
        ["Направления", "Ученики", "Родители", "Преподаватели", "Материалы","Расписание"]
    )
    
    # Upload CSV file
    uploaded_file = st.file_uploader(
        "Загрузите CSV файл",
        type=["csv"],
        help="Файл должен быть в формате CSV с соответствующими колонками для выбранного типа данных"
    )
    
    if uploaded_file:
        # Read CSV file
        try:
            df = pd.read_csv(uploaded_file)
            st.success("Файл успешно загружен!")
            st.dataframe(df.head())
            
            # Process based on data type
            if st.button("Импортировать данные"):
                try:
                    if data_type == "Направления":
                        required_cols = ['name', 'cost']
                        if all(col in df.columns for col in required_cols):
                            new_directions = []
                            for _, row in df.iterrows():
                                new_direction = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'description': row.get('description', ''),
                                    'cost': float(row['cost']),
                                    'trial_cost': float(row.get('trial_cost', row['cost'] * 0.2)),
                                    'min_age': int(row.get('min_age', 3)),
                                    'max_age': int(row.get('max_age', 12)),
                                    'gender': row.get('gender', None)
                                }
                                new_directions.append(new_direction)
                            
                            st.session_state.data['directions'].extend(new_directions)
                            st.success(f"Добавлено {len(new_directions)} направлений!")
                    
                    elif data_type == "Ученики":
                        required_cols = ['name', 'dob']
                        if all(col in df.columns for col in required_cols):
                            new_students = []
                            for _, row in df.iterrows():
                                new_student = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'dob': row['dob'],
                                    'gender': row.get('gender', 'Мальчик'),
                                    'parent_id': None,  # Will need to handle parents separately
                                    'directions': row.get('directions', '').split(',') if pd.notna(row.get('directions')) else [],
                                    'notes': row.get('notes', ''),
                                    'registration_date': str(date.today())
                                }
                                new_students.append(new_student)
                            
                            st.session_state.data['students'].extend(new_students)
                            st.success(f"Добавлено {len(new_students)} учеников!")
                    
                    elif data_type == "Родители":
                        required_cols = ['name', 'phone']
                        if all(col in df.columns for col in required_cols):
                            new_parents = []
                            for _, row in df.iterrows():
                                new_parent = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'phone': str(row['phone']),
                                    'email': row.get('email', ''),
                                    'children_ids': []
                                }
                                new_parents.append(new_parent)
                            
                            st.session_state.data['parents'].extend(new_parents)
                            st.success(f"Добавлено {len(new_parents)} родителей!")
                    
                    elif data_type == "Преподаватели":
                        required_cols = ['name']
                        if all(col in df.columns for col in required_cols):
                            new_teachers = []
                            for _, row in df.iterrows():
                                # Обработка направлений - разбиваем строку и сопоставляем с существующими направлениями
                                raw_directions = row.get('directions', '')
                                if pd.notna(raw_directions):
                                    # Разбиваем строку направлений по запятым
                                    raw_dir_list = [d.strip() for d in raw_directions.split(',')]
                                    valid_directions = []
                                    
                                    # Сопоставляем с существующими направлениями
                                    for dir_name in raw_dir_list:
                                        # Ищем точное совпадение
                                        exact_match = next((d for d in st.session_state.data['directions'] 
                                                          if d['name'].lower() == dir_name.lower()), None)
                                        if exact_match:
                                            valid_directions.append(exact_match['name'])
                                        else:
                                            # Если точного совпадения нет, ищем частичное
                                            partial_match = next((d for d in st.session_state.data['directions'] 
                                                                if dir_name.lower() in d['name'].lower()), None)
                                            if partial_match:
                                                valid_directions.append(partial_match['name'])
                                    
                                    directions = list(set(valid_directions))  # Удаляем дубликаты
                                else:
                                    directions = []
                                
                                new_teacher = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'phone': str(row.get('phone', '')),
                                    'email': row.get('email', ''),
                                    'directions': directions,
                                    'notes': row.get('notes', ''),
                                    'hire_date': str(date.today())
                                }
                                new_teachers.append(new_teacher)
                            
                            st.session_state.data['teachers'].extend(new_teachers)
                            st.success(f"Добавлено {len(new_teachers)} преподавателей!")
                            
                    
                    elif data_type == "Материалы":
                        required_cols = ['name', 'cost', 'direction']
                        if all(col in df.columns for col in required_cols):
                            new_materials = []
                            for _, row in df.iterrows():
                                new_material = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'cost': float(row['cost']),
                                    'quantity': int(row.get('quantity', 1)),
                                    'total_cost': float(row['cost']) * int(row.get('quantity', 1)),
                                    'direction': row['direction'],
                                    'date': str(date.today()),
                                    'supplier': row.get('supplier', ''),
                                    'link': row.get('link', '')
                                }
                                new_materials.append(new_material)
                            
                            st.session_state.data['materials'].extend(new_materials)
                            st.success(f"Добавлено {len(new_materials)} материалов!")
                    # --- НОВЫЙ БЛОК ДЛЯ РАСПИСАНИЯ ---
                    elif data_type == "Расписание":
                        required_cols = ['direction', 'teacher', 'start_time', 'end_time', 'day']
                        if all(col in df.columns for col in required_cols):
                            new_schedule_entries = []
                            for _, row in df.iterrows():
                                # Проверка существования направления и преподавателя (опционально, но рекомендуется)
                                direction_exists = any(d['name'] == row['direction'] for d in st.session_state.data['directions'])
                                teacher_exists = any(t['name'] == row['teacher'] for t in st.session_state.data['teachers'])

                                if not direction_exists:
                                    st.warning(f"Направление '{row['direction']}' не найдено, занятие будет добавлено, но без привязки к существующему направлению.")
                                if not teacher_exists:
                                    st.warning(f"Преподаватель '{row['teacher']}' не найден, занятие будет добавлено, но без привязки к существующему преподавателю.")
                                
                                new_schedule_entry = {
                                    'id': str(uuid.uuid4()),
                                    'direction': row['direction'],
                                    'teacher': row['teacher'],
                                    'start_time': str(row['start_time']), # Время должно быть в формате HH:MM
                                    'end_time': str(row['end_time']),     # Время должно быть в формате HH:MM
                                    'day': row['day'] # День недели, например "Понедельник"
                                }
                                new_schedule_entries.append(new_schedule_entry)
                            
                            st.session_state.data['schedule'].extend(new_schedule_entries)
                            st.success(f"Добавлено {len(new_schedule_entries)} занятий в расписание!")
                    # --- КОНЕЦ НОВОГО БЛОКА ---
                    
                    save_data(st.session_state.data)
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Ошибка при импорте данных: {str(e)}")
        
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {str(e)}")

def show_payments_report():
    """Page for payments report."""
    st.header("📊 Отчет по оплатам")
    
    if st.session_state.data['payments']:
        df_payments = pd.DataFrame(st.session_state.data['payments'])
        
        # Convert date strings to datetime
        df_payments['date'] = pd.to_datetime(df_payments['date'])
        
        # Add student names
        student_id_to_name = {s['id']: s['name'] for s in st.session_state.data['students']}
        df_payments['student'] = df_payments['student_id'].map(student_id_to_name)
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=df_payments['date'].min().date())
        with col2:
            end_date = st.date_input("Конечная дата", value=df_payments['date'].max().date())
        
        # Filter by date range
        df_filtered = df_payments[
            (df_payments['date'].dt.date >= start_date) & 
            (df_payments['date'].dt.date <= end_date)
        ]
        
        if not df_filtered.empty:
            # Display filtered data
            st.dataframe(
                df_filtered[['student', 'date', 'amount', 'direction', 'type', 'notes']],
                use_container_width=True
            )
            
            # Summary statistics
            total_payments = df_filtered['amount'].sum()
            st.subheader(f"Общая сумма оплат: {total_payments:.2f} руб.")
            
            # Group by direction and type
            st.subheader("Оплаты по направлениям")
            payments_by_direction = df_filtered.groupby('direction')['amount'].sum().reset_index()
            st.bar_chart(payments_by_direction.set_index('direction'))
            
            st.subheader("Оплаты по типам")
            payments_by_type = df_filtered.groupby('type')['amount'].sum().reset_index()
            st.bar_chart(payments_by_type.set_index('type'))
            
            # Export button
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Экспорт в CSV",
                data=csv,
                file_name=f"payments_report_{start_date}_{end_date}.csv",
                mime="text/csv"
            )
        else:
            st.info("Нет данных по оплатам за выбранный период.")
    else:
        st.info("Нет данных по оплатам.")

def show_materials_report():
    """Page for materials report."""
    st.header("📊 Отчет по закупкам")
    
    if st.session_state.data['materials']:
        df_materials = pd.DataFrame(st.session_state.data['materials'])
        
        # Convert date strings to datetime
        df_materials['date'] = pd.to_datetime(df_materials['date'])
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=df_materials['date'].min().date())
        with col2:
            end_date = st.date_input("Конечная дата", value=df_materials['date'].max().date())
        
        # Filter by date range
        df_filtered = df_materials[
            (df_materials['date'].dt.date >= start_date) & 
            (df_materials['date'].dt.date <= end_date)
        ]
        
        if not df_filtered.empty:
            # Display filtered data
            st.dataframe(
                df_filtered[['name', 'direction', 'quantity', 'cost', 'total_cost', 'date', 'supplier']],
                use_container_width=True
            )
            
            # Summary statistics
            total_cost = df_filtered['total_cost'].sum()
            st.subheader(f"Общая сумма затрат: {total_cost:.2f} руб.")
            
            # Group by direction
            st.subheader("Затраты по направлениям")
            materials_by_direction = df_filtered.groupby('direction')['total_cost'].sum().reset_index()
            st.bar_chart(materials_by_direction.set_index('direction'))
            
            # Export button
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Экспорт в CSV",
                data=csv,
                file_name=f"materials_report_{start_date}_{end_date}.csv",
                mime="text/csv"
            )
        else:
            st.info("Нет данных по закупкам за выбранный период.")
    else:
        st.info("Нет данных по закупкам.")

def show_reception_helper():
    """Page for reception helper to suggest directions."""
    st.header("👋 Помощник ресепшена")
    
    # Создаем словарь категорий направлений
    direction_categories = {
        "Языки": ["Английский язык", "Французский язык"],
        "Творчество": [
            "Студия живописи с 4 лет и с 6 лет", 
            "Гончарная мастерская с 5 лет",
            "Театральная студия с 5 лет"
        ],
        "Музыка": [
            "Вокальная студия с 5 лет",
            "Музыкальный ансамбль на разных инструментах",
            "Индивидуальные занятия по гитаре"
        ],
        "Танцы": ["Танцевальная студия с 4 лет"],
        "Наука": [
            "Программирование", 
            "Лаборатория опытов с 6 лет",
            "Индивидуальные занятия по математике"
        ],
        "Подготовка к школе": [
            "Подготовка к школе и ВПР", 
            "Курс \"Пишу красиво\"",
            "Речевая студия \"Говоруша\" (5-7 лет)"
        ],
        "Логопедия": ["Логопедические занятия"],
        "Шахматы": ["Шахматный клуб с 5 лет"],
        "Репетиторство": [
            "Индивидуальные занятия по истории",
            "Индивидуальные занятия по обществознанию",
            "Индивидуальные занятия по русскому языку"
        ]
    }
    
    with st.form("child_info_form"):
        col1, col2 = st.columns(2)
        with col1:
            child_age = st.number_input("Возраст ребенка", min_value=0, max_value=18, value=5)
            gender = st.selectbox("Пол ребенка", ["Мальчик", "Девочка", "Не важно"])
        with col2:
            interests = st.multiselect(
                "Интересы (опционально)",
                list(direction_categories.keys())
            )
        
        if st.form_submit_button("Подобрать направления"):
            # Сначала фильтруем по возрасту и полу
            suitable_directions = suggest_directions(child_age, gender if gender != "Не важно" else None)
            
            # Если выбраны интересы, фильтруем по категориям
            if interests:
                # Получаем все направления из выбранных категорий
                interested_directions = []
                for interest in interests:
                    interested_directions.extend(direction_categories.get(interest, []))
                
                # Фильтруем подходящие направления по выбранным категориям
                suitable_directions = [
                    d for d in suitable_directions 
                    if d['name'] in interested_directions
                ]
            
            if suitable_directions:
                st.success(f"Найдено {len(suitable_directions)} подходящих направлений:")
                
                # Группируем направления по категориям для удобного отображения
                categorized = defaultdict(list)
                for direction in suitable_directions:
                    for category, dirs in direction_categories.items():
                        if direction['name'] in dirs:
                            categorized[category].append(direction)
                            break
                    else:
                        categorized["Другие"].append(direction)
                
                # Выводим направления по категориям
                for category, directions in categorized.items():
                    with st.expander(f"**{category}** ({len(directions)} направлений)"):
                        cols = st.columns(2)
                        for i, direction in enumerate(directions):
                            with cols[i % 2]:
                                with st.container(border=True):
                                    st.subheader(direction['name'])
                                    st.write(f"**Возраст:** {direction.get('min_age', '?')}-{direction.get('max_age', '?')} лет")
                                    st.write(f"**Абонемент:** {direction['cost']} руб.")
                                    st.write(f"**Пробное занятие:** {direction.get('trial_cost', '?')} руб.")
                                    
                                    if direction.get('description'):
                                        st.caption(direction['description'])
            else:
                st.info("К сожалению, нет подходящих направлений для указанных параметров.")
# --- Main App Title and Navigation ---
st.title("🏫 Система управления детским центром")

# If not authenticated, show login page
if not st.session_state.authenticated:
    st.header("🔑 Вход в систему")
    with st.form("login_form"):
        username = st.text_input("Имя пользователя")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")
        if submitted:
            login(username, password)

# If authenticated, show the main app
else:
    # Sidebar navigation menu
    st.sidebar.title("🧭 Навигация")
    
    if st.session_state.role == 'admin':
        st.sidebar.button("🏠 Главная", on_click=lambda: setattr(st.session_state, 'page', 'home'))
        st.sidebar.button("🎨 Направления", on_click=lambda: setattr(st.session_state, 'page', 'directions'))
        st.sidebar.button("👦 Ученики и оплаты", on_click=lambda: setattr(st.session_state, 'page', 'students'))
        st.sidebar.button("👩‍🏫 Преподаватели", on_click=lambda: setattr(st.session_state, 'page', 'teachers'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: setattr(st.session_state, 'page', 'schedule'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: setattr(st.session_state, 'page', 'materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: setattr(st.session_state, 'page', 'kanban'))
        st.sidebar.button("🖼️ Медиа-галерея", on_click=lambda: setattr(st.session_state, 'page', 'media_gallery'))
        st.sidebar.button("📤 Массовая загрузка", on_click=lambda: setattr(st.session_state, 'page', 'bulk_upload'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: setattr(st.session_state, 'page', 'reception_helper'))
        
        st.sidebar.markdown("---")
        st.sidebar.button("📊 Отчет по оплатам", on_click=lambda: setattr(st.session_state, 'page', 'payments_report'))
        st.sidebar.button("📊 Отчет по закупкам", on_click=lambda: setattr(st.session_state, 'page', 'materials_report'))
        
    elif st.session_state.role == 'teacher':
        st.sidebar.button("🏠 Главная", on_click=lambda: setattr(st.session_state, 'page', 'home'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: setattr(st.session_state, 'page', 'schedule'))
        st.sidebar.button("👦 Мои ученики", on_click=lambda: setattr(st.session_state, 'page', 'students'))
        st.sidebar.button("📌 Мои задачи", on_click=lambda: setattr(st.session_state, 'page', 'kanban'))
    
    elif st.session_state.role == 'reception':
        st.sidebar.button("🏠 Главная", on_click=lambda: setattr(st.session_state, 'page', 'home'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: setattr(st.session_state, 'page', 'reception_helper'))
        st.sidebar.button("👦 Ученики", on_click=lambda: setattr(st.session_state, 'page', 'students'))
        st.sidebar.button("📅 Расписание", on_click=lambda: setattr(st.session_state, 'page', 'schedule'))
    
    st.sidebar.markdown("---")
    st.sidebar.text(f"👤 {st.session_state.username} ({st.session_state.role})")
    st.sidebar.button("🚪 Выйти", on_click=logout)
    
    # Clear data confirmation (admin only)
    if st.session_state.role == 'admin':
        if st.sidebar.button("🧹 Очистить все данные"):
            st.session_state.show_clear_confirm = True
        
        if st.session_state.show_clear_confirm:
            st.sidebar.warning("Это действие необратимо! Вы уверены?")
            col1, col2 = st.sidebar.columns(2)
            if col1.button("✅ Да"):
                initial_data = {
                    'directions': [],
                    'students': [],
                    'teachers': [],
                    'parents': [],
                    'payments': [],
                    'schedule': [],
                    'materials': [],
                    'kanban_tasks': {'ToDo': [], 'InProgress': [], 'Done': []},
                    'attendance': {},
                    'settings': {'trial_cost': 500, 'single_cost_multiplier': 1.5}
                }
                save_data(initial_data)
                st.session_state.data = load_data()
                st.success("Все данные очищены!")
                st.session_state.show_clear_confirm = False
                st.rerun()
            if col2.button("❌ Нет"):
                st.session_state.show_clear_confirm = False
                st.rerun()

    # --- Page Routing ---
    if st.session_state.page == 'home':
        show_home_page()
    elif st.session_state.page == 'directions':
        show_directions_page()
    elif st.session_state.page == 'students':
        show_students_page()
    elif st.session_state.page == 'teachers':
        show_teachers_page()
    elif st.session_state.page == 'schedule':
        show_schedule_page()
    elif st.session_state.page == 'materials':
        show_materials_page()
    elif st.session_state.page == 'kanban':
        show_kanban_board()
    elif st.session_state.page == 'media_gallery':
        show_media_gallery_page()
    elif st.session_state.page == 'bulk_upload':
        show_bulk_upload_page()
    elif st.session_state.page == 'payments_report':
        show_payments_report()
    elif st.session_state.page == 'materials_report':
        show_materials_report()
    elif st.session_state.page == 'reception_helper':
        show_reception_helper()
    else:
        st.info("Выберите раздел в меню слева.")