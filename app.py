# Import necessary libraries
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from collections import defaultdict
import uuid
import time
from datetime import timedelta
import csv
from io import StringIO
import base64

# --- Configuration and Data Storage ---
DATA_FILE = 'center_data.json'
MEDIA_FOLDER = 'media'
st.set_page_config(layout="wide", page_title="Детский центр - Управление")

# User authentication data (for a small, local app)
USERS = {
    # Администратор (полный доступ)
    "admin": {
        "password": "admin123", 
        "role": "admin",
        "teacher_id": None
    },
    
    # Преподаватели (ограниченный доступ)
    "teacher": {
        "password": "teacher123",
        "role": "reception",
        "teacher_id": None
    },
    "kristina": {
        "password": "kristina123",
        "role": "teacher",
        "teacher_id": "0138ade6-d53a-4cf1-a991-d6fe190dd78c"  # Филиппова Кристина Евгеньевна
    },
    "maria": {
        "password": "maria123",
        "role": "teacher",
        "teacher_id": "c13d7275-0cf0-46a7-b553-ed49eb7f3c18"  # Сидорова Мария (английский)
    },
    "lusine": {
        "password": "lusine123",
        "role": "teacher",
        "teacher_id": "af26a45e-2bfb-48f2-987c-94bf08da0a24"  # Лусине Арамовна Петросян
    },
    "oksana": {
        "password": "oksana123",
        "role": "teacher",
        "teacher_id": "4e75e60a-c7b6-404f-9c55-5b7cf4982c8d"  # Оксана Викторовна Иванова
    },
    "ali": {
        "password": "ali123",
        "role": "teacher",
        "teacher_id": "e9f70379-02f6-42d7-a4b4-31ce5bf4a840"  # Али Магомедович Каримов
    },
    "natalia_v": {
        "password": "natalia123",
        "role": "teacher",
        "teacher_id": "17ecccaf-5300-4238-8728-21cbb78db67b"  # Гелунова Наталья Владимировна
    },
    "natalia_s": {
        "password": "natalias123",
        "role": "teacher",
        "teacher_id": "47454a8d-fa51-4f64-aa30-79a5f1d1a476"  # Наталья Сергеевна Смирнова
    },
    "elena": {
        "password": "elena123",
        "role": "teacher",
        "teacher_id": "92c00fb4-80a8-4d26-af5a-f9bb58218fea"  # Елена Александровна Ковалева
    },
    
    # Ресепшен (специальная роль)
    "reception": {
        "password": "reception123",
        "role": "reception",
        "teacher_id": None
    }
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
        'recurring_lessons': [],
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
        
if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)
    for subfolder in ["images", "documents", "videos", "general"]:
        os.makedirs(os.path.join(MEDIA_FOLDER, subfolder))

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
    required_keys = {
        'news': [],
        'directions': [],
        'students': [],
        'teachers': [],
        'parents': [],
        'payments': [],
        'schedule': [],
        'recurring_lessons': [],
        'materials': [],
        'kanban_tasks': {'ToDo': [], 'InProgress': [], 'Done': []},
        'attendance': {},
        'settings': {'trial_cost': 500, 'single_cost_multiplier': 1.5}
    }
    
    for key, default_value in required_keys.items():
        if key not in st.session_state.data:
            st.session_state.data[key] = default_value

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
    'bulk_upload_type': 'directions',
    'filter_direction': None,
    'recurring_lesson_id': None
}

for var, default in session_vars.items():
    if var not in st.session_state:
        st.session_state[var] = default

# --- Authentication Functions ---
def login(username, password):
    """Handles user login with role-based permissions."""
    if username in USERS and USERS[username]['password'] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.role = USERS[username]['role']
        st.session_state.teacher_id = USERS[username].get('teacher_id')
        
        st.success(f"Добро пожаловать, {username}!")
        st.cache_data.clear()
        st.session_state.page = 'home'
        st.rerun()
    else:
        st.error("Неверное имя пользователя или пароль.")
def check_permission(allowed_roles=None, teacher_only=False):
    """Decorator to check user permissions."""
    if allowed_roles is None:
        allowed_roles = ['admin']
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated'):
                st.warning("Доступ запрещен. Пожалуйста, войдите в систему.")
                st.session_state.page = 'login'
                st.rerun()
                return
            
            if st.session_state.role not in allowed_roles:
                st.error("У вас недостаточно прав для этого действия.")
                return
            
            if teacher_only and st.session_state.teacher_id:
                # Для преподавателей - проверяем, что они работают со своими данными
                if 'teacher_id' in kwargs and kwargs['teacher_id'] != st.session_state.teacher_id:
                    st.error("Вы можете просматривать только свои данные.")
                    return
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
def logout():
    """Handles user logout."""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.cache_data.clear()
    st.session_state.page = 'login'
    st.info("Вы вышли из системы.")
    st.rerun()

# --- Helper Functions ---
@st.cache_data
def get_student_by_id(student_id):
    """Get student by ID. Uses caching to improve performance."""
    return next((s for s in st.session_state.data['students'] if s.get('id') == student_id), None)

@st.cache_data
def get_direction_by_id(direction_id):
    """Get direction by ID. Uses caching to improve performance."""
    return next((d for d in st.session_state.data['directions'] if d.get('id') == direction_id), None)

@st.cache_data
def get_teacher_by_id(teacher_id):
    """Get teacher by ID. Uses caching to improve performance."""
    return next((t for t in st.session_state.data['teachers'] if t.get('id') == teacher_id), None)

@st.cache_data
def get_parent_by_id(parent_id):
    """Get parent by ID. Uses caching to improve performance."""
    return next((p for p in st.session_state.data['parents'] if p.get('id') == parent_id), None)

def get_students_by_direction(direction_name):
    """Get students attending a specific direction."""
    return [s for s in st.session_state.data['students'] if direction_name in s.get('directions', [])]

def get_schedule_by_day(day):
    """Get schedule entries for a specific day."""
    return [s for s in st.session_state.data['schedule'] if s.get('day') == day]

def calculate_age(birth_date):
    """Корректный расчёт возраста."""
    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    elif isinstance(birth_date, str):
        try:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except ValueError:
            return None
    elif not isinstance(birth_date, date):
        return None
    
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
        if st.session_state.role == 'teacher':
            teacher = get_teacher_by_id(st.session_state.teacher_id)
            if teacher:
                lessons_today = [l for l in lessons_today if l.get('teacher') == teacher.get('name')]

        if lessons_today:
            message = f"Доброе утро!{selected_sticker}\nПриглашаем сегодня на занятия:\n"
            
            lessons_today.sort(key=lambda x: x['start_time'])
            for lesson in lessons_today:
                # Removed age_text as it's often included in direction name already
                message += f"{lesson['start_time']} - {lesson['direction']}\n" 
            
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
    """Управление направлениями: таблица и карточки."""
    st.header("🎨 Управление направлениями")

    directions = st.session_state.data.get("directions", [])
    students = st.session_state.data.get("students", [])

    # 👉 Добавление нового направления
    with st.expander("➕ Добавить новое направление"):
        with st.form("new_direction_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Название*")
                description = st.text_area("Описание")
                cost = st.number_input("Стоимость абонемента", min_value=0.0, step=100.0, value=3000.0)
            with col2:
                trial = st.number_input("Пробное занятие", min_value=0.0, value=500.0)
                min_age = st.number_input("Мин. возраст", min_value=0, max_value=18, value=3)
                max_age = st.number_input("Макс. возраст", min_value=0, max_value=18, value=12)
                gender = st.selectbox("Пол", ["Любой", "Мальчик", "Девочка"])

            if st.form_submit_button("Добавить"):
                if name:
                    new_direction = {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "description": description,
                        "cost": cost,
                        "trial_cost": trial,
                        "min_age": min_age,
                        "max_age": max_age,
                        "gender": gender if gender != "Любой" else None
                    }
                    directions.append(new_direction)
                    save_data(st.session_state.data)
                    st.success(f"Направление '{name}' добавлено.")
                    st.rerun()
                else:
                    st.error("Название обязательно.")

    # 🔄 Переключение режима отображения
    st.markdown("### 📌 Отображение")
    view_mode = st.radio("Режим", ["📋 Таблица", "🧾 Карточки"], horizontal=True)

    # 📋 Редактируемая таблица
    if view_mode == "📋 Таблица":
        if directions:
            table_data = []
            for d in directions:
                if 'id' not in d:
                    d['id'] = str(uuid.uuid4())  # фиксация KeyError
                student_count = len([s for s in students if d['name'] in s.get("directions", [])])
                table_data.append({
                    "id": d["id"],
                    "Название": d["name"],
                    "Описание": d.get("description", ""),
                    "Стоимость": d.get("cost", 0),
                    "Пробное": d.get("trial_cost", 0),
                    "Возраст": f"{d.get('min_age', '')}-{d.get('max_age', '')}",
                    "Пол": d.get("gender", "Любой"),
                    "Учеников": student_count
                })

            df = pd.DataFrame(table_data)
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                disabled=["id", "Учеников"],
                column_config={
                    "Стоимость": st.column_config.NumberColumn(format="%.0f ₽"),
                    "Пробное": st.column_config.NumberColumn(format="%.0f ₽")
                }
            )

            if st.button("💾 Сохранить изменения"):
                for i, row in edited_df.iterrows():
                    for d in directions:
                        if d["id"] == row["id"]:
                            d["name"] = row["Название"]
                            d["description"] = row["Описание"]
                            d["cost"] = row["Стоимость"]
                            d["trial_cost"] = row["Пробное"]
                            d["gender"] = row["Пол"] if row["Пол"] != "Любой" else None
                            try:
                                min_a, max_a = map(int, str(row["Возраст"]).split('-'))
                                d["min_age"] = min_a
                                d["max_age"] = max_a
                            except Exception:
                                pass
                save_data(st.session_state.data)
                st.success("Изменения сохранены.")
                st.rerun()
        else:
            st.info("Направления пока не добавлены.")

    # 🧾 Карточки
    elif view_mode == "🧾 Карточки":
        if directions:
            for d in directions:
                if 'id' not in d:
                    d['id'] = str(uuid.uuid4())  # защита от KeyError
                student_count = len([s for s in students if d["name"] in s.get("directions", [])])
                with st.container(border=True):
                    st.subheader(d["name"])
                    st.caption(d.get("description", ""))
                    col1, col2, col3 = st.columns(3)
                    col1.metric("💵 Абонемент", f"{d.get('cost', 0):.0f} ₽")
                    col2.metric("🎫 Пробное", f"{d.get('trial_cost', 0):.0f} ₽")
                    col3.metric("👥 Учеников", student_count)

                    age_str = f"{d.get('min_age', '?')} - {d.get('max_age', '?')} лет"
                    st.markdown(f"**Возраст:** {age_str} | **Пол:** {d.get('gender', 'Любой')}")
        else:
            st.info("Нет направлений для отображения.")

def show_student_card(student_id):
    student = get_student_by_id(student_id)
    if not student:
        st.warning("Ученик не найден.")
        return

    parent = get_parent_by_id(student.get('parent_id'))
    with st.expander(f"📘 {student['name']}", expanded=False):
        st.write(f"👤 **Пол:** {student.get('gender')}")
        st.write(f"🎂 **Дата рождения:** {student.get('dob')} — {calculate_age(student.get('dob'))} лет")
        st.write(f"📆 Зарегистрирован: {student.get('registration_date')}")
        st.write(f"📝 Заметки: {student.get('notes', '')}")
        if parent:
            st.write(f"👪 Родитель: {parent.get('name')} | 📞 {parent.get('phone')}")

        st.subheader("🎯 Направления")
        for d in student.get("directions", []):
            with st.form(f"unassign_form_{student['id']}_{d}"):
                if st.form_submit_button(f"❌ Отписать от {d}"):
                    student['directions'].remove(d)
                    save_data(st.session_state.data)
                    st.success(f"Ученик отписан от {d}")
                    st.rerun()

        available = [d['name'] for d in st.session_state.data['directions'] if d['name'] not in student.get("directions", [])]
        if available:
            with st.form(f"assign_dir_form_{student['id']}"):
                new_dir = st.selectbox("Добавить направление", available, key=f"dir_sel_{student['id']}")
                if st.form_submit_button("Добавить"):
                    student['directions'].append(new_dir)
                    save_data(st.session_state.data)
                    st.success(f"Добавлено направление {new_dir}")
                    st.rerun()

        st.subheader("💳 Оплаты")
        payments = [p for p in st.session_state.data['payments'] if p['student_id'] == student['id']]
        if payments:
            df_pay = pd.DataFrame(payments)
            df_pay['date'] = pd.to_datetime(df_pay['date'])
            st.dataframe(df_pay[['date', 'amount', 'direction', 'type', 'notes']], hide_index=True, use_container_width=True)
        else:
            st.info("Нет оплат.")

        st.subheader("📅 Посещения")
        attendances = []
        for day, lessons in st.session_state.data.get("attendance", {}).items():
            for lesson_id, students in lessons.items():
                if student_id in students:
                    status = students[student_id]
                    lesson = next((l for l in st.session_state.data['schedule'] if l['id'] == lesson_id), None)
                    if lesson:
                        attendances.append({
                            "Дата": day,
                            "Направление": lesson['direction'],
                            "Преподаватель": lesson['teacher'],
                            "Был": "Да" if status.get('present') else "Нет",
                            "Оплачено": "Да" if status.get('paid') else "Нет",
                            "Примечание": status.get('note', '')
                        })
        if attendances:
            st.dataframe(pd.DataFrame(attendances).sort_values("Дата", ascending=False), use_container_width=True)
        else:
            st.info("Нет посещений.")




def show_teacher_card(teacher_id):
    teacher = get_teacher_by_id(teacher_id)
    if not teacher:
        st.warning("Преподаватель не найден.")
        return

    with st.expander(f"👩‍🏫 {teacher.get('name', 'Без имени')}", expanded=False):
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image("https://placehold.co/100x100/A3A3A3/FFFFFF?text=Фото", width=100)
        with col2:
            st.write(f"📞 Телефон: {teacher.get('phone', 'нет')}")
            st.write(f"📧 Email: {teacher.get('email', 'нет')}")
            st.write(f"📝 Заметки: {teacher.get('notes', '')}")
            st.write(f"🗓️ Принят: {teacher.get('hire_date', '')}")

        # 🎯 Направления преподавателя
        st.subheader("🎯 Направления и посещения")
        for direction_name in teacher.get('directions', []):
            st.markdown(f"### 📘 {direction_name}")
            
            # Найдём все занятия по этому направлению у этого преподавателя
            lessons = [l for l in st.session_state.data['schedule']
                      if l['direction'] == direction_name 
                      and l['teacher'] == teacher['name']]

            if not lessons:
                st.info("Нет занятий по этому направлению.")
                continue

            # Найдём всех учеников на этом направлении
            students_in_dir = [s for s in st.session_state.data['students'] 
                             if direction_name in s.get('directions', [])]
            
            if not students_in_dir:
                st.info("Нет учеников на этом направлении.")
                continue

            # Соберём все данные о посещениях
            attendance_data = []
            attendance = st.session_state.data.get("attendance", {})
            
            # Для каждого ученика найдём все посещения
            for student in students_in_dir:
                for lesson in lessons:
                    lesson_id = lesson.get('id')
                    for date_str, day_lessons in attendance.items():
                        if lesson_id in day_lessons and student['id'] in day_lessons[lesson_id]:
                            record = day_lessons[lesson_id][student['id']]
                            
                            # Проверим оплату (синхронизация с данными о платежах)
                            paid_status = record.get('paid', False)
                            if not paid_status:
                                # Дополнительная проверка по платежам
                                for payment in st.session_state.data['payments']:
                                    if (payment['student_id'] == student['id'] and 
                                        payment['direction'] == direction_name):
                                        payment_date = datetime.strptime(payment['date'], "%Y-%m-%d").date()
                                        lesson_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                        
                                        if payment['type'] == "Абонемент":
                                            if (payment_date.month == lesson_date.month and 
                                                payment_date.year == lesson_date.year):
                                                paid_status = True
                                                break
                                        elif payment['type'] in ["Разовое", "Пробное"]:
                                            if payment_date == lesson_date:
                                                paid_status = True
                                                break
                            
                            attendance_data.append({
                                "Ученик": student['name'],
                                "Дата": date_str,
                                "Занятие": f"{lesson['start_time']}-{lesson['end_time']}",
                                "Присутствовал": "✅" if record.get('present') else "❌",
                                "Оплачено": "✅" if paid_status else "❌",
                                "Примечание": record.get('note', '')
                            })

            if attendance_data:
                # Создаём DataFrame и сортируем по дате
                df = pd.DataFrame(attendance_data)
                df['Дата'] = pd.to_datetime(df['Дата'])
                df = df.sort_values('Дата', ascending=False)
                
                # Отображаем таблицу с возможностью фильтрации
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                        "Присутствовал": st.column_config.TextColumn(),
                        "Оплачено": st.column_config.TextColumn()
                    }
                )
                
                # Кнопка экспорта
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Экспорт в CSV",
                    data=csv,
                    file_name=f"attendance_{teacher['name']}_{direction_name}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Нет данных о посещениях.")



def show_students_page():
    st.header("👦👧 Ученики и оплаты")

    students = st.session_state.data['students']
    parents = st.session_state.data['parents']
    directions = st.session_state.data['directions']

    # Добавим id для всех, если вдруг отсутствует
    for s in students:
        if 'id' not in s:
            s['id'] = str(uuid.uuid4())

    view_mode = st.radio("Режим отображения", ["📋 Таблица", "🧾 Карточки"], horizontal=True)

    with st.expander("➕ Добавить нового ученика"):
        with st.form("new_student_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ФИО*")
                dob = st.date_input("Дата рождения*", value=date.today())
                gender = st.selectbox("Пол", ["Мальчик", "Девочка"])
                notes = st.text_area("Заметки")
            with col2:
                parent_map = {p['id']: f"{p['name']} ({p.get('phone', '-')})" for p in parents}
                parent_id = st.selectbox("Родитель", [None] + list(parent_map.keys()),
                                         format_func=lambda x: parent_map.get(x, "Новый родитель") if x else "Новый родитель")
                new_parent_name = st.text_input("Имя нового родителя")
                new_parent_phone = st.text_input("Телефон нового родителя")
                selected_dirs = st.multiselect("Направления", [d['name'] for d in directions])

            if st.form_submit_button("Добавить"):
                if name:
                    if not parent_id:
                        new_parent = {
                            "id": str(uuid.uuid4()),
                            "name": new_parent_name or f"Родитель {name}",
                            "phone": new_parent_phone,
                            "children_ids": []
                        }
                        parents.append(new_parent)
                        parent_id = new_parent['id']
                    new_student = {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "dob": str(dob),
                        "gender": gender,
                        "parent_id": parent_id,
                        "directions": selected_dirs,
                        "notes": notes,
                        "registration_date": str(date.today())
                    }
                    students.append(new_student)
                    for p in parents:
                        if p['id'] == parent_id:
                            p.setdefault("children_ids", []).append(new_student['id'])
                    save_data(st.session_state.data)
                    st.success(f"Ученик {name} добавлен.")
                    st.rerun()
                else:
                    st.error("Введите ФИО.")

    if view_mode == "📋 Таблица":
        if students:
            df = pd.DataFrame(students)
            df['parent'] = df['parent_id'].map({p['id']: p['name'] for p in parents})
            df['directions'] = df['directions'].apply(lambda x: ', '.join(x) if isinstance(x, list) else '')
            df['age'] = df['dob'].apply(calculate_age)
            df['id'] = df['id']  # убедимся, что есть

            edited = st.data_editor(
                df[['id', 'name', 'dob', 'age', 'gender', 'parent', 'directions', 'notes']],
                hide_index=True,
                use_container_width=True,
                disabled=["age", "parent"],
            )

            if st.button("💾 Сохранить изменения"):
                for i, row in edited.iterrows():
                    for s in students:
                        if s['id'] == row['id']:
                            s['name'] = row['name']
                            s['dob'] = str(row['dob']) if isinstance(row['dob'], date) else row['dob']
                            s['gender'] = row['gender']
                            s['notes'] = row['notes']
                            s['directions'] = [d.strip() for d in str(row['directions']).split(',') if d.strip()]
                save_data(st.session_state.data)
                st.success("Данные обновлены.")
                st.rerun()
        else:
            st.info("Нет учеников.")
    else:
        for student in students:
            show_student_card(student['id'])

    # 💳 Оплаты
    st.subheader("💳 Добавить оплату")
    if students:
        student_map = {s['id']: s['name'] for s in students}
        selected_id = st.selectbox("Ученик", list(student_map.keys()), format_func=lambda x: student_map[x])
        with st.form("add_payment_form"):
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Сумма (₽)", min_value=0.0)
                p_date = st.date_input("Дата", value=date.today())
            with col2:
                direction = st.selectbox("Направление", [d['name'] for d in directions])
                p_type = st.selectbox("Тип", ["Абонемент", "Пробное", "Разовое"])
            notes = st.text_input("Заметки")

            # В функции show_students_page(), в разделе добавления оплаты:
            if st.form_submit_button("Добавить оплату"):
                new_payment = {
                    "id": str(uuid.uuid4()),
                    "student_id": selected_id,
                    "date": str(p_date),
                    "amount": amount,
                    "direction": direction,
                    "type": p_type,
                    "notes": notes
                }
                st.session_state.data['payments'].append(new_payment)
                
                # Синхронизация с посещениями
                if p_type == "Абонемент":
                    # Для абонемента отмечаем все занятия в этом месяце
                    for schedule_item in st.session_state.data['schedule']:
                        if schedule_item['direction'] == direction:
                            # Находим все даты этого занятия в текущем месяце
                            day_map = {
                                "Понедельник": 0, "Вторник": 1, "Среда": 2,
                                "Четверг": 3, "Пятница": 4, "Суббота": 5, "Воскресенье": 6
                            }
                            target_weekday = day_map.get(schedule_item['day'])
                            
                            if target_weekday is not None:
                                current_date = p_date
                                # Перебираем все дни месяца
                                while current_date.month == p_date.month:
                                    if current_date.weekday() == target_weekday:
                                        date_key = current_date.strftime("%Y-%m-%d")
                                        lesson_id = schedule_item['id']
                                        
                                        # Инициализируем структуру данных для посещений
                                        if date_key not in st.session_state.data['attendance']:
                                            st.session_state.data['attendance'][date_key] = {}
                                        if lesson_id not in st.session_state.data['attendance'][date_key]:
                                            st.session_state.data['attendance'][date_key][lesson_id] = {}
                                        if selected_id not in st.session_state.data['attendance'][date_key][lesson_id]:
                                            st.session_state.data['attendance'][date_key][lesson_id][selected_id] = {
                                                'present': False,
                                                'paid': True,  # Отмечаем как оплаченное
                                                'note': 'Абонемент'
                                            }
                                        else:
                                            st.session_state.data['attendance'][date_key][lesson_id][selected_id]['paid'] = True
                                    current_date += timedelta(days=1)
                else:
                    # Для разового/пробного отмечаем только текущий день
                    date_key = p_date.strftime("%Y-%m-%d")
                    for schedule_item in st.session_state.data['schedule']:
                        if schedule_item['direction'] == direction:
                            lesson_id = schedule_item['id']
                            if date_key not in st.session_state.data['attendance']:
                                st.session_state.data['attendance'][date_key] = {}
                            if lesson_id not in st.session_state.data['attendance'][date_key]:
                                st.session_state.data['attendance'][date_key][lesson_id] = {}
                            if selected_id not in st.session_state.data['attendance'][date_key][lesson_id]:
                                st.session_state.data['attendance'][date_key][lesson_id][selected_id] = {
                                    'present': False,
                                    'paid': True,  # Отмечаем как оплаченное
                                    'note': p_type
                                }
                            else:
                                st.session_state.data['attendance'][date_key][lesson_id][selected_id]['paid'] = True
                
                save_data(st.session_state.data)
                st.success("Оплата добавлена и синхронизирована с посещениями!")
                st.rerun()



def show_teachers_page():
    st.header("👩‍🏫 Преподаватели")

    teachers = st.session_state.data.get("teachers", [])
    directions = st.session_state.data.get("directions", [])

    # Убедимся, что у всех есть id
    for t in teachers:
        if 'id' not in t:
            t['id'] = str(uuid.uuid4())

    # ➕ Добавить преподавателя
    with st.expander("➕ Добавить преподавателя"):
        with st.form("new_teacher_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ФИО*")
                phone = st.text_input("Телефон")
                email = st.text_input("Email")
            with col2:
                teacher_directions = st.multiselect("Направления", [d['name'] for d in directions])
                notes = st.text_area("Заметки")

            if st.form_submit_button("Добавить"):
                if name:
                    new_teacher = {
                        'id': str(uuid.uuid4()),
                        'name': name,
                        'phone': phone,
                        'email': email,
                        'directions': teacher_directions,
                        'notes': notes,
                        'hire_date': str(date.today())
                    }
                    teachers.append(new_teacher)
                    save_data(st.session_state.data)
                    st.success(f"Преподаватель {name} добавлен.")
                    st.rerun()
                else:
                    st.error("ФИО обязательно.")

    # 📋 Таблица редактирования
    if teachers:
        df = pd.DataFrame(teachers)
        df['directions'] = df['directions'].apply(lambda x: ', '.join(x))
        df['id'] = df['id']

        edited_df = st.data_editor(
            df[['id', 'name', 'phone', 'email', 'directions', 'notes']],
            hide_index=True,
            use_container_width=True,
            disabled=['id'],
        )

        if st.button("💾 Сохранить изменения"):
            for i, row in edited_df.iterrows():
                for t in teachers:
                    if t['id'] == row['id']:
                        t['name'] = row['name']
                        t['phone'] = row['phone']
                        t['email'] = row['email']
                        t['notes'] = row['notes']
                        # Важно: сохраняем направления как список
                        t['directions'] = [d.strip() for d in row['directions'].split(',') if d.strip()]
                        break
            
            # Обновляем расписание, если изменилось имя преподавателя
            for teacher in teachers:
                old_name = next((t['name'] for t in st.session_state.data['teachers'] if t['id'] == teacher['id']), None)
                if old_name and old_name != teacher['name']:
                    for lesson in st.session_state.data['schedule']:
                        if lesson['teacher'] == old_name:
                            lesson['teacher'] = teacher['name']
            
            save_data(st.session_state.data)
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Преподаватели не добавлены.")

    # 🧾 Карточки преподавателей
    st.subheader("🧾 Карточки преподавателей")
    for t in teachers:
        show_teacher_card(t['id'])


def show_schedule_page():
    st.header("📅 Расписание и посещения")

    data = st.session_state.data
    schedule = data.setdefault("schedule", [])
    attendance = data.setdefault("attendance", {})
    payments = data.setdefault("payments", [])
    students = data.get("students", [])
    directions = data.get("directions", [])
    teachers = data.get("teachers", [])

    # === Добавление занятия ===
    if st.session_state.role in ['admin', 'teacher']:
        with st.expander("➕ Добавить занятие в расписание", expanded=False):
            with st.form("new_schedule_form"):
                col1, col2 = st.columns(2)
                with col1:
                    direction_name = st.selectbox("Направление*", [d['name'] for d in directions])
                    teacher = st.selectbox("Преподаватель*", [t['name'] for t in teachers])
                with col2:
                    start_time = st.time_input("Начало*", value=datetime.strptime("16:00", "%H:%M").time())
                    end_time = st.time_input("Конец*", value=datetime.strptime("17:00", "%H:%M").time())
                    day_of_week = st.selectbox("День недели*", [
                        "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
                    ])

                if st.form_submit_button("Добавить занятие"):
                    schedule.append({
                        'id': str(uuid.uuid4()),
                        'direction': direction_name,
                        'teacher': teacher,
                        'start_time': str(start_time),
                        'end_time': str(end_time),
                        'day': day_of_week
                    })
                    save_data(data)
                    st.success("Занятие добавлено.")
                    st.rerun()

    # === Календарь и занятия ===
    st.subheader("🗓️ Календарь занятий")
    selected_date = st.date_input("Выберите дату", value=st.session_state.get("selected_date", date.today()))
    st.session_state.selected_date = selected_date
    day_name = selected_date.strftime("%A")

    day_map = {
        "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
        "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
    }
    russian_day = day_map.get(day_name, day_name)
    lessons_today = [s for s in schedule if s['day'] == russian_day]

    if lessons_today:
        for lesson in lessons_today:
            with st.expander(f"{lesson['direction']} ({lesson['start_time']}-{lesson['end_time']}, {lesson['teacher']})", expanded=False):
                date_key = selected_date.strftime("%Y-%m-%d")
                lesson_key = lesson['id']
                att_key = f"att_{lesson_key}_{date_key}"

                # Инициализация состояния
                if att_key not in st.session_state:
                    st.session_state[att_key] = {
                        'data': [],
                        'saved': False
                    }

                # Найдём учеников
                students_in_dir = [s for s in students if lesson['direction'] in s.get('directions', [])]
                
                if not students_in_dir:
                    st.info("Нет учеников на этом направлении.")
                    continue

                # Инициализация структуры посещений
                if date_key not in attendance:
                    attendance[date_key] = {}
                if lesson_key not in attendance[date_key]:
                    attendance[date_key][lesson_key] = {}

                # Подготовка данных для таблицы
                att_rows = []
                for s in students_in_dir:
                    student_id = s['id']
                    
                    # Проверка оплаты
                    paid = False
                    for p in payments:
                        if p['student_id'] == student_id and p['direction'] == lesson['direction']:
                            p_date = datetime.strptime(p['date'], "%Y-%m-%d").date()
                            if p['type'] == "Абонемент" and p_date.month == selected_date.month and p_date.year == selected_date.year:
                                paid = True
                                break
                            elif p['type'] in ["Разовое", "Пробное"] and p_date == selected_date:
                                paid = True
                                break
                    
                    # Инициализация записи о посещении
                    if student_id not in attendance[date_key][lesson_key]:
                        attendance[date_key][lesson_key][student_id] = {
                            'present': False,
                            'paid': paid,
                            'note': ''
                        }
                    
                    att_rows.append({
                        "Ученик": s['name'],
                        "Присутствовал": attendance[date_key][lesson_key][student_id]['present'],
                        "Оплачено": attendance[date_key][lesson_key][student_id]['paid'],
                        "Примечание": attendance[date_key][lesson_key][student_id]['note']
                    })

                # Инициализация таблицы
                if not st.session_state[att_key]['data']:
                    st.session_state[att_key]['data'] = att_rows

                # Отображение редактора
                edited_df = st.data_editor(
                    pd.DataFrame(st.session_state[att_key]['data']),
                    use_container_width=True,
                    hide_index=True,
                    key=f"editor_{att_key}",
                    column_config={
                        "Присутствовал": st.column_config.CheckboxColumn(),
                        "Оплачено": st.column_config.CheckboxColumn()
                    }
                )

                # Обработка сохранения
                if st.button("💾 Сохранить посещения", key=f"save_{att_key}"):
                    for idx, s in enumerate(students_in_dir):
                        s_id = s['id']
                        attendance[date_key][lesson_key][s_id] = {
                            'present': bool(edited_df.iloc[idx]['Присутствовал']),
                            'paid': bool(edited_df.iloc[idx]['Оплачено']),
                            'note': str(edited_df.iloc[idx]['Примечание'])
                        }
                    
                    st.session_state[att_key]['saved'] = True
                    st.session_state[att_key]['data'] = edited_df.to_dict('records')
                    save_data(data)
                    st.success("Посещения сохранены!")
                    time.sleep(0.3)
                    st.rerun()
    else:
        st.info(f"На {russian_day} занятий нет.")

    # === Общее расписание ===
    st.subheader("📋 Общее расписание")
    if schedule:
        df = pd.DataFrame(schedule)

        # Безопасное приведение времени
        df['start_time'] = pd.to_datetime(df['start_time'], format='mixed', errors='coerce').dt.strftime("%H:%M")
        df['end_time'] = pd.to_datetime(df['end_time'], format='mixed', errors='coerce').dt.strftime("%H:%M")
        df['start_time'] = df['start_time'].fillna("—")
        df['end_time'] = df['end_time'].fillna("—")

        # Фильтры
        col1, col2, col3 = st.columns(3)
        with col1:
            day_filter = st.multiselect("День недели", sorted(df['day'].unique()))
        with col2:
            teacher_filter = st.multiselect("Преподаватель", sorted(df['teacher'].unique()))
        with col3:
            dir_filter = st.multiselect("Направление", sorted(df['direction'].unique()))

        if day_filter:
            df = df[df['day'].isin(day_filter)]
        if teacher_filter:
            df = df[df['teacher'].isin(teacher_filter)]
        if dir_filter:
            df = df[df['direction'].isin(dir_filter)]

        # Добавляем столбец с кнопками удаления
        df['Удалить'] = False  # Добавляем столбец для чекбоксов
        
        # Отображаем таблицу с возможностью выбора строк для удаления
        edited_df = st.data_editor(
            df[['day', 'start_time', 'end_time', 'teacher', 'direction', 'Удалить']],
            use_container_width=True,
            hide_index=True,
            key="full_schedule_editor",
            column_config={
                "Удалить": st.column_config.CheckboxColumn(
                    "Удалить",
                    help="Выберите занятия для удаления",
                    default=False
                )
            }
        )

        # Кнопка для удаления выбранных занятий
        if st.button("🗑️ Удалить выбранные занятия"):
            # Получаем индексы строк, отмеченных для удаления
            rows_to_delete = edited_df[edited_df['Удалить']].index
            
            if len(rows_to_delete) > 0:
                # Удаляем занятия из расписания
                for index in sorted(rows_to_delete, reverse=True):
                    # Находим ID занятия для удаления
                    lesson_id = schedule[index]['id']
                    
                    # Удаляем из основного расписания
                    del schedule[index]
                    
                    # Удаляем связанные посещения
                    for date_key in list(attendance.keys()):
                        if lesson_id in attendance[date_key]:
                            del attendance[date_key][lesson_id]
                        # Удаляем пустые даты
                        if not attendance[date_key]:
                            del attendance[date_key]
                
                save_data(data)
                st.success(f"Удалено {len(rows_to_delete)} занятий!")
                st.rerun()
            else:
                st.warning("Не выбрано ни одного занятия для удаления")

        st.download_button(
            "📥 Экспорт в CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name="schedule_export.csv",
            mime="text/csv"
        )
    else:
        st.info("Пока нет занятий.")



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
    """Page to manage media files with folder support."""
    st.header("🖼️ Медиа-галерея")
    
    # Create tabs for different media types
    tab_images, tab_docs, tab_videos, tab_folders = st.tabs(["Фотографии", "Документы", "Видео", "Управление папками"])
    
    # Helper function to get all folders
    def get_folders(base_path):
        folders = []
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                folders.append(item)
        return folders
    
    # Folder management tab
    with tab_folders:
        st.subheader("📂 Управление папками")
        
        # Create new folder
        with st.expander("➕ Создать новую папку", expanded=True):
            with st.form("create_folder_form"):
                folder_type = st.selectbox("Тип папки", ["Фото", "Документ", "Видео", "Общая"])
                folder_name = st.text_input("Название папки*")
                
                if st.form_submit_button("Создать папку"):
                    if folder_name:
                        # Determine base folder based on type
                        base_folder = {
                            "Фото": "images",
                            "Документ": "documents",
                            "Видео": "videos",
                            "Общая": "general"
                        }.get(folder_type, "general")
                        
                        full_path = os.path.join(MEDIA_FOLDER, base_folder, folder_name)
                        try:
                            os.makedirs(full_path, exist_ok=True)
                            st.success(f"Папка '{folder_name}' создана в разделе '{folder_type}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при создании папки: {e}")
                    else:
                        st.error("Введите название папки")
        
        # List existing folders
        st.subheader("📁 Существующие папки")
        
        for media_type, base_folder in [("Фото", "images"), 
                                      ("Документы", "documents"), 
                                      ("Видео", "videos"),
                                      ("Общие", "general")]:
            
            folder_path = os.path.join(MEDIA_FOLDER, base_folder)
            if os.path.exists(folder_path):
                folders = get_folders(folder_path)
                if folders:
                    with st.expander(f"{media_type} ({len(folders)})"):
                        for folder in folders:
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"📁 {folder}")
                            with col2:
                                if st.button("🗑️", key=f"del_{base_folder}_{folder}"):
                                    try:
                                        os.rmdir(os.path.join(folder_path, folder))
                                        st.success(f"Папка '{folder}' удалена!")
                                        st.rerun()
                                    except OSError:
                                        st.error("Папка не пуста! Удалите сначала файлы.")
    
    # Upload section with folder selection
    with st.expander("⬆️ Загрузить файлы", expanded=False):
        with st.form("upload_media_form"):
            file_type = st.selectbox("Тип файла", ["Фото", "Документ", "Видео"])
            # Get available folders for selected type
            base_folder = {
                "Фото": "images",
                "Документ": "documents",
                "Видео": "videos"
            }.get(file_type, "general")
            
            target_folders = get_folders(os.path.join(MEDIA_FOLDER, base_folder))
            target_folder = st.selectbox(
                "Папка назначения",
                ["Основная папка"] + target_folders
            )
            
            uploaded_files = st.file_uploader(
                "Выберите файлы",
                type=["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "mp4", "mov"],
                accept_multiple_files=True
            )
            
            if st.form_submit_button("Загрузить"):
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        # Determine target path
                        if target_folder == "Основная папка":
                            dest_folder = os.path.join(MEDIA_FOLDER, base_folder)
                        else:
                            dest_folder = os.path.join(MEDIA_FOLDER, base_folder, target_folder)
                        
                        os.makedirs(dest_folder, exist_ok=True)
                        file_path = os.path.join(dest_folder, uploaded_file.name)
                        
                        # Check for existing file
                        if os.path.exists(file_path):
                            st.warning(f"Файл '{uploaded_file.name}' уже существует в папке '{target_folder}'")
                            continue
                        
                        try:
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                        except Exception as e:
                            st.error(f"Ошибка при загрузке файла '{uploaded_file.name}': {e}")
                    
                    st.success(f"Загружено {len(uploaded_files)} файлов в папку '{target_folder}'!")
                    st.rerun()
                else:
                    st.error("Пожалуйста, выберите хотя бы один файл")

    # Display media by type with folder support
    def display_media_with_folders(media_type, extensions, tab):
        base_folder = {
            "Фото": "images",
            "Документ": "documents",
            "Видео": "videos"
        }.get(media_type, "general")
        
        main_folder_path = os.path.join(MEDIA_FOLDER, base_folder)
        
        if not os.path.exists(main_folder_path):
            tab.info(f"Нет {media_type.lower()} в галерее.")
            return
        
        # Get all folders for this media type
        folders = get_folders(main_folder_path)
        
        if not folders:
            # Display files from main folder
            display_files_from_folder(main_folder_path, extensions, tab, media_type)
        else:
            # Create tabs for each folder
            folder_tabs = tab.tabs(["Основная папка"] + folders)
            
            # Main folder
            with folder_tabs[0]:
                display_files_from_folder(main_folder_path, extensions, tab, media_type)
            
            # Each subfolder
            for i, folder in enumerate(folders, 1):
                with folder_tabs[i]:
                    folder_path = os.path.join(main_folder_path, folder)
                    display_files_from_folder(folder_path, extensions, tab, media_type, folder)

    def display_files_from_folder(folder_path, extensions, tab, media_type, folder_name=None):
        files = []
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path) and file.lower().endswith(extensions):
                files.append(file_path)
        
        if not files:
            tab.info(f"Нет файлов в папке {folder_name if folder_name else 'основной'}")
            return
        
        if media_type == "Фото":
            cols = tab.columns(3)
            for i, img_path in enumerate(files):
                with cols[i % 3]:
                    st.image(img_path, use_column_width=True)
                    st.caption(os.path.basename(img_path))
                    if st.button("Удалить", key=f"del_img_{img_path}"):
                        os.remove(img_path)
                        st.success("Файл удален!")
                        st.rerun()
        
        elif media_type == "Документ":
            for doc_path in files:
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
        
        elif media_type == "Видео":
            for video_path in files:
                st.video(video_path)
                st.caption(os.path.basename(video_path))
                if st.button("Удалить", key=f"del_vid_{video_path}"):
                    os.remove(video_path)
                    st.success("Файл удален!")
                    st.rerun()

    # Display media in respective tabs with folder support
    with tab_images:
        st.subheader("Фотографии")
        display_media_with_folders("Фото", ('.png', '.jpg', '.jpeg', '.gif'), st)

    with tab_docs:
        st.subheader("Документы")
        display_media_with_folders("Документ", ('.pdf', '.doc', '.docx'), st)

    with tab_videos:
        st.subheader("Видео")
        display_media_with_folders("Видео", ('.mp4', '.mov'), st)

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
    
    def _navigate_to(page_name):
        st.cache_data.clear() 
        st.session_state.page = page_name
        st.rerun()

    if st.session_state.role == 'admin':
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("🎨 Направления", on_click=lambda: _navigate_to('directions'))
        st.sidebar.button("👦 Ученики и оплаты", on_click=lambda: _navigate_to('students'))
        st.sidebar.button("👩‍🏫 Преподаватели", on_click=lambda: _navigate_to('teachers'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: _navigate_to('schedule'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        st.sidebar.button("🖼️ Медиа-галерея", on_click=lambda: _navigate_to('media_gallery'))
        st.sidebar.button("📤 Массовая загрузка", on_click=lambda: _navigate_to('bulk_upload'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: _navigate_to('reception_helper'))
        
        st.sidebar.markdown("---")
        st.sidebar.button("📊 Отчет по оплатам", on_click=lambda: _navigate_to('payments_report'))
        st.sidebar.button("📊 Отчет по закупкам", on_click=lambda: _navigate_to('materials_report'))
        
    elif st.session_state.role == 'teacher':
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("👩‍🏫 Преподаватели", on_click=lambda: _navigate_to('teachers'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        st.sidebar.button("🖼️ Медиа-галерея", on_click=lambda: _navigate_to('media_gallery'))
    
    elif st.session_state.role == 'reception':
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("🎨 Направления", on_click=lambda: _navigate_to('directions'))
        st.sidebar.button("👦 Ученики и оплаты", on_click=lambda: _navigate_to('students'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: _navigate_to('schedule'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: _navigate_to('reception_helper'))
    
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