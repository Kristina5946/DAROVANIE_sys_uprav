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
from urllib.parse import quote
import requests
import calendar

# Конфигурация (используйте секреты Streamlit!)
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GIST_ID = st.secrets.get("GIST_ID")

if not GITHUB_TOKEN or not GIST_ID:
    st.error("GitHub токен или ID Gist не настроены! Данные будут сохраняться только локально.")
    # Присваиваем пустые значения, чтобы избежать ошибок
    GITHUB_TOKEN = ""
    GIST_ID = ""

# --- Configuration and Data Storage ---
DATA_FILE = 'center_data.json'
MEDIA_FOLDER = 'media'
st.set_page_config(layout="wide", page_title="Детский центр - Управление")

def get_users():
    """Загружает пользователей из secrets"""
    users = {}
    for username in st.secrets.users:
        user_cfg = st.secrets.users[username]
        users[username] = {
            "password": user_cfg["password"],
            "role": user_cfg["role"],
            "teacher_id": user_cfg.get("teacher_id") or None
        }
    return users

# Check if the data file exists, if not, create a new one with an empty structure
if not os.path.exists(DATA_FILE):
    initial_data = {
        'news': [],
        'directions': [],
        'subdirections': [], 
        'students': [],
        'teachers': [],
        'parents': [],
        'payments': [],
        'schedule': [],
        'archived_schedule': [],
        'materials': [],
        'single_lessons': [], 
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
    """Улучшенная загрузка данных с приоритетом GitHub"""
    try:
        # 1. Пытаемся загрузить из GitHub
        if GITHUB_TOKEN and GIST_ID:
            try:
                resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=github_headers())
                if resp.status_code == 200:
                    gist_data = resp.json()
                    if "center_data.json" in gist_data["files"]:
                        content = gist_data["files"]["center_data.json"]["content"]
                        if content.strip():
                            remote_data = json.loads(content)
                            if isinstance(remote_data, dict) and 'students' in remote_data:
                                st.success(f"Данные загружены из GitHub (обновлено: {gist_data['updated_at']})")
                                return remote_data
                            else:
                                st.warning("Данные из GitHub имеют неверную структуру")
                else:
                    st.warning(f"Ошибка загрузки из GitHub: {resp.status_code} {resp.text}")
            except Exception as e:
                st.warning(f"Ошибка загрузки из GitHub: {str(e)}")

                
        # 2. Fallback на локальный файл
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                    st.warning("Используются локальные данные")
                    return local_data
            except Exception as e:
                st.error(f"Ошибка чтения локального файла: {str(e)}")
                
    except Exception as e:
        st.error(f"Критическая ошибка загрузки: {str(e)}")
    
    # 3. Возвращаем начальные данные, если ничего не загрузилось
    st.warning("Используются начальные данные")
    return initial_data.copy()

# --- AUDIT LOGGING SYSTEM ---
LOG_FILE = 'audit_log.csv'

def log_action(user, action, details):
    """Log user actions to a CSV file to save memory."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(LOG_FILE)
    
    try:
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Timestamp', 'User', 'Action', 'Details'])
            writer.writerow([timestamp, user, action, details])
    except Exception as e:
        print(f"Logging error: {e}")

def show_audit_log_page():
    """Display the audit log."""
    st.header("🕵️ История действий")
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        df = df.sort_values('Timestamp', ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if st.session_state.role == 'admin':
            if st.button("🗑️ Очистить историю"):
                os.remove(LOG_FILE)
                st.rerun()
    else:
        st.info("История действий пуста.")

def github_headers():
    """Возвращает заголовки для GitHub API"""
    if not GITHUB_TOKEN:
        st.warning("GitHub токен не настроен! Работаем локально.")
        return None
    return {"Authorization": f"token {GITHUB_TOKEN}"}

# Функция для безопасного преобразования времени
def safe_time_parse(time_str):
    try:
        # Пробуем разные форматы времени
        for fmt in ("%H:%M", "%H:%M:%S", "%H.%M"):
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        # Если ни один формат не подошел, возвращаем минимальное время
        return datetime.min.time()
    except:
        return datetime.min.time()

def archive_data():
    """Переносит старые данные в отдельный архивный Gist"""
    try:
        old_data = st.session_state.data.copy()
        for key in ['_temp', '_cache']:
            old_data.pop(key, None)

        def json_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        json_str = json.dumps(old_data, indent=4, ensure_ascii=False, default=json_serializer)

        headers = github_headers()
        if not headers:
            return False

        resp = requests.post(
            "https://api.github.com/gists",
            headers=headers,
            json={
                "description": f"Архив от {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "public": False,
                "files": {"archive_center_data.json": {"content": json_str}}
            }
        )

        if resp.status_code == 201:
            gist_data = resp.json()
            st.session_state.data.setdefault('_archives', []).append({
                'url': gist_data['html_url'],
                'created': datetime.now().isoformat(),
                'id': gist_data['id'],
                'size': len(json_str)
            })
            # st.session_state.data['payments'] = [] # Отключено для безопасности
            # st.session_state.data['attendance'] = {} # Отключено для безопасности
            if save_data(st.session_state.data):
                st.success(f"Архив создан: {gist_data['html_url']}")
                return True
        else:
            st.error(f"Ошибка архивации: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        st.error(f"Ошибка архивации: {str(e)}")
        return False


def save_data(data):
    """Сохраняет данные локально и в Gist через API"""
    try:
        def json_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        json_str = json.dumps(data, indent=4, ensure_ascii=False, default=json_serializer)

        # Локальное сохранение
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            f.write(json_str)

        # Сохранение в GitHub
        if GITHUB_TOKEN and GIST_ID:
            headers = github_headers()
            if not headers:
                return False

            resp = requests.patch(
                f"https://api.github.com/gists/{GIST_ID}",
                headers=headers,
                json={"files": {"center_data.json": {"content": json_str}}}
            )

            if resp.status_code == 200:
                st.success("Данные синхронизированы с GitHub!")
            else:
                st.error(f"Ошибка обновления Gist: {resp.status_code} {resp.text}")
                return False
        for payment in data['payments']:
            if payment['student_id'] not in [s['id'] for s in data['students']]:
                st.error(f"Ошибка целостности: платеж для несуществующего ученика {payment['student_id']}")
                
        return True
        
    except Exception as e:
        st.error(f"Ошибка сохранения: {str(e)}")
        return False


# Initialize session state for the app
if 'data' not in st.session_state:
    st.session_state.data = load_data()
    required_keys = {
        'news': [],
        'directions': [],
        'subdirections': [], 
        'students': [],
        'teachers': [],
        'parents': [],
        'payments': [],
        'schedule': [],
        'archived_schedule': [],
        'materials': [],
        'single_lessons': [], 
        'kanban_tasks': {'ToDo': [], 'InProgress': [], 'Done': []},
        'attendance': {},
        'settings': {'trial_cost': 500, 'single_cost_multiplier': 1.5}
    }
    
    for key, default_value in required_keys.items():
        if key not in st.session_state.data:
            st.session_state.data[key] = default_value

# Ensure schedule_exceptions exists
if 'schedule_exceptions' not in st.session_state.data:
    st.session_state.data['schedule_exceptions'] = {}

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


# --- НОВЫЕ ФУНКЦИИ ЛОГИКИ ---

# --- БЛОК КОНТРОЛЯ И ЛОГОВ (Вставить после импортов) ---
import csv

LOG_FILE = 'audit_log.csv'

def log_action(user, action, details):
    """Записывает действие в файл, не нагружая память"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Если файла нет, создаем заголовок
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Время', 'Пользователь', 'Действие', 'Детали'])
            
    # Дописываем строку
    try:
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, user, action, details])
    except Exception as e:
        print(f"Ошибка лога: {e}")

def show_audit_log_page():
    """Страница просмотра истории"""
    st.title("🕵️ История действий администраторов")
    
    if not os.path.exists(LOG_FILE):
        st.info("История действий пока пуста.")
        return

    # Читаем файл
    try:
        df = pd.read_csv(LOG_FILE)
        # Сортируем: новые сверху
        df = df.sort_values(by="Время", ascending=False)
        
        # Фильтры для удобства
        col1, col2 = st.columns(2)
        with col1:
            user_filter = st.multiselect("Фильтр по админу", options=df['Пользователь'].unique())
        with col2:
            action_filter = st.multiselect("Фильтр по действию", options=df['Действие'].unique())
            
        if user_filter:
            df = df[df['Пользователь'].isin(user_filter)]
        if action_filter:
            df = df[df['Действие'].isin(action_filter)]
            
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.download_button(
            label="📥 Скачать историю (CSV)",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name='audit_log.csv',
            mime='text/csv',
        )
        
        # Кнопка очистки (только для главного)
        if st.session_state.username == 'admin':
            if st.button("🗑 Очистить историю (Осторожно!)"):
                os.remove(LOG_FILE)
                st.rerun()
                
    except Exception as e:
        st.error(f"Ошибка чтения логов: {e}")

# 1. Логирование (Простой вариант без лишней памяти)
LOG_FILE = 'audit_log.csv'
def log_action(user, action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user, action, details])

# 2. Умный расчет стоимости и уроков в месяце
def get_month_lessons(direction_name, year, month):
    """Считает даты занятий в конкретном месяце по расписанию"""
    lessons_dates = []
    # Находим дни недели, когда идет это направление (0=Пн, 6=Вс)
    target_days = set()
    for l in st.session_state.data['schedule']:
        if l['direction'] == direction_name:
            # Преобразуем русские дни в цифры
            days_map = {'Понедельник':0, 'Вторник':1, 'Среда':2, 'Четверг':3, 'Пятница':4, 'Суббота':5, 'Воскресенье':6}
            if l['day'] in days_map:
                target_days.add(days_map[l['day']])
    
    if not target_days:
        return []

    # Перебираем все дни месяца
    import calendar
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        date_obj = date(year, month, day)
        if date_obj.weekday() in target_days:
            lessons_dates.append(date_obj)
    return lessons_dates

# 3. Определение реального учителя (с учетом замен)
def get_teacher_for_lesson(lesson_id, lesson_date_str):
    """Возвращает ID учителя: либо основного, либо заменяющего"""
    # Проверяем исключения (замены)
    exceptions = st.session_state.data.get('schedule_exceptions', {})
    if lesson_date_str in exceptions and lesson_id in exceptions[lesson_date_str]:
        exc = exceptions[lesson_date_str][lesson_id]
        if exc['type'] == 'substitution':
            return exc['teacher_id']
        if exc['type'] == 'cancel':
            return None # Урок отменен
            
    # Если замен нет, ищем основного в расписании
    for l in st.session_state.data['schedule']:
        if l['id'] == lesson_id:
            return l['teacher_id']
    return None

# 4. Финансы: Получение цены одного занятия
def get_lesson_price(direction_name):
    for d in st.session_state.data['directions']:
        if d['name'] == direction_name:
            # Считаем, что в абонементе в среднем 8 занятий
            # Или можно сделать точнее: делить на кол-во занятий в текущем месяце
            return d['cost'] / 8 
    return 0


# --- Authentication Functions ---
def login(username, password):
    """Проверяет логин/пароль"""
    users = get_users()
    if username in users and users[username]["password"] == password:
        st.session_state.update({
            "authenticated": True,
            "username": username,
            "role": users[username]["role"],
            "teacher_id": users[username]["teacher_id"]
        })
        log_action(username, "Login", "User logged in")
        st.success(f"Добро пожаловать, {username}!")
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
    log_action(st.session_state.username, "Logout", "User logged out")
    st.session_state.page = 'login'
    st.info("Вы вышли из системы.")
    st.rerun()

# --- Helper Functions ---
def calculate_lessons_in_month(direction_name, selected_date):
    """Вычисляет количество занятий по направлению в текущем месяце"""
    # Получаем дни недели для этого направления из расписания
    schedule_days = set()
    for lesson in st.session_state.data['schedule']:
        if lesson['direction'] == direction_name:
            schedule_days.add(lesson['day'])
    
    if not schedule_days:
        return 0
    
    # Словарь для перевода русских дней в английские
    day_translation = {
        'Понедельник': 'Monday',
        'Вторник': 'Tuesday',
        'Среда': 'Wednesday',
        'Четверг': 'Thursday',
        'Пятница': 'Friday',
        'Суббота': 'Saturday',
        'Воскресенье': 'Sunday'
    }
    
    # Считаем количество занятий в месяце
    from calendar import monthrange
    year = selected_date.year
    month = selected_date.month
    _, num_days = monthrange(year, month)
    
    count = 0
    for day in range(1, num_days + 1):
        date = datetime(year, month, day)
        english_day = date.strftime('%A')
        
        # Находим русское название дня
        for ru_day, en_day in day_translation.items():
            if en_day == english_day:
                if ru_day in schedule_days:
                    count += 1
                break
                
    return count

def get_student_by_id(student_id):
    """Get student by ID without caching"""
    return next((s for s in st.session_state.data['students'] if s.get('id') == student_id), None)
def get_payments_for_student(student_id):
    """Get payments with immediate updates"""
    payments = []
    for p in st.session_state.data['payments']:
        if p['student_id'] == student_id:
            # Проверяем прямое направление
            student = get_student_by_id(student_id)
            if p['direction'] in student.get('directions', []):
                payments.append(p)
            # Проверяем поднаправления
            elif any(p['direction'] == f"{s['parent']} ({s['name']})" 
                    for s in st.session_state.data.get('subdirections', [])
                    if s['name'] == student['name']):
                payments.append(p)
    return payments
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
def refresh_data():
    """Полностью перезагружает данные, очищает кэш и состояние UI."""
    # Очищаем кэш функций, помеченных декоратором @st.cache_data
    st.cache_data.clear()

    # Перезагружаем основные данные из источника (локальный файл или GitHub)
    st.session_state.data = load_data()

    # Сбрасываем переменные состояния UI, которые могут содержать устаревшие ID или фильтры.
    # Это предотвращает отображение закэшированных представлений.
    keys_to_reset = [
        'selected_teacher_id', 'edit_student_id', 'edit_direction_id', 
        'edit_teacher_id', 'filter_direction', 'recurring_lesson_id',
        'att_key' # Удаляем временные ключи от таблиц посещений
    ]
    
    # Безопасно удаляем ключи, если они существуют
    for key in list(st.session_state.keys()):
        # Проверяем как точное совпадение, так и начало ключа (для динамических ключей)
        if key in keys_to_reset or key.startswith('att_'):
            del st.session_state[key]

    st.success("Данные и кэш интерфейса были принудительно обновлены!")
    
    # Принудительно перезапускаем приложение, чтобы все изменения вступили в силу
    st.rerun()
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

# Добавьте эту функцию в ваш код для просмотра истории
def show_gist_history():
    """Выводит историю изменений Gist через GitHub API"""
    gist_id = st.secrets["GIST_ID"]
    commits_url = f"{GITHUB_API}/gists/{gist_id}/commits"

    try:
        commits_resp = requests.get(commits_url, headers=github_headers())
        commits_resp.raise_for_status()
        commits = commits_resp.json()

        st.write("Последние изменения:")
        for commit in commits:
            commit_id = commit["version"]
            committed_at = commit["committed_at"]

            # Загружаем содержимое конкретной версии
            gist_version_url = f"{GITHUB_API}/gists/{gist_id}/{commit_id}"
            gist_version_resp = requests.get(gist_version_url, headers=github_headers())
            gist_version_resp.raise_for_status()

            files = gist_version_resp.json().get("files", {})
            content = files.get("center_data.json", {}).get("content", "")

            st.write(f"Версия от {committed_at}:")
            st.code(content[:200] + "...")  # Показываем начало файла

    except Exception as e:
        st.error(f"Ошибка при загрузке истории Gist: {str(e)}")

# Проверка соединения с GitHub (только для админов)
if st.session_state.get('authenticated') and st.session_state.role == 'admin':
    if st.sidebar.button("Проверить GitHub соединение"):
        try:
            resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=github_headers())
            if resp.status_code == 200:
                gist = resp.json()
                content_preview = gist["files"]["center_data.json"]["content"][:200] + "..." if "center_data.json" in gist["files"] else "Файл не найден"
                st.sidebar.success("✅ Соединение с GitHub установлено")
                st.sidebar.markdown(f"**Последнее обновление:** {gist['updated_at']}")
                st.sidebar.markdown(f"**Размер данных:** {len(content_preview)/1024:.1f} KB")
                st.sidebar.text_area("Предпросмотр данных", content_preview, height=100)
            else:
                st.sidebar.error(f"❌ Ошибка подключения: {resp.status_code} {resp.text}")
        except Exception as e:
            st.sidebar.error(f"❌ Ошибка подключения: {str(e)}")
if st.session_state.role == 'admin' or st.session_state.role == 'reception':
    if st.sidebar.button("🔄 Обновить все данные"):
        refresh_data()
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

    # Выбор даты с ограничением на будущие даты
    selected_date = st.date_input(
        "Выберите дату для сообщения",
        value=date.today(),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=60))

    # Определяем день недели
    day_name = selected_date.strftime("%A")
    day_map = {
        "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
        "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
    }
    russian_day = day_map.get(day_name, day_name)

    # Расширенный выбор стикеров
    sticker_options = {
        "Осенний листок": "🍁",
        "Осенний дождь": "🌧️",
        "Зимний снежок": "❄️",
        "Снеговик": "☃️",
        "Цветок": "🌸",
        "Солнце": "🌞",
        "Радуга": "🌈",
        "Бабочка": "🦋",
        "Клевер": "🍀",
        "Сердце": "💖",
        "Звезда": "✨",
        "Улыбка": "😊",
        "Книжка": "📖",
        "Корона": "👑",
        "Новогодняя ёлка": "🎄",
        "Подарок": "🎁",
        "Новогодний шар": "🎊",
        "Фейерверк": "🎆",
        "Салют": "🎇",
        "Валентинка": "💌",
        "Воздушный шар": "🎈",
        "Конфетти": "🎉",
        "Весенний дождь": "🌦️"
        
    }
    selected_sticker_name = st.selectbox("Выберите стикер", list(sticker_options.keys()))
    sticker = sticker_options[selected_sticker_name]

    if st.button("Сгенерировать сообщение"):
        # 1. Собираем регулярные занятия
        regular_lessons = [
            {'time': l['start_time'], 'direction': l['direction']}
            for l in st.session_state.data['schedule']
            if l['day'] == russian_day
        ]
        
        # 2. Добавляем разовые занятия на эту дату
        single_lessons = [
            {'time': l['start_time'], 'direction': l['direction']}
            for l in st.session_state.data.get('single_lessons', [])
            if l['date'] == selected_date.strftime("%Y-%m-%d")
        ]
        
        # 3. Фильтруем по преподавателю (если это учитель)
        if st.session_state.role == 'teacher':
            teacher = get_teacher_by_id(st.session_state.teacher_id)
            if teacher:
                teacher_name = teacher.get('name', '')
                regular_lessons = [
                    l for l in regular_lessons 
                    if any(
                        t['name'] == teacher_name 
                        for t in st.session_state.data['teachers'] 
                        if l['direction'] in t.get('directions', [])
                    )
                ]
                single_lessons = [
                    l for l in single_lessons 
                    if any(
                        t['name'] == teacher_name 
                        for t in st.session_state.data['teachers'] 
                        if l['direction'] in t.get('directions', [])
                    )
                ]
        
        # 4. Объединяем и сортируем
        all_lessons = regular_lessons + single_lessons
        all_lessons.sort(key=lambda x: x['time'])
        
        if all_lessons:
            # Формируем сообщение
            message = f"Доброе утро!{sticker}\n"
            message += f"Напоминаем о занятиях на {selected_date.strftime('%d.%m.%Y')}:\n\n"
            
            for lesson in all_lessons:
                message += f"{lesson['time']} - {lesson['direction']}\n"
            
            message += "\nЖдем вас!"
            
            # Отображаем и добавляем кнопку WhatsApp
            st.text_area("Готовое сообщение", message, height=150)
            
            # Используем urllib.parse.quote для безопасного кодирования всей строки
            encoded_message = quote(message)
            whatsapp_link = f"https://wa.me/?text={encoded_message}"
            
            st.markdown(
                f"""
                <a href="{whatsapp_link}" target="_blank">
                    <button style="
                        background-color:#25D366;
                        color:white;
                        border:none;
                        padding:12px 24px;
                        border-radius:8px;
                        font-size:16px;
                        margin-top:10px;
                        width:100%;
                    ">
                        📱 Отправить в WhatsApp
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )
        else:
            st.warning(f"На {selected_date.strftime('%d.%m.%Y')} нет занятий")
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
                log_action(st.session_state.username, "Add News", f"Added news: {news_id}")
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
                    log_action(st.session_state.username, "Delete News", f"Deleted news: {news['id']}")
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
                    log_action(st.session_state.username, "Add Direction", f"Added: {name}")
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
                #  подсчет учеников :
                student_count = 0
                has_subdirections = any(sub['parent'] == d['name'] for sub in st.session_state.data.get('subdirections', []))

                if has_subdirections:
                    # Для направлений с поднаправлениями - считаем количество поднаправлений
                    student_count = len([sub for sub in st.session_state.data.get('subdirections', []) 
                                        if sub['parent'] == d['name']])
                else:
                    # Для обычных направлений - считаем учеников как раньше
                    student_count = len([s for s in students if d['name'] in s.get("directions", [])])
                table_data.append({
                    "id": d["id"],
                    "Название": d["name"],
                    "Описание": d.get("description", ""),
                    "Стоимость": d.get("cost", 0),
                    "Разовое": d.get("trial_cost", 0),
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
                    "Разовое": st.column_config.NumberColumn(format="%.0f ₽")
                }
            )

            if st.button("💾 Сохранить изменения"):
                for i, row in edited_df.iterrows():
                    for d in directions:
                        if d["id"] == row["id"]:
                            d["name"] = row["Название"]
                            d["description"] = row["Описание"]
                            d["cost"] = row["Стоимость"]
                            d["trial_cost"] = row["Разовое"]
                            d["gender"] = row["Пол"] if row["Пол"] != "Любой" else None
                            try:
                                min_a, max_a = map(int, str(row["Возраст"]).split('-'))
                                d["min_age"] = min_a
                                d["max_age"] = max_a
                            except Exception:
                                pass
                save_data(st.session_state.data)
                log_action(st.session_state.username, "Edit Directions", "Updated directions table")
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
                #  подсчет учеников:
                student_count = 0
                has_subdirections = any(sub['parent'] == d['name'] for sub in st.session_state.data.get('subdirections', []))

                if has_subdirections:
                    # Для направлений с поднаправлениями - считаем количество поднаправлений
                    student_count = len([sub for sub in st.session_state.data.get('subdirections', []) 
                                        if sub['parent'] == d['name']])
                else:
                    # Для обычных направлений - считаем учеников как раньше
                    student_count = len([s for s in students if d['name'] in s.get("directions", [])])
                with st.container(border=True):
                    st.subheader(d["name"])
                    st.caption(d.get("description", ""))
                    col1, col2, col3 = st.columns(3)
                    col1.metric("💵 Абонемент", f"{d.get('cost', 0):.0f} ₽")
                    col2.metric("🎫 Разовое", f"{d.get('trial_cost', 0):.0f} ₽")
                    col3.metric("👥 Учеников", student_count)

                    age_str = f"{d.get('min_age', '?')} - {d.get('max_age', '?')} лет"
                    st.markdown(f"**Возраст:** {age_str} | **Пол:** {d.get('gender', 'Любой')}")
        else:
            st.info("Нет направлений для отображения.")
    st.subheader("🎯 Поднаправления (для индивидуальных занятий)")

    # Создаем таблицу поднаправлений
    subdirections = st.session_state.data.setdefault('subdirections', [])

    # Добавление нового поднаправления
    with st.expander("➕ Добавить поднаправление", expanded=False):
        with st.form("new_subdirection_form"):
            col1, col2 = st.columns(2)
            with col1:
                parent_dir = st.selectbox("Основное направление", 
                                    [d['name'] for d in st.session_state.data['directions']])
            with col2:
                sub_name = st.text_input("Название поднаправления*")
            
            if st.form_submit_button("Добавить"):
                if sub_name:
                    new_sub = {
                        'id': str(uuid.uuid4()),
                        'parent': parent_dir,
                        'name': sub_name
                    }
                    subdirections.append(new_sub)
                    save_data(st.session_state.data)
                    log_action(st.session_state.username, "Add Subdirection", f"{sub_name} to {parent_dir}")
                    st.success("Поднаправление добавлено!")
                    st.rerun()
                else:
                    st.error("Название обязательно")

    # Отображение и редактирование таблицы поднаправлений
    if subdirections:
        df_subs = pd.DataFrame(subdirections)
        df_subs['Удалить'] = False
        
        edited_subs = st.data_editor(
            df_subs[['parent', 'name', 'Удалить']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "parent": "Основное направление",
                "name": "Поднаправление",
                "Удалить": st.column_config.CheckboxColumn("Удалить?")
            }
        )
        
        if st.button("💾 Сохранить изменения поднаправлений"):
            for i, row in edited_subs.iterrows():
                if not row['Удалить']:
                    subdirections[i]['parent'] = row['parent']
                    subdirections[i]['name'] = row['name']
            
            # Удаляем отмеченные
            st.session_state.data['subdirections'] = [
                s for i, s in enumerate(subdirections) 
                if not edited_subs.iloc[i]['Удалить']
            ]
            save_data(st.session_state.data)
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Нет поднаправлений")
def show_financial_control_page():
    st.title("💰 Управление Оплатами и Абонементами")
    
    tabs = st.tabs(["📊 Сетка Абонементов", "🔄 Переносы и Замены", "🗂 История операций"])

    # --- ТАБ 1: Визуальная сетка (как просила, с квадратиками) ---
    with tabs[0]:
        st.subheader("Состояние абонементов на текущий месяц")
        
        # Фильтр по направлению
        all_dirs = [d['name'] for d in st.session_state.data['directions']]
        selected_dir = st.selectbox("Фильтр по направлению:", ["Все"] + all_dirs)
        
        current_year = date.today().year
        current_month = date.today().month
        
        # Проходим по ученикам
        for s in st.session_state.data['students']:
            # Фильтр направлений ученика
            student_dirs = s['directions']
            if selected_dir != "Все":
                if selected_dir not in student_dirs:
                    continue
                student_dirs = [selected_dir] # Показываем только выбранное

            if not student_dirs: continue

            with st.container(border=True):
                st.markdown(f"**👤 {s['name']}**")
                
                for d_name in student_dirs:
                    st.write(f"*{d_name}*")
                    # Получаем все даты занятий в этом месяце
                    dates = get_month_lessons(d_name, current_year, current_month)
                    
                    # --- ДОБАВЛЕНИЕ: Учитываем фактические посещения (даже если расписание изменилось) ---
                    attendance_dates = set()
                    for date_str, lessons_data in st.session_state.data.get('attendance', {}).items():
                        try:
                            d_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                            if d_date_obj.year == current_year and d_date_obj.month == current_month:
                                for l_id, students_in_l in lessons_data.items():
                                    if s['id'] in students_in_l:
                                        # Ищем занятие в расписании или архиве
                                        all_lessons_source = st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', []) + st.session_state.data.get('archived_schedule', [])
                                        l_info = next((l for l in all_lessons_source if l['id'] == l_id), None)
                                        if l_info and l_info.get('direction') == d_name:
                                            attendance_dates.add(d_date_obj)
                        except:
                            pass
                    
                    # Объединяем плановые даты и даты фактических посещений
                    dates = sorted(list(set(dates) | attendance_dates))
                    # -----------------------------------------------------------------------------------
                    
                    # Рисуем "квадратики"
                    cols = st.columns(len(dates) if dates else 1)
                    
                    attended_count = 0
                    for i, d_date in enumerate(dates):
                        d_str = d_date.strftime("%Y-%m-%d")
                        status = "future" # future, present, sick, skip
                        
                        # Проверяем посещаемость
                        # (Тут упрощенный поиск, в реальности надо перебрать уроки этого дня)
                        attendance_day = st.session_state.data.get('attendance', {}).get(d_str, {})
                        is_present = False
                        is_sick = False
                        
                        # Ищем, был ли ученик на любом уроке этого направления в этот день
                        for l_id, students_in_l in attendance_day.items():
                             # Надо проверить, относится ли урок к направлению (нужен маппинг)
                             if s['id'] in students_in_l:
                                # Проверяем, относится ли урок к текущему направлению
                                all_lessons_source = st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', []) + st.session_state.data.get('archived_schedule', [])
                                lesson_info = next((l for l in all_lessons_source if l['id'] == l_id), None)
                                
                                if lesson_info and lesson_info.get('direction') == d_name and s['id'] in students_in_l:
                                    record = students_in_l[s['id']]
                                    if record.get('present'):
                                        is_present = True
                                    elif 'болел' in str(record.get('note', '')).lower():
                                        is_sick = True
                        
                        # Визуализация квадратика
                        color = "gray" # Будущее
                        if d_date < date.today(): color = "#ffcccb" # Прогул (красный)
                        if is_present: 
                            color = "#90ee90" # Был (зеленый)
                            attended_count += 1
                        if is_sick: color = "#ffd700" # Болел (желтый)
                        
                        if i < len(cols):
                            cols[i].markdown(f"""
                                <div style="background-color: {color}; padding: 5px; text-align: center; border-radius: 4px; font-size: 0.8em;">
                                {d_date.day}
                                </div>
                                """, unsafe_allow_html=True)
                    
                    # Полоска прогресса и сумма
                    total = len(dates)
                    
                    if total > 0:
                        st.progress(attended_count / total)
                        
                        # Считаем оплаты за текущий месяц
                        total_paid = 0
                        for p in st.session_state.data['payments']:
                            if p['student_id'] == s['id'] and p['direction'] == d_name:
                                try:
                                    p_date = datetime.strptime(p['date'], "%Y-%m-%d").date()
                                    if p_date.year == current_year and p_date.month == current_month:
                                        total_paid += p['amount']
                                except:
                                    pass
                        
                        # Расчет использованных средств на основе ОПЛАЧЕННОГО
                        cost_per_lesson_paid = total_paid / total if total > 0 else 0
                        used = attended_count * cost_per_lesson_paid
                        
                        balance = total_paid - used
                        st.caption(f"Оплачено: {total_paid:.0f} ₽ | Использовано: {used:.0f} ₽ | Остаток: {balance:.0f} ₽ (Посещено {attended_count}/{total})")

    # --- ТАБ 2: Замены преподавателей и Перерасчет ---
    with tabs[1]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👨‍🏫 Замена преподавателя")
            sub_date = st.date_input("Дата замены")
            sub_date_str = sub_date.strftime("%Y-%m-%d")
            
            # Найти уроки в этот день
            day_name_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][sub_date.weekday()]
            lessons_today = [l for l in st.session_state.data['schedule'] if l['day'] == day_name_ru]
            
            if lessons_today:
                l_options = {l['id']: f"{l['start_time']} - {l['direction']} ({l['teacher']})" for l in lessons_today}
                selected_l_id = st.selectbox("Выберите занятие", list(l_options.keys()), format_func=lambda x: l_options[x])
                
                new_teacher = st.selectbox("Кто заменяет?", [t['name'] for t in st.session_state.data['teachers']])
                new_teacher_id = next(t['id'] for t in st.session_state.data['teachers'] if t['name'] == new_teacher)
                
                if st.button("Сохранить замену"):
                    if 'schedule_exceptions' not in st.session_state.data:
                        st.session_state.data['schedule_exceptions'] = {}
                    if sub_date_str not in st.session_state.data['schedule_exceptions']:
                        st.session_state.data['schedule_exceptions'][sub_date_str] = {}
                    
                    st.session_state.data['schedule_exceptions'][sub_date_str][selected_l_id] = {
                        "type": "substitution",
                        "teacher_id": new_teacher_id,
                        "orig_teacher_name": l_options[selected_l_id]
                    }
                    save_data(st.session_state.data)
                    log_action(st.session_state.username, "Замена учителя", f"{sub_date_str}: {new_teacher}")
                    st.success("Замена сохранена! Зарплата посчитается новому учителю.")
            else:
                st.warning("В этот день нет занятий по расписанию.")

        with col2:
            st.subheader("🔄 Перенос средств (Болезнь/Отработка)")
            st.info("Используйте это, если ребенок проболел и нужно перекинуть деньги на след. месяц или другое направление.")
            st.subheader("🔄 Перенос средств и Отработка")
            st.info("Перенос оплаты с одного направления на другое или на следующий месяц.")
            
            p_student_name = st.selectbox("Ученик", [s['name'] for s in st.session_state.data['students']])
            p_student = None
            if p_student_name:
                p_student = next((s for s in st.session_state.data['students'] if s['name'] == p_student_name), None)
            
            if not p_student:
                st.warning("Выберите ученика")
                st.stop()
            
            # Выбор источника средств
            source_dir = st.selectbox("С какого направления списать?", p_student.get('directions', []))
            
            # Выбор цели
            target_type = st.radio("Куда перенести?", ["На следующий месяц (то же направление)", "На другое направление (Отработка)"])
            
            target_dir = source_dir
            target_date_start = date.today()
            create_lesson = False
            target_date_obj = None
            
            if target_type == "На следующий месяц (то же направление)":
                # Вычисляем первое число следующего месяца
                if date.today().month == 12:
                    target_date_start = date(date.today().year + 1, 1, 1)
                else:
                    target_date_start = date(date.today().year, date.today().month + 1, 1)
            elif target_type == "На другое направление (Отработка)":
                all_dirs = [d['name'] for d in st.session_state.data['directions']]
                target_dir = st.selectbox("Выберите направление для зачисления", all_dirs)
                create_lesson = True
                target_date_obj = st.date_input("Дата занятия для отработки", min_value=date.today())
            
            amount = st.number_input("Сумма к переносу (руб)", min_value=0, step=100)
            reason = st.text_input("Причина (напр. Болезнь)", value="Перенос занятий")
            
            if st.button("Выполнить перенос"):
                # 1. Списание с текущего
                debit_payment = {
                    "id": str(uuid.uuid4()),
                    "student_id": p_student['id'],
                    "date": str(date.today()),
                    "amount": -amount,
                    "direction": source_dir,
                    "type": "Перенос (списание)",
                    "notes": f"{reason} -> {target_dir} ({target_type})"
                }
                st.session_state.data['payments'].append(debit_payment)
                
                # 2. Зачисление на новое
                credit_payment = {
                    "id": str(uuid.uuid4()),
                    "student_id": p_student['id'],
                    "date": str(target_date_start),
                    "amount": amount,
                    "direction": target_dir,
                    "type": "Перенос (зачисление)",
                    "notes": f"Из {source_dir}: {reason}"
                }
                st.session_state.data['payments'].append(credit_payment)
                
                # 3. Если перенос на другое направление - создаем запись на занятие (отработку)
                if create_lesson and target_date_obj:
                    # Ищем преподавателя для этого направления в этот день
                    day_name = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][target_date_obj.weekday()]
                    
                    # Пытаемся найти регулярное занятие
                    target_teacher_name = "Не назначен"
                    target_teacher_id = None
                    
                    found_lesson = next((l for l in st.session_state.data['schedule'] if l['direction'] == target_dir and l['day'] == day_name), None)
                    if found_lesson:
                        target_teacher_name = found_lesson['teacher']
                        # Находим ID учителя
                        t_obj = next((t for t in st.session_state.data['teachers'] if t['name'] == target_teacher_name), None)
                        if t_obj: target_teacher_id = t_obj['id']

                    new_single_lesson = {
                        'id': str(uuid.uuid4()),
                        'student_id': p_student['id'],
                        'direction': target_dir,
                        'teacher': target_teacher_name,
                        'teacher_id': target_teacher_id,
                        'date': str(target_date_obj),
                        'start_time': found_lesson['start_time'] if found_lesson else "00:00",
                        'end_time': found_lesson['end_time'] if found_lesson else "00:00",
                        'type': 'makeup', # Отработка
                        'notes': f"Отработка: {reason}",
                        'cost': amount # Сохраняем сумму переноса для учителя
                    }
                    st.session_state.data.setdefault('single_lessons', []).append(new_single_lesson)
                    
                    # Автоматически создаем запись в посещаемости с оплатой (галочка оплачено)
                    date_key = str(target_date_obj)
                    if date_key not in st.session_state.data['attendance']:
                        st.session_state.data['attendance'][date_key] = {}
                    
                    if new_single_lesson['id'] not in st.session_state.data['attendance'][date_key]:
                         st.session_state.data['attendance'][date_key][new_single_lesson['id']] = {}

                    st.session_state.data['attendance'][date_key][new_single_lesson['id']][p_student['id']] = {
                        'present': False, 
                        'paid': True,     # Оплачено переносом
                        'note': f"Перенос: {reason}"
                    }

                save_data(st.session_state.data)
                log_action(st.session_state.username, "Перенос средств", f"{p_student_name}: +{amount} ({reason})")
                st.success(f"Баланс обновлен! Текущий: {p_student['balance']}")
                log_action(st.session_state.username, "Перенос средств", f"{p_student_name}: {amount}р {source_dir}->{target_dir}")
                st.success(f"Перенос выполнен! Списано с '{source_dir}', зачислено на '{target_dir}' ({target_date_start})")

    # --- ТАБ 3: История операций ---
    with tabs[2]:
        st.subheader("📜 История операций (Замены, Отработки, Переносы)")
        
        history_data = []
        
        # 1. Замены
        exceptions = st.session_state.data.get('schedule_exceptions', {})
        for date_str, lessons in exceptions.items():
            for l_id, exc in lessons.items():
                if exc.get('type') == 'substitution':
                    teacher_name = next((t['name'] for t in st.session_state.data['teachers'] if t['id'] == exc['teacher_id']), "Неизвестно")
                    history_data.append({
                        "id": l_id,
                        "source": "substitution",
                        "date_key": date_str,
                        "Дата": date_str,
                        "Тип": "Замена преподавателя",
                        "Описание": f"{exc.get('orig_teacher_name')} -> {teacher_name}",
                        "Сумма": "Расчет ЗП"
                    })

        # 2. Отработки / Разовые (Single Lessons)
        for sl in st.session_state.data.get('single_lessons', []):
            student_name = next((s['name'] for s in st.session_state.data['students'] if s['id'] == sl['student_id']), "Неизвестный")
            history_data.append({
                "id": sl['id'],
                "source": "single_lesson",
                "date_key": sl['date'],
                "Дата": sl['date'],
                "Тип": "Отработка/Разовое",
                "Описание": f"{student_name} ({sl['direction']}) к {sl['teacher']}",
                "Сумма": "По тарифу"
            })

        # 3. Переносы (Payments)
        for p in st.session_state.data.get('payments', []):
            if "Перенос" in p.get('type', '') or "Перенос" in str(p.get('notes', '')):
                student_name = next((s['name'] for s in st.session_state.data['students'] if s['id'] == p['student_id']), "Неизвестный")
                history_data.append({
                    "id": p['id'],
                    "source": "payment",
                    "date_key": p['date'],
                    "Дата": p['date'],
                    "Тип": f"Финансы ({p.get('type')})",
                    "Описание": f"{student_name}: {p.get('notes')}",
                    "Сумма": f"{p['amount']} ₽"
                })
        
        if history_data:
            df_hist = pd.DataFrame(history_data)
            df_hist['Удалить'] = False
            df_hist = df_hist.sort_values('Дата', ascending=False)

            edited_hist = st.data_editor(
                df_hist,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": None, "source": None, "date_key": None,
                    "Удалить": st.column_config.CheckboxColumn("Удалить?")
                }
            )
            
            if st.button("🗑️ Удалить выбранные операции"):
                to_delete = edited_hist[edited_hist['Удалить']]
                for _, row in to_delete.iterrows():
                    if row['source'] == 'substitution':
                        if row['date_key'] in st.session_state.data['schedule_exceptions']:
                            if row['id'] in st.session_state.data['schedule_exceptions'][row['date_key']]:
                                del st.session_state.data['schedule_exceptions'][row['date_key']][row['id']]
                    elif row['source'] == 'single_lesson':
                        st.session_state.data['single_lessons'] = [
                            sl for sl in st.session_state.data['single_lessons'] if sl['id'] != row['id']
                        ]
                    elif row['source'] == 'payment':
                        st.session_state.data['payments'] = [
                            p for p in st.session_state.data['payments'] if p['id'] != row['id']
                        ]
                
                save_data(st.session_state.data)
                st.success("Операции удалены!")
                st.rerun()
        else:
            st.info("История операций пуста")
def show_student_card(student_id):
    student = get_student_by_id(student_id)
    if not student:
        st.warning("Ученик не найден.")
        return

    parent = get_parent_by_id(student.get('parent_id'))
    with st.container():
        st.markdown(f"### 📘 {student['name']}")
        st.write(f"👤 **Пол:** {student.get('gender')}")
        st.write(f"🎂 **Дата рождения:** {student.get('dob')} — {calculate_age(student.get('dob'))} лет")
        st.write(f"📆 Зарегистрирован: {student.get('registration_date')}")
        st.write(f"📝 Заметки: {student.get('notes', '')}")
        if parent:
            st.write(f"👪 Родитель: {parent.get('name')} | 📞 {parent.get('phone')}")

        st.subheader("🎯 Направления")

        if not isinstance(student.get("directions"), list):
            student["directions"] = [student["directions"]] if student.get("directions") else []

        for d in student["directions"]:
            with st.form(f"unassign_form_{student['id']}_{d}"):
                if st.form_submit_button(f"❌ Отписать от {d}"):
                    student["directions"] = [x for x in student["directions"] if x != d]
                    save_data(st.session_state.data)
                    log_action(st.session_state.username, "Unassign Direction", f"Removed {d} from {student['name']}")
                    st.success(f"Ученик отписан от {d}")
                    st.rerun()

        available = (
            [d['name'] for d in st.session_state.data['directions'] if d['name'] not in student["directions"]] +
            [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', []) 
            if f"{s['parent']} ({s['name']})" not in student.get("directions", [])]
        )

        if available:
            with st.form(f"assign_dir_form_{student['id']}"):
                new_dir = st.selectbox("Добавить направление", available, key=f"dir_sel_{student['id']}")
                if st.form_submit_button("Добавить"):
                    student["directions"].append(new_dir)
                    save_data(st.session_state.data)
                    log_action(st.session_state.username, "Assign Direction", f"Added {new_dir} to {student['name']}")
                    st.success(f"Добавлено направление {new_dir}")
                    st.rerun()

        # --- ТАБЛИЦА ПЕРЕНОСОВ И ОТРАБОТОК ---
        st.subheader("🔄 История переносов и разовых занятий")
        student_single_lessons = [
            sl for sl in st.session_state.data.get('single_lessons', [])
            if sl['student_id'] == student['id']
        ]
        
        if student_single_lessons:
            sl_data = []
            for sl in student_single_lessons:
                sl_data.append({
                    "Дата": sl['date'],
                    "Направление": sl['direction'],
                    "Преподаватель": sl['teacher'],
                    "Тип": sl.get('type', 'Разовое'),
                    "Примечание": sl.get('notes', '')
                })
            st.dataframe(pd.DataFrame(sl_data), use_container_width=True, hide_index=True)

        st.subheader("💳 Оплаты")
        payments = []
        for p in st.session_state.data['payments']:
            if p['student_id'] == student['id']:
                if p['direction'] in student.get('directions', []):
                    payments.append(p)
                elif any(p['direction'] == f"{s['parent']} ({s['name']})" 
                        for s in st.session_state.data.get('subdirections', [])
                        if s['name'] == student['name']):
                    payments.append(p)

        if payments:
            df_pay = pd.DataFrame(payments)
            df_pay['date'] = pd.to_datetime(df_pay['date'])
            st.dataframe(df_pay[['date', 'amount', 'direction', 'type', 'notes']], 
                    hide_index=True, 
                    use_container_width=True)
        else:
            st.info("Нет оплат.")

        st.subheader("📅 Посещения")
        attendances = []
        direction_map = {
            f"{s['parent']} ({s['name']})": s['parent'] 
            for s in st.session_state.data.get('subdirections', [])
        }

        for day, lessons in st.session_state.data.get("attendance", {}).items():
            for lesson_id, students_data in lessons.items():
                if student_id in students_data:
                    status = students_data[student_id]
                    lesson = next(
                        (l for l in st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', []) + st.session_state.data.get('archived_schedule', [])
                        if l['id'] == lesson_id),
                        None
                    )
                    
                    if lesson:
                        direction_name = lesson['direction']
                        direction_to_show = direction_map.get(direction_name, direction_name)
                        lesson_type = "Разовое" if 'date' in lesson else "Регулярное"
                        
                        attendances.append({
                            "Дата": day,
                            "Направление": direction_to_show,
                            "Фактическое направление": direction_name,
                            "Преподаватель": lesson['teacher'],
                            "Тип": lesson_type,
                            "Был": status.get('present', False),
                            "Оплачено": status.get('paid', False),
                            "Примечание": status.get('note', '')
                        })

        if attendances:
            df_att = pd.DataFrame(attendances).sort_values("Дата", ascending=False)
            df_att['Удалить'] = False
            
            st.dataframe(
                df_att.drop(columns=['Удалить', 'Фактическое направление']),
                use_container_width=True,
                column_config={
                    "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                    "Был": st.column_config.CheckboxColumn("Посещение"),
                    "Оплачено": st.column_config.CheckboxColumn("Оплата")
                },
                hide_index=True
            )
            
            with st.expander("✏️ Редактировать посещения", expanded=False):
                edited_att = st.data_editor(
                    df_att,
                    use_container_width=True,
                    column_config={
                        "Удалить": st.column_config.CheckboxColumn("Удалить?", default=False),
                        "Дата": st.column_config.DateColumn(format="DD.MM.YYYY", disabled=True),
                        "Направление": st.column_config.TextColumn(disabled=True),
                        "Тип": st.column_config.TextColumn(disabled=True),
                        "Был": st.column_config.CheckboxColumn("Посещение"),
                        "Оплачено": st.column_config.CheckboxColumn("Оплата"),
                    },
                    hide_index=True,
                    key=f"att_editor_{student_id}"
                )
                
                if st.button("💾 Сохранить изменения", key=f"save_att_{student_id}"):
                    # --- НОВЫЙ БЛОК: ОБНОВЛЕНИЕ ДАННЫХ ---
                    for _, row in edited_att.iterrows():
                        if not row['Удалить']:
                            date_key = row['Дата'].strftime("%Y-%m-%d") if hasattr(row['Дата'], 'strftime') else row['Дата']
                            direction = row['Фактическое направление']
                            
                            # Находим и обновляем запись о посещении
                            if date_key in st.session_state.data['attendance']:
                                for lesson_id, students in st.session_state.data['attendance'][date_key].items():
                                    if student_id in students:
                                        lesson = next((l for l in st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', []) + st.session_state.data.get('archived_schedule', []) if l['id'] == lesson_id), None)
                                        if lesson and lesson['direction'] == direction:
                                            st.session_state.data['attendance'][date_key][lesson_id][student_id]['present'] = bool(row['Был'])
                                            st.session_state.data['attendance'][date_key][lesson_id][student_id]['paid'] = bool(row['Оплачено'])
                                            st.session_state.data['attendance'][date_key][lesson_id][student_id]['note'] = str(row['Примечание'])
                    # --- КОНЕЦ НОВОГО БЛОКА ---

                    # Удаляем отмеченные посещения
                    to_delete = edited_att[edited_att['Удалить']]
                    for _, row in to_delete.iterrows():
                        date_key = row['Дата'].strftime("%Y-%m-%d") if hasattr(row['Дата'], 'strftime') else row['Дата']
                        direction = row['Фактическое направление']
                        
                        if date_key in st.session_state.data['attendance']:
                            for lesson_id in list(st.session_state.data['attendance'][date_key].keys()):
                                if student_id in st.session_state.data['attendance'][date_key][lesson_id]:
                                    lesson = next(
                                        (l for l in st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', []) + st.session_state.data.get('archived_schedule', [])
                                        if l['id'] == lesson_id and l['direction'] == direction
                                        ), None)
                                    
                                    if lesson:
                                        del st.session_state.data['attendance'][date_key][lesson_id][student_id]
                                        if not st.session_state.data['attendance'][date_key][lesson_id]:
                                            del st.session_state.data['attendance'][date_key][lesson_id]
                                        if not st.session_state.data['attendance'][date_key]:
                                            del st.session_state.data['attendance'][date_key]
                    
                    save_data(st.session_state.data)
                    log_action(st.session_state.username, "Edit Attendance", f"Updated attendance for {student['name']}")
                    st.success("Изменения сохранены!")
                    st.rerun()
            
            with st.expander("🔍 Детализация по поднаправлениям"):
                st.dataframe(
                    df_att,
                    use_container_width=True,
                    column_config={
                        "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                        "Направление": st.column_config.TextColumn("Группировка"),
                        "Фактическое направление": st.column_config.TextColumn("Конкретное занятие"),
                        "Был": st.column_config.TextColumn("Посещение"),
                        "Оплачено": st.column_config.TextColumn("Оплата")
                    }
                )
        else:
            st.info("Нет посещений.")


def show_teacher_card(teacher_id):
    teacher = get_teacher_by_id(teacher_id)
    if not teacher:
        st.warning("Преподаватель не найден.")
        return

    # Функция для перезагрузки компонента
    def rerun():
        st.session_state[f"rerun_{teacher_id}"] = not st.session_state.get(f"rerun_{teacher_id}", False)
    
    # Ключ для хранения состояния
    state_key = f"teacher_{teacher_id}_state"
    
    # Инициализация состояния
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "edited": False,
            "deleted_directions": [],
            "added_directions": []
        }

    # Текущие направления с учетом изменений
    current_directions = [
        d for d in teacher.get("directions", []) 
        if d not in st.session_state[state_key]["deleted_directions"]
    ] + st.session_state[state_key]["added_directions"]

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
        st.subheader("🎯 Управление направлениями")
        
        # Отображаем текущие направления с кнопками удаления
        if current_directions:
            st.write("Текущие направления:")
            cols = st.columns(4)
            for i, direction in enumerate(current_directions):
                with cols[i % 4]:
                    if st.button(f"❌ {direction}", key=f"remove_{teacher_id}_{direction}_{i}"):
                        if direction in st.session_state[state_key]["added_directions"]:
                            st.session_state[state_key]["added_directions"].remove(direction)
                        else:
                            st.session_state[state_key]["deleted_directions"].append(direction)
                        st.session_state[state_key]["edited"] = True
                        st.rerun()
        
        # Получаем ВСЕ доступные направления (основные + поднаправления)
        all_available_directions = []
        all_available_directions.extend([d['name'] for d in st.session_state.data['directions']])
        all_available_directions.extend([
            f"{s['parent']} ({s['name']})" 
            for s in st.session_state.data.get('subdirections', [])
        ])
        
        # Доступные для добавления направления (которых еще нет у преподавателя)
        available_directions = sorted(list(set(all_available_directions) - set(current_directions)))
        
        # Форма добавления существующего направления
        with st.form(key=f"add_direction_form_{teacher_id}", clear_on_submit=True):
            if available_directions:
                selected_direction = st.selectbox(
                    "Выберите направление для добавления:",
                    available_directions,
                    key=f"select_dir_{teacher_id}"
                )
                
                # ДОБАВЛЕНА КНОПКА SUBMIT
                submitted = st.form_submit_button("➕ Добавить выбранное направление")
                if submitted and selected_direction:
                    st.session_state[state_key]["added_directions"].append(selected_direction)
                    st.session_state[state_key]["edited"] = True
                    st.rerun()
            else:
                st.info("Все доступные направления уже добавлены")
        
        # --- ТАБЛИЦА ЗАМЕН И ОТРАБОТОК ---
        st.subheader("🔄 Замены и Отработки")
        
        # 1. Замены (где этот учитель заменял кого-то)
        substitutions = []
        # Собираем данные для таблицы
        exceptions = st.session_state.data.get('schedule_exceptions', {})
        for date_str, lessons in exceptions.items():
            for l_id, exc in lessons.items():
                if exc.get('type') == 'substitution' and exc.get('teacher_id') == teacher_id:
                    # Находим детали урока
                    lesson_info = next((l for l in st.session_state.data['schedule'] + st.session_state.data.get('archived_schedule', []) if l['id'] == l_id), None)
                    direction = lesson_info['direction'] if lesson_info else "Неизвестно"
                    time_slot = f"{lesson_info['start_time']}-{lesson_info['end_time']}" if lesson_info else ""
                    
                    substitutions.append({
                        "id": l_id, # ID урока для идентификации
                        "date_key": date_str, # Ключ даты для удаления
                        "Дата": date_str,
                        "Тип": "Замена",
                        "Детали": f"Заменил(а) {exc.get('orig_teacher_name')} ({direction}, {time_slot})",
                        "Сумма": "Расчет в ЗП"
                    })
        
        # 2. Отработки (разовые занятия, проведенные этим учителем)
        single_lessons = st.session_state.data.get('single_lessons', [])
        for i, sl in enumerate(single_lessons):
            if sl.get('teacher_id') == teacher_id or sl.get('teacher') == teacher['name']:
                student_name = next((s['name'] for s in st.session_state.data['students'] if s['id'] == sl['student_id']), "Неизвестный")
                
                # Сумма: либо сохраненная cost (при переносе), либо из тарифа направления
                lesson_cost = sl.get('cost', "По тарифу")
                
                # Проверяем посещение
                is_present = False
                att_record = st.session_state.data.get('attendance', {}).get(sl['date'], {}).get(sl['id'], {}).get(sl['student_id'], {})
                if att_record.get('present'):
                    is_present = True

                substitutions.append({
                    "id": sl['id'],
                    "date_key": "single", # Маркер что это разовое
                    "Дата": sl['date'],
                    "Тип": "Отработка" if sl.get('type') == 'makeup' else "Разовое",
                    "Ученик": student_name,
                    "Детали": f"Направление: {sl['direction']}",
                    "Сумма": lesson_cost,
                    "Посещение": is_present
                })
        
        if substitutions:
            df_subs = pd.DataFrame(substitutions)
            df_subs['Удалить'] = False
            
            edited_subs = st.data_editor(
                df_subs,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": None, "date_key": None, # Скрываем служебные поля
                    "Удалить": st.column_config.CheckboxColumn("Удалить?"),
                    "Посещение": st.column_config.CheckboxColumn("Был?", disabled=True)
                }
            )
            
            if st.button("🗑️ Удалить выбранные записи", key=f"del_subs_{teacher_id}"):
                to_delete = edited_subs[edited_subs['Удалить']]
                for _, row in to_delete.iterrows():
                    if row['date_key'] == 'single':
                        # Удаляем из single_lessons
                        st.session_state.data['single_lessons'] = [
                            sl for sl in st.session_state.data['single_lessons'] if sl['id'] != row['id']
                        ]
                    else:
                        # Удаляем из schedule_exceptions
                        if row['date_key'] in st.session_state.data['schedule_exceptions']:
                            if row['id'] in st.session_state.data['schedule_exceptions'][row['date_key']]:
                                del st.session_state.data['schedule_exceptions'][row['date_key']][row['id']]
                
                save_data(st.session_state.data)
                st.success("Записи удалены")
                st.rerun()
        else:
            st.info("Нет записей о заменах или отработках.")

        # Кнопка сохранения изменений
        if st.session_state[state_key]["edited"]:
            if st.button("💾 Сохранить изменения", key=f"save_{teacher_id}"):
                # Применяем изменения
                teacher["directions"] = [
                    d for d in teacher.get("directions", []) 
                    if d not in st.session_state[state_key]["deleted_directions"]
                ] + st.session_state[state_key]["added_directions"]
                
                # Обновляем данные
                for i, t in enumerate(st.session_state.data['teachers']):
                    if t['id'] == teacher_id:
                        st.session_state.data['teachers'][i] = teacher
                        break
                
                save_data(st.session_state.data)
                log_action(st.session_state.username, "Edit Teacher", f"Updated directions for {teacher['name']}")
                
                # Сбрасываем состояние
                st.session_state[state_key] = {
                    "edited": False,
                    "deleted_directions": [],
                    "added_directions": []
                }
                
                st.success("Изменения сохранены!")
                time.sleep(1)
                st.rerun()

        # Статистика и посещения
        direction_map = {
            f"{s['parent']} ({s['name']})": s['parent'] 
            for s in st.session_state.data.get('subdirections', [])
        }

        all_directions_stats = set()
        for dir_name in teacher.get('directions', []):
            if dir_name in direction_map:
                all_directions_stats.add(direction_map[dir_name])
            else:
                all_directions_stats.add(dir_name)

        for direction_name in sorted(all_directions_stats):
            st.markdown(f"### 📘 {direction_name}")
            
            lessons = []
            all_schedule_source = st.session_state.data['schedule'] + st.session_state.data.get('archived_schedule', [])
            lessons.extend([l for l in all_schedule_source
                          if l['direction'] == direction_name 
                          and l['teacher'] == teacher['name']])
            
            subdirections = [k for k, v in direction_map.items() if v == direction_name]
            for subdir in subdirections:
                lessons.extend([l for l in all_schedule_source
                              if l['direction'] == subdir
                              and l['teacher'] == teacher['name']])
            
            single_lessons = [
                l for l in st.session_state.data.get('single_lessons', [])
                if l['teacher'] == teacher['name'] and l['direction'] == direction_name
            ]
            
            if not lessons and not single_lessons:
                st.info("Нет занятий по этому направлению.")
                continue

            students_in_dir = []
            students_in_dir.extend([s for s in st.session_state.data['students'] 
                                 if direction_name in s.get('directions', [])])
            
            for subdir in subdirections:
                students_in_dir.extend([s for s in st.session_state.data['students'] 
                                      if subdir in s.get('directions', [])])
            
            for lesson in single_lessons:
                student = next((s for s in st.session_state.data['students'] 
                             if s['id'] == lesson['student_id']), None)
                if student and student not in students_in_dir:
                    students_in_dir.append(student)

            if not students_in_dir:
                st.info("Нет учеников на этом направлении.")
                continue

            attendance_data = []
            attendance = st.session_state.data.get("attendance", {})

            for student in students_in_dir:
                for lesson in lessons:
                    lesson_id = lesson.get('id')
                    for date_str, day_lessons in attendance.items():
                        if lesson_id in day_lessons and student['id'] in day_lessons[lesson_id]:
                            record = day_lessons[lesson_id][student['id']]
                            
                            paid_status = record.get('paid', False)
                            if not paid_status:
                                for payment in st.session_state.data['payments']:
                                    if payment['student_id'] == student['id']:
                                        payment_dir = payment['direction']
                                        if (payment_dir == direction_name or 
                                            payment_dir in subdirections):
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
                                "Присутствовал": "Да" if record.get('present') else "Нет",
                                "Оплачено": "Да" if paid_status else "Нет",
                                "Примечание": record.get('note', ''),
                                "Тип": "Поднаправление" if lesson['direction'] in subdirections else "Основное"
                            })

            for lesson in single_lessons:
                date_str = lesson['date']
                lesson_id = lesson['id']
                student_id = lesson['student_id']
                student = next((s for s in students_in_dir if s['id'] == student_id), None)
                
                if student:
                    record = attendance.get(date_str, {}).get(lesson_id, {}).get(student_id, {})
                    
                    paid_status = record.get('paid', False)
                    if not paid_status:
                        for payment in st.session_state.data['payments']:
                            if (payment['student_id'] == student_id and 
                                payment['direction'] == direction_name and
                                payment['date'] == date_str):
                                paid_status = True
                                break
                    
                    attendance_data.append({
                        "Ученик": student['name'],
                        "Дата": date_str,
                        "Занятие": f"{lesson['start_time']}-{lesson['end_time']}",
                        "Присутствовал": "Да" if record.get('present') else "Нет",
                        "Оплачено": "Да" if paid_status else "Нет",
                        "Примечание": record.get('note', '') or lesson.get('notes', ''),
                        "Тип": "Разовое занятие"
                    })

            if attendance_data:
                df = pd.DataFrame(attendance_data)
                df['Дата'] = pd.to_datetime(df['Дата'])
                df = df.sort_values('Дата', ascending=False)
                
                st.dataframe(
                    df.drop(columns=['Тип']),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                        "Присутствовал": st.column_config.TextColumn(),
                        "Оплачено": st.column_config.TextColumn()
                    }
                )
                
                with st.expander("🔍 Детализация по типам занятий"):
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                            "Тип": st.column_config.TextColumn("Тип занятия")
                        }
                    )
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Экспорт в CSV",
                    data=csv,
                    file_name=f"attendance_{teacher['name']}_{direction_name}.csv",
                    mime="text/csv",
                    key=f"export_csv_{teacher_id}_{direction_name}"
                )
            else:
                st.info("Нет данных о посещениях.")

def show_students_page():
    st.header("👦👧 Ученики и оплаты")

    # 1. Проверка режима редактирования карточки (Твоя логика)
    if st.session_state.get('edit_student_id'):
        if st.button("🔙 Вернуться к списку"):
            st.session_state.edit_student_id = None
            st.rerun()
        show_student_card(st.session_state.edit_student_id)
        return

    # 2. Подготовка данных
    students = st.session_state.data.get('students', [])
    parents = st.session_state.data.get('parents', [])
    directions = st.session_state.data.get('directions', [])

    # Гарантируем наличие ID для всех учеников
    for s in students:
        if 'id' not in s:
            s['id'] = str(uuid.uuid4())

    view_mode = st.radio("Режим отображения", ["📋 Таблица", "🧾 Карточки"], horizontal=True)

    # 3. Форма добавления нового ученика (Твой полный блок)
    with st.expander("➕ Добавить нового ученика"):
        with st.form("new_student_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ФИО*")
                dob = st.date_input("Дата рождения*", 
                                   value=date.today(),
                                   min_value=date(2000, 1, 1),
                                   max_value=date.today())
                gender = st.selectbox("Пол", ["Мальчик", "Девочка"])
                notes = st.text_area("Заметки")
            with col2:
                parent_map = {p['id']: f"{p['name']} ({p.get('phone', '-')})" for p in parents}
                parent_id = st.selectbox("Родитель", [None] + list(parent_map.keys()),
                                         format_func=lambda x: parent_map.get(x, "Новый родитель") if x else "Новый родитель")
                new_parent_name = st.text_input("Имя нового родителя")
                new_parent_phone = st.text_input("Телефон нового родителя")
                
                dir_options = [d['name'] for d in directions]
                subdir_options = [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]
                selected_dirs = st.multiselect("Направления", dir_options + subdir_options)

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
                    log_action(st.session_state.username, "Add Student", f"Added {name}")
                    st.success(f"Ученик {name} добавлен.")
                    st.rerun()
                else:
                    st.error("Введите ФИО.")

    # 4. Режим ТАБЛИЦЫ (Синхронизированный и полностью редактируемый)
    if view_mode == "📋 Таблица":
        if students:
            # Создаем карту родителей
            parent_info_map = {p['id']: {'name': p['name'], 'phone': p.get('phone', '')} for p in parents}
            
            display_data = []
            for s in students:
                p_id = s.get('parent_id')
                # Исправляем формат даты для таблицы
                raw_dob = s.get('dob')
                try:
                    clean_dob = datetime.strptime(raw_dob, '%Y-%m-%d').date() if isinstance(raw_dob, str) else raw_dob
                except:
                    clean_dob = None

                display_data.append({
                    "id": s['id'],
                    "parent_id": p_id,
                    "ФИО Ученика": str(s.get('name', '')),
                    "Дата рождения": clean_dob,
                    "Пол": s.get('gender', 'Мальчик'),
                    "ФИО Родителя": str(parent_info_map.get(p_id, {}).get('name', '—')),
                    "📞 Телефон(ы)": str(parent_info_map.get(p_id, {}).get('phone', '')),
                    "Направления": ", ".join(s.get('directions', [])) if isinstance(s.get('directions'), list) else str(s.get('directions', '')),
                    "Заметки": str(s.get('notes', '')),
                    "🗑️": False
                })

            df = pd.DataFrame(display_data)

            # Редактор таблицы: ФИО родителя теперь просто текст (TextColumn)
            edited_df = st.data_editor(
                df,
                column_config={
                    "id": None, 
                    "parent_id": None,
                    "ФИО Ученика": st.column_config.TextColumn("ФИО Ученика", width="medium"),
                    "Дата рождения": st.column_config.DateColumn("Дата рождения"),
                    "Пол": st.column_config.SelectboxColumn("Пол", options=["Мальчик", "Девочка"]),
                    "ФИО Родителя": st.column_config.TextColumn("ФИО Родителя", width="medium"), # РЕДАКТИРУЕМ КУРСОРOM
                    "📞 Телефон(ы)": st.column_config.TextColumn("📞 Телефон(ы)", width="medium"), # РЕДАКТИРУЕМ КУРСОРOM
                    "Направления": st.column_config.TextColumn("Направления (через запятую)"),
                    "Заметки": st.column_config.TextColumn("Заметки"),
                    "🗑️": st.column_config.CheckboxColumn("Удалить")
                },
                hide_index=True,
                use_container_width=True,
                key="students_table_final_v5"
            )

            if st.button("💾 Сохранить всё", type="primary"):
                # А) Удаление
                to_delete_ids = edited_df[edited_df['🗑️'] == True]['id'].tolist()
                if to_delete_ids:
                    st.session_state.data['students'] = [s for s in students if s['id'] not in to_delete_ids]
                    # Чистим связанные платежи и посещения
                    st.session_state.data['payments'] = [p for p in st.session_state.data.get('payments', []) if p['student_id'] not in to_delete_ids]
                    for d_key in st.session_state.data.get('attendance', {}):
                        for l_id in st.session_state.data['attendance'][d_key]:
                            for sid in to_delete_ids:
                                st.session_state.data['attendance'][d_key][l_id].pop(sid, None)
                    log_action(st.session_state.username, "Delete Students", f"Deleted {len(to_delete_ids)} students")

                # Б) Синхронизация правок
                current_students = st.session_state.data['students']
                current_parents = st.session_state.data['parents']
                
                for _, row in edited_df.iterrows():
                    if row['id'] in to_delete_ids: continue
                    
                    # Обновляем данные ученика
                    for s in current_students:
                        if s['id'] == row['id']:
                            s['name'] = row['ФИО Ученика']
                            s['dob'] = str(row['Дата рождения']) if row['Дата рождения'] else None
                            s['gender'] = row['Пол']
                            s['notes'] = str(row['Заметки']) if pd.notna(row['Заметки']) else ''
                            
                            # Превращаем строку направлений обратно в список
                            dirs_raw = row['Направления']
                            if pd.notna(dirs_raw):
                                s['directions'] = [d.strip() for d in str(dirs_raw).split(',') if d.strip()]
                    
                    # Обновляем данные родителя (связанного с этим учеником по ID)
                    pid = row['parent_id']
                    if pid:
                        for p in current_parents:
                            if p['id'] == pid:
                                p['name'] = row['ФИО Родителя'] # Прямая правка имени
                                p['phone'] = row['📞 Телефон(ы)'] # Прямая правка телефона

                save_data(st.session_state.data)
                st.success("Данные учеников и родителей обновлены!")
                st.rerun()
        else:
            st.info("Нет учеников.")

    # 5. Режим КАРТОЧЕК (Твоя логика с прогресс-барами)
    else:
        for student in students:
            with st.container(border=True):
                st.markdown(f"#### {student['name']}")
                st.caption(f"Возраст: {calculate_age(student.get('dob'))} | Пол: {student.get('gender')}")

                # Визуализация прогресса по направлениям
                for direction in student.get('directions', []):
                    lessons_this_month = get_month_lessons(direction, date.today().year, date.today().month)
                    total_lessons = len(lessons_this_month)
                    attended = 0
                    
                    for l_date in lessons_this_month:
                        d_str = l_date.strftime("%Y-%m-%d")
                        if d_str in st.session_state.data.get('attendance', {}):
                            for l_id, students_in_l in st.session_state.data['attendance'][d_str].items():
                                if student['id'] in students_in_l:
                                    all_lessons_source = st.session_state.data['schedule'] + st.session_state.data.get('single_lessons', [])
                                    lesson_info = next((l for l in all_lessons_source if l['id'] == l_id), None)
                                    if lesson_info and lesson_info.get('direction') == direction:
                                        if students_in_l[student['id']].get('present'):
                                            attended += 1
                    
                    col_vis, col_info = st.columns([3, 1])
                    with col_vis:
                        progress = attended / total_lessons if total_lessons > 0 else 0
                        st.progress(min(progress, 1.0))
                    with col_info:
                        st.caption(f"{direction}: {attended}/{total_lessons}")
                
                if st.button("Открыть карточку", key=f"open_card_{student['id']}"):
                    st.session_state.edit_student_id = student['id']
                    st.rerun()

    # 💳 Оплаты
    st.subheader("💳 Добавить оплату")
    if students:
        student_map = {s['id']: s['name'] for s in students}
        selected_id = st.selectbox("Ученик", list(student_map.keys()), format_func=lambda x: student_map[x])
        with st.form("add_payment_form"):
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Сумма (₽)", min_value=0.0)
                p_date = st.date_input("Дата", value=date.today(), min_value=date(2008, 1, 1))
            with col2:
                dir_options = [d['name'] for d in directions]
                subdir_options = [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]
                direction = st.selectbox("Направление", dir_options + subdir_options)
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
                log_action(st.session_state.username, "Add Payment", f"Added {amount} for {student_map[selected_id]}")
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
                    log_action(st.session_state.username, "Add Teacher", f"Added {name}")
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
            log_action(st.session_state.username, "Edit Teachers", "Updated teachers table")
            st.success("Изменения сохранены!")
            st.rerun()
        # Создаем DataFrame с колонкой для удаления
        df = pd.DataFrame(teachers)
        df['Удалить'] = False  # Добавляем колонку с чекбоксами
        
        # Отображаем редактор таблицы
        edited_df = st.data_editor(
            df[['id', 'name', 'phone', 'email', 'directions', 'notes', 'Удалить']],
            hide_index=True,
            use_container_width=True,
            disabled=['id'],
            column_config={
                "directions": st.column_config.ListColumn("Направления"),
                "Удалить": st.column_config.CheckboxColumn("Удалить?")
            }
        )
        
        # Кнопка для удаления отмеченных строк
        if st.button("🗑️ Удалить выбранных преподавателей"):
            # Получаем ID преподавателей для удаления
            to_delete = edited_df[edited_df['Удалить']]['id'].tolist()
            
            if to_delete:
                # Удаляем из основного списка
                st.session_state.data['teachers'] = [
                    t for t in teachers if t['id'] not in to_delete
                ]
                
                # Удаляем из расписания
                st.session_state.data['schedule'] = [
                    lesson for lesson in st.session_state.data['schedule'] 
                    if lesson['teacher'] not in [t['name'] for t in teachers if t['id'] in to_delete]
                ]
                
                save_data(st.session_state.data)
                log_action(st.session_state.username, "Delete Teachers", f"Deleted {len(to_delete)} teachers")
                st.success(f"Удалено {len(to_delete)} преподавателей!")
                st.rerun()
            else:
                st.warning("Не выбрано ни одного преподавателя для удаления")
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
    if st.session_state.role in ['admin', 'teacher', 'reception']:
        with st.expander("➕ Добавить занятие в расписание", expanded=False):
            with st.form("new_schedule_form"):
                col1, col2 = st.columns(2)
                with col1:
                    direction_options = [d['name'] for d in directions]
                    subdirection_options = [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]
                    direction_name = st.selectbox("Направление*", direction_options + subdirection_options)
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
                    # Предполагаем наличие функции log_action, если ее нет - закомментируйте строку ниже
                    if 'log_action' in globals():
                        log_action(st.session_state.username, "Add Schedule", f"Added {direction_name} on {day_of_week}")
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

    # Получаем все занятия на выбранную дату
    regular_lessons = [s for s in schedule if s['day'] == russian_day]
    single_lessons = [
        {
            'id': l['id'],
            'direction': l['direction'],
            'teacher': l['teacher'],
            'start_time': l['start_time'],
            'end_time': l['end_time'],
            'day': russian_day,
            'type': l.get('type', 'single'),
            'student_id': l['student_id']
        }
        for l in st.session_state.data.get('single_lessons', [])
        if l['date'] == selected_date.strftime("%Y-%m-%d")
    ]

    # Сортировка занятий с защитой от ошибок формата
    all_lessons = sorted(
        regular_lessons + single_lessons,
        key=lambda x: safe_time_parse(x.get('start_time', '00:00')))

    if all_lessons:
        for lesson in all_lessons:
            l_type = lesson.get('type', 'regular')
            lesson_type_str = ""
            if l_type == 'single':
                lesson_type_str = "(Разовое)"
            elif l_type == 'makeup':
                lesson_type_str = "(Отработка)"
            
            # Проверка замен
            date_key = selected_date.strftime("%Y-%m-%d")
            exceptions = st.session_state.data.get('schedule_exceptions', {}).get(date_key, {})
            display_teacher = lesson['teacher']
            sub_info = ""
            if lesson['id'] in exceptions:
                exc = exceptions[lesson['id']]
                if exc['type'] == 'substitution':
                    # Предполагаем наличие get_teacher_by_id
                    sub_teacher = get_teacher_by_id(exc['teacher_id'])
                    if sub_teacher:
                        display_teacher = sub_teacher['name']
                        sub_info = f" 🔄 (Замена: {lesson['teacher']} ➝ {display_teacher})"
            
            with st.expander(f"{lesson['direction']} {lesson_type_str} ({lesson['start_time']}-{lesson['end_time']}, {display_teacher}){sub_info}", expanded=False):
                lesson_key = lesson['id']
                att_key = f"att_{lesson_key}_{date_key}"

                # Инициализация состояния
                if att_key not in st.session_state:
                    st.session_state[att_key] = {
                        'data': [],
                        'saved': False
                    }

                # Найдём учеников
                if lesson.get('type') in ['single', 'makeup']:
                    # Для разовых занятий - только один ученик
                    student = next((s for s in students if s['id'] == lesson.get('student_id')), None)
                    if student:
                        students_in_dir = [student]
                        # Добавляем направление ученику, если его нет (ТОЛЬКО ЕСЛИ НЕ ОТРАБОТКА)
                        if lesson.get('type') != 'makeup' and lesson['direction'] not in student.get('directions', []):
                            student['directions'].append(lesson['direction'])
                            save_data(st.session_state.data)
                    else:
                        students_in_dir = []
                else:
                    # Для регулярных - все ученики направления
                    students_in_dir = [s for s in students if lesson['direction'] in s.get('directions', [])]
                
                if not students_in_dir:
                    st.info("Нет учеников на этом занятии.")
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

                if st.button("💾 Сохранить посещения", key=f"save_{att_key}"):
                    # Проверка на рассинхронизацию
                    if len(edited_df) != len(students_in_dir):
                        st.warning("Список учеников изменился. Пожалуйста, обновите страницу.")
                        del st.session_state[att_key]
                        st.rerun()

                    for idx, s in enumerate(students_in_dir):
                        s_id = s['id']
                        new_status = {
                            'present': bool(edited_df.iloc[idx]['Присутствовал']),
                            'paid': bool(edited_df.iloc[idx]['Оплачено']),
                            'note': str(edited_df.iloc[idx]['Примечание'])
                        }
                        
                        # Проверяем текущий статус оплаты
                        current_paid_status = attendance[date_key][lesson_key][s_id].get('paid', False)
                        
                        # Если галочка оплаты была изменена с False на True
                        if new_status['paid'] and not current_paid_status:
                            payment_exists = any(
                                p['student_id'] == s_id and 
                                p['direction'] == lesson['direction'] and
                                p['date'] == date_key
                                for p in st.session_state.data['payments']
                            )
                            
                            if not payment_exists:
                                # Для разовых занятий берем стоимость из направления
                                if lesson.get('type') == 'single':
                                    direction = next(
                                        (d for d in st.session_state.data['directions'] 
                                        if d['name'] == lesson['direction']), None)
                                    cost = direction.get('trial_cost', 0) if direction else 0
                                    
                                    new_payment = {
                                        'id': str(uuid.uuid4()),
                                        'student_id': s_id,
                                        'date': date_key,
                                        'amount': cost,
                                        'direction': lesson['direction'],
                                        'type': 'Разовое',
                                        'notes': "Автоматически создано при отметке посещения"
                                    }
                                    st.session_state.data['payments'].append(new_payment)
                                    st.success(f"Добавлена оплата за разовое занятие: {cost} ₽")
                        
                        attendance[date_key][lesson_key][s_id] = new_status
                    
                    save_data(st.session_state.data)
                    if 'log_action' in globals():
                        log_action(st.session_state.username, "Mark Attendance", f"Updated attendance for {date_key}")
                    st.success("Посещения сохранены!")
                    time.sleep(0.3)
                    st.rerun()
    else:
        st.info(f"На {russian_day} занятий нет.")

    # === Общее расписание (ИСПРАВЛЕННАЯ СЕКЦИЯ) ===
    st.subheader("📋 Общее расписание")
    if schedule:
        df = pd.DataFrame(schedule)
        
        # 1. Безопасное приведение времени для отображения и редактирования
        df['start_time_str'] = pd.to_datetime(df['start_time'], format='mixed', errors='coerce').dt.strftime("%H:%M").fillna("00:00")
        df['end_time_str'] = pd.to_datetime(df['end_time'], format='mixed', errors='coerce').dt.strftime("%H:%M").fillna("00:00")

        # 2. Фильтры
        col1, col2, col3 = st.columns(3)
        with col1:
            day_filter = st.multiselect("День недели", sorted(df['day'].unique()))
        with col2:
            teacher_filter = st.multiselect("Преподаватель", sorted(df['teacher'].unique()))
        with col3:
            # Улучшенный фильтр направлений с учетом поднаправлений
            subdir_to_main = {
                subdir: main 
                for main, subdir in [
                    (s['parent'], f"{s['parent']} ({s['name']})") 
                    for s in st.session_state.data.get('subdirections', [])
                ]
            }
            
            all_directions = set(df['direction'])
            main_directions = set()
            for direction in all_directions:
                if direction in subdir_to_main:
                    main_directions.add(subdir_to_main[direction])
                else:
                    main_directions.add(direction)
            
            selected_main_dirs = st.multiselect(
                "Направление", 
                sorted(main_directions),
                format_func=lambda x: f"{x} (все поднаправления)" if any(
                    d in subdir_to_main and subdir_to_main[d] == x 
                    for d in all_directions
                ) else x
            )

        # 3. Применяем фильтры
        df_filtered = df.copy()
        if day_filter:
            df_filtered = df_filtered[df_filtered['day'].isin(day_filter)]
        if teacher_filter:
            df_filtered = df_filtered[df_filtered['teacher'].isin(teacher_filter)]
        if selected_main_dirs:
            selected_dirs = []
            for main_dir in selected_main_dirs:
                selected_dirs.append(main_dir)
                selected_dirs.extend([
                    subdir for subdir in subdir_to_main 
                    if subdir_to_main[subdir] == main_dir and subdir in all_directions
                ])
            df_filtered = df_filtered[df_filtered['direction'].isin(selected_dirs)]

        # 4. Подготовка DataFrame для редактора (ВАЖНО: ВКЛЮЧАЕМ ID)
        # Мы берем нужные колонки + ID, чтобы точно знать, что обновлять
        df_to_edit = df_filtered[['id', 'day', 'start_time_str', 'end_time_str', 'teacher', 'direction']].copy()
        df_to_edit['Удалить'] = False
        
        # Получаем списки для выпадающих меню
        all_teachers = [t['name'] for t in teachers]
        all_directions_list = [d['name'] for d in directions] + [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]

        # 5. Отображаем таблицу
        edited_df = st.data_editor(
            df_to_edit,
            use_container_width=True,
            hide_index=True,
            key="full_schedule_editor",
            column_config={
                "id": None, # Скрываем ID от пользователя, но он доступен в коде
                "day": st.column_config.SelectboxColumn(
                    "День",
                    options=["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
                    required=True
                ),
                "start_time_str": st.column_config.TextColumn("Начало (ЧЧ:ММ)", required=True),
                "end_time_str": st.column_config.TextColumn("Конец (ЧЧ:ММ)", required=True),
                "teacher": st.column_config.SelectboxColumn(
                    "Преподаватель",
                    options=all_teachers,
                    required=True
                ),
                "direction": st.column_config.SelectboxColumn(
                    "Направление",
                    options=all_directions_list,
                    required=True
                ),
                "Удалить": st.column_config.CheckboxColumn(
                    "Удалить",
                    help="Выберите занятия для удаления",
                    default=False
                )
            }
        )

        # 6. Кнопка для сохранения изменений (Умное обновление по ID)
        col_save, col_del, col_export = st.columns([1, 1, 1])

        with col_save:
            if st.button("💾 Сохранить изменения"):
                changes_count = 0
                rows_to_delete_ids = []

                # Проходим по отредактированной таблице
                for index, row in edited_df.iterrows():
                    lesson_id = row['id']
                    
                    if row['Удалить']:
                        rows_to_delete_ids.append(lesson_id)
                        continue

                    # Ищем оригинальное занятие в общем списке по ID
                    original_lesson = next((item for item in schedule if item["id"] == lesson_id), None)
                    
                    if original_lesson:
                        # Проверяем, были ли изменения
                        has_changed = False
                        if original_lesson['day'] != row['day']:
                            original_lesson['day'] = row['day']
                            has_changed = True
                        if original_lesson['teacher'] != row['teacher']:
                            original_lesson['teacher'] = row['teacher']
                            has_changed = True
                        if original_lesson['direction'] != row['direction']:
                            original_lesson['direction'] = row['direction']
                            has_changed = True
                        # Обновляем время из строковых колонок
                        if original_lesson.get('start_time') != row['start_time_str']:
                            original_lesson['start_time'] = row['start_time_str']
                            has_changed = True
                        if original_lesson.get('end_time') != row['end_time_str']:
                            original_lesson['end_time'] = row['end_time_str']
                            has_changed = True
                        
                        if has_changed:
                            changes_count += 1
                
                # Обработка удалений внутри кнопки сохранения (опционально, или отдельной кнопкой)
                if rows_to_delete_ids:
                    # Архивируем вместо удаления
                    items_to_archive = [l for l in schedule if l['id'] in rows_to_delete_ids]
                    st.session_state.data.setdefault('archived_schedule', []).extend(items_to_archive)
                    
                    st.session_state.data['schedule'] = [l for l in schedule if l['id'] not in rows_to_delete_ids]
                    
                    # НЕ удаляем посещения, чтобы сохранить историю
                    st.toast(f"Архивировано {len(rows_to_delete_ids)} занятий")

                if changes_count > 0 or rows_to_delete_ids:
                    save_data(st.session_state.data)
                    if 'log_action' in globals():
                        log_action(st.session_state.username, "Edit Schedule", f"Updated {changes_count} lessons, Deleted {len(rows_to_delete_ids)}")
                    st.success("Расписание успешно обновлено!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("Изменений не обнаружено.")

        # Отдельная кнопка удаления (для ясности)
        with col_del:
            if st.button("🗑️ Удалить выбранные"):
                to_delete_ids = edited_df[edited_df['Удалить']]['id'].tolist()
                if to_delete_ids:
                    # Архивируем вместо удаления
                    items_to_archive = [l for l in schedule if l['id'] in to_delete_ids]
                    st.session_state.data.setdefault('archived_schedule', []).extend(items_to_archive)
                    
                    st.session_state.data['schedule'] = [l for l in schedule if l['id'] not in to_delete_ids]
                    
                    # НЕ удаляем посещения
                    save_data(data)
                    if 'log_action' in globals():
                        log_action(st.session_state.username, "Delete Schedule", f"Deleted {len(to_delete_ids)} lessons")
                    st.success(f"Удалено {len(to_delete_ids)} занятий!")
                    st.rerun()
                else:
                    st.warning("Не выбрано ни одного занятия")

        with col_export:
            st.download_button(
                "📥 Экспорт CSV",
                data=df_filtered.to_csv(index=False).encode('utf-8'),
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
                    log_action(st.session_state.username, "Add Material", f"Added {material_name}")
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
            log_action(st.session_state.username, "Edit Materials", "Updated materials table")
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
                    log_action(st.session_state.username, "Add Task", f"Added task: {task_title}")
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
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded directions")
                    
                    elif data_type == "Ученики":
                        required_cols = ['name', 'dob', 'gender']
                        if all(col in df.columns for col in required_cols):
                            new_students = []
                            for _, row in df.iterrows():
                                # Обработка родителя
                                parent_id = None
                                if 'parent_id' in row and pd.notna(row['parent_id']):
                                    parent_id = row['parent_id']
                                elif 'parent_name' in row and pd.notna(row['parent_name']):
                                    # Ищем существующего родителя или создаем нового
                                    parent_phone = str(row['parent_phone']) if 'parent_phone' in row else ''
                                    existing_parent = next(
                                        (p for p in st.session_state.data['parents'] 
                                        if p['name'] == row['parent_name'] and 
                                            (not parent_phone or p['phone'] == parent_phone)),
                                        None
                                    )
                                    if existing_parent:
                                        parent_id = existing_parent['id']
                                    else:
                                        new_parent = {
                                            'id': str(uuid.uuid4()),
                                            'name': row['parent_name'],
                                            'phone': parent_phone,
                                            'children_ids': []
                                        }
                                        st.session_state.data['parents'].append(new_parent)
                                        parent_id = new_parent['id']
                                
                                # Обработка направлений
                                directions = []
                                if 'directions' in row and pd.notna(row['directions']):
                                    directions = [d.strip() for d in str(row['directions']).split(',')]
                                
                                new_student = {
                                    'id': str(uuid.uuid4()),
                                    'name': row['name'],
                                    'dob': row['dob'],
                                    'gender': row['gender'],
                                    'parent_id': parent_id,
                                    'directions': directions,
                                    'notes': row.get('notes', ''),
                                    'registration_date': row.get('registration_date', str(date.today()))
                                }
                                new_students.append(new_student)
                            
                            st.session_state.data['students'].extend(new_students)
                            save_data(st.session_state.data)
                            st.success(f"Добавлено {len(new_students)} учеников!")
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded students")
                    
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
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded parents")
                    
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
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded teachers")
                            
                    
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
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded materials")
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
                            log_action(st.session_state.username, "Bulk Upload", "Uploaded schedule")
                    # --- КОНЕЦ НОВОГО БЛОКА ---
                    
                    save_data(st.session_state.data)
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Ошибка при импорте данных: {str(e)}")
        
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {str(e)}")
def show_data_management_page():
    st.header("⚙️ Управление данными")
    
    # Информация о размере данных
    json_str = json.dumps(st.session_state.data, ensure_ascii=False, indent=4)
    data_size = len(json_str)
    st.progress(min(data_size/1000000, 1), 
               text=f"Использовано: {data_size/1024:.1f} KB / 1 MB ({(data_size/1000000)*100:.1f}%)")
    
    # --- Блок резервного копирования ---
    st.subheader("📦 Резервное копирование")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Создать точку восстановления (Архив)"):
            if archive_data():
                log_action(st.session_state.username, "Backup", "Created manual backup")
                st.success("Точка восстановления создана!")
    
    with col2:
        # Кнопка скачивания текущего JSON
        st.download_button(
            label="💾 Скачать копию файла (JSON)",
            data=json_str,
            file_name=f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json",
            mime="application/json"
        )

    st.markdown("---")

    # --- Блок оптимизации ---
    st.subheader("🧹 Оптимизация и очистка устаревших данных")
    
    with st.expander("Настройки очистки", expanded=True):
        st.warning("⚠️ Внимание! Выбранные данные будут удалены из текущей базы. Перед удалением система автоматически создаст полную резервную копию, которую можно будет восстановить.")
        
        # Выбор даты
        clean_date = st.date_input(
            "Удалить данные старше чем:", 
            value=date.today() - timedelta(days=365),
            help="Будут удалены записи до этой даты"
        )
        
        # Чекбоксы
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            clean_attendance = st.checkbox("Очистить посещения", value=True)
            clean_payments = st.checkbox("Очистить оплаты", value=True)
        with col_opt2:
            clean_archives = st.checkbox("Очистить список старых архивов", value=False, help="Удалит ссылки на старые архивы из меню, но не сами файлы на GitHub")
            clean_logs = st.checkbox("Очистить историю действий (Audit Log)", value=False)

        if st.button("🚀 Выполнить оптимизацию"):
            # 1. Создаем резервную копию ПЕРЕД удалением
            with st.spinner("Создание резервной копии..."):
                if not archive_data():
                    st.error("❌ Не удалось создать резервную копию. Оптимизация отменена для безопасности.")
                    return
            
            # 2. Выполняем очистку
            deleted_info = []
            
            # Очистка посещений
            if clean_attendance:
                original_len = sum(len(v) for v in st.session_state.data.get('attendance', {}).values())
                new_attendance = {}
                for date_str, day_data in st.session_state.data.get('attendance', {}).items():
                    try:
                        d = datetime.strptime(date_str, "%Y-%m-%d").date()
                        if d >= clean_date:
                            new_attendance[date_str] = day_data
                    except:
                        new_attendance[date_str] = day_data # Оставляем, если формат странный
                
                st.session_state.data['attendance'] = new_attendance
                deleted_info.append(f"Удалено дней посещений: {len(st.session_state.data.get('attendance', {})) - len(new_attendance)} (было записей: {original_len})")

            # Очистка оплат
            if clean_payments:
                original_len = len(st.session_state.data.get('payments', []))
                new_payments = []
                for p in st.session_state.data.get('payments', []):
                    try:
                        p_date = datetime.strptime(p['date'], "%Y-%m-%d").date()
                        if p_date >= clean_date:
                            new_payments.append(p)
                    except:
                        new_payments.append(p)
                
                st.session_state.data['payments'] = new_payments
                deleted_info.append(f"Удалено платежей: {original_len - len(new_payments)}")

            # Очистка списка архивов (ссылок)
            if clean_archives:
                # Оставляем только 5 последних
                archives = st.session_state.data.get('_archives', [])
                if len(archives) > 5:
                    st.session_state.data['_archives'] = archives[-5:]
                    deleted_info.append(f"Очищен список архивов (оставлено 5 последних)")

            # Очистка логов
            if clean_logs:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                    deleted_info.append("Файл логов удален")

            # 3. Сохраняем изменения
            if save_data(st.session_state.data):
                log_action(st.session_state.username, "Optimize Data", f"Cleaned data older than {clean_date}")
                st.success("✅ Оптимизация успешно завершена!")
                for info in deleted_info:
                    st.info(info)
                time.sleep(2)
                st.rerun()
            else:
                st.error("Ошибка при сохранении оптимизированных данных.")
    
    st.markdown("---")
    st.subheader("Экспорт данных")
    
    format_choice = st.radio("Формат экспорта", ["JSON", "CSV (только табличные данные)"])
    
    if st.button("📥 Экспортировать все данные"):
        if format_choice == "JSON":
            data_str = json.dumps(st.session_state.data, ensure_ascii=False, indent=4)
            st.download_button(
                label="Скачать JSON",
                data=data_str,
                file_name=f"center_data_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
        else:
            # Для CSV нужно преобразовать основные таблицы
            output = StringIO()
            writer = csv.writer(output)
            
            # Собираем данные из всех таблиц
            tables = {
                'students': st.session_state.data.get('students', []),
                'teachers': st.session_state.data.get('teachers', []),
                'payments': st.session_state.data.get('payments', []),
                'schedule': st.session_state.data.get('schedule', [])
            }
            
            for name, data in tables.items():
                writer.writerow([f"=== {name} ==="])
                if data:
                    writer.writerow(data[0].keys())  # заголовки
                    for row in data:
                        writer.writerow(row.values())
                writer.writerow([])
            
            st.download_button(
                label="Скачать CSV",
                data=output.getvalue(),
                file_name=f"center_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
import requests

GITHUB_API = "https://api.github.com"

def github_headers():
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json"
    }

def show_version_history_page():
    """Страница для просмотра истории изменений данных через GitHub API"""
    st.header("🕰 История версий данных")

    try:
        gist_id = st.secrets["GIST_ID"]
        commits_url = f"{GITHUB_API}/gists/{gist_id}/commits"
        commits_resp = requests.get(commits_url, headers=github_headers())
        commits_resp.raise_for_status()

        commits = commits_resp.json()
        if not commits:
            st.info("История изменений не найдена")
            return

        st.subheader(f"Последние изменения (всего {len(commits)} версий)")

        for i, commit in enumerate(commits[:10]):
            commit_id = commit["version"]
            committed_at = commit["committed_at"]

            with st.expander(f"Версия от {committed_at}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Загружаем содержимое файла этой версии
                    gist_version_url = f"{GITHUB_API}/gists/{gist_id}/{commit_id}"
                    gist_version_resp = requests.get(gist_version_url, headers=github_headers())
                    gist_version_resp.raise_for_status()
                    files = gist_version_resp.json()["files"]
                    content = files.get("center_data.json", {}).get("content", "")
                    st.code("\n".join(content.split("\n")[:10]))

                with col2:
                    if st.button("Просмотреть", key=f"view_{i}"):
                        st.session_state.viewing_version = content
                        st.session_state.page = "view_version"
                        st.rerun()

                    if st.button("Восстановить", key=f"restore_{i}"):
                        if st.session_state.role != 'admin':
                            st.warning("Только администратор может восстанавливать версии")
                        else:
                            confirm = st.checkbox(f"Подтвердите восстановление версии от {committed_at}")
                            if confirm:
                                restored_data = json.loads(content)
                                save_data(restored_data)
                                log_action(st.session_state.username, "Restore Version", f"Restored version from {committed_at}")
                                st.success("Версия восстановлена! Обновите страницу.")
                                time.sleep(2)
                                st.rerun()

        if len(commits) > 10:
            st.write(f"Показано 10 из {len(commits)} версий")

    except Exception as e:
        st.error(f"Ошибка при загрузке истории: {str(e)}")

def show_data_archives_page():
    """Страница для управления архивными копиями данных через GitHub API"""
    st.header("📦 Архивы данных")

    gist_api = "https://api.github.com/gists"

    # Инициализация списка архивов
    if "_archives" not in st.session_state.data:
        st.session_state.data["_archives"] = []
        save_data(st.session_state.data)

    # Создание нового архива
    with st.expander("➕ Создать новый архив", expanded=False):
        archive_name = st.text_input("Название архива*", placeholder="Архив на 2024-01-01")
        archive_desc = st.text_area("Описание", placeholder="Резервная копия перед обновлением системы")

        if st.button("Создать архивную копию"):
            if not archive_name:
                st.error("Пожалуйста, укажите название архива")
            else:
                try:
                    archive_data = json.dumps(st.session_state.data, indent=4, ensure_ascii=False)
                    payload = {
                        "description": f"{archive_name} | {archive_desc}",
                        "public": False,
                        "files": {
                            "archive.json": {"content": archive_data}
                        }
                    }
                    resp = requests.post(gist_api, headers=github_headers(), json=payload)
                    resp.raise_for_status()
                    gist_info = resp.json()

                    new_archive = {
                        'id': gist_info["id"],
                        'name': archive_name,
                        'description': archive_desc,
                        'url': gist_info["html_url"],
                        'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'size': len(archive_data),
                        'filename': "archive.json"
                    }

                    st.session_state.data["_archives"].append(new_archive)
                    save_data(st.session_state.data)

                    log_action(st.session_state.username, "Create Archive", f"Created archive: {archive_name}")
                    st.success(f"Архив успешно создан! [Открыть]({gist_info['html_url']})")
                    st.rerun()

                except Exception as e:
                    st.error(f"Ошибка при создании архива: {str(e)}")

    # Список архивов - исправленная версия
    st.subheader("Существующие архивы")
    if not st.session_state.data["_archives"]:
        st.info("Архивные копии не создавались")
    else:
        for archive in reversed(st.session_state.data["_archives"]):
            with st.container(border=True):
                # Безопасное получение имени архива
                archive_name = archive.get("name", f"Архив от {archive.get('created', 'неизвестная дата')}")
                archive_desc = archive.get("description", "Без описания")
                
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.subheader(archive_name)  # Используем безопасное имя
                    st.caption(archive_desc)
                    st.write(f"📅 {archive.get('created', 'нет даты')} | 📏 {archive.get('size', 0)/1024:.1f} KB")
                    if 'url' in archive:
                        st.markdown(f"[🔗 Открыть в GitHub]({archive['url']})")

                with col2:
                    if st.button("↩️ Восстановить", key=f"restore_{archive.get('id', '')}"):
                        if st.session_state.role != "admin":
                            st.warning("Только администратор может восстанавливать архивы")
                        else:
                            try:
                                gist_url = f"{GITHUB_API}/gists/{archive.get('id')}"
                                gist_resp = requests.get(gist_url, headers=github_headers())
                                gist_resp.raise_for_status()
                                files = gist_resp.json().get("files", {})
                                content = next((f["content"] for f in files.values() if "content" in f), "")
                                
                                if content:
                                    restored_data = json.loads(content)
                                    st.session_state.data = restored_data
                                    save_data(st.session_state.data)
                                    log_action(st.session_state.username, "Restore Archive", f"Restored archive: {archive_name}")
                                    st.success("Архив успешно восстановлен! Обновите страницу.")
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Не удалось получить содержимое архива")
                            except Exception as e:
                                st.error(f"Ошибка восстановления: {str(e)}")

                with col3:
                    if st.button("🗑️ Удалить", key=f"del_{archive.get('id', '')}"):
                        if st.session_state.role != "admin":
                            st.warning("Только администратор может удалять архивы")
                        else:
                            try:
                                gist_url = f"{GITHUB_API}/gists/{archive.get('id')}"
                                del_resp = requests.delete(gist_url, headers=github_headers())
                                
                                if del_resp.status_code == 204:
                                    st.session_state.data["_archives"] = [
                                        a for a in st.session_state.data["_archives"]
                                        if a.get("id") != archive.get("id")
                                    ]
                                    save_data(st.session_state.data)
                                    log_action(st.session_state.username, "Delete Archive", f"Deleted archive: {archive_name}")
                                    st.success("Архив удален!")
                                    st.rerun()
                                else:
                                    st.error(f"Ошибка удаления: {del_resp.status_code}")
                            except Exception as e:
                                st.error(f"Ошибка удаления: {str(e)}")
def show_version_view_page():
    """Страница для просмотра конкретной версии"""
    if 'viewing_version' not in st.session_state:
        st.warning("Версия не выбрана")
        st.session_state.page = "version_history"
        st.rerun()
    
    st.header("👀 Просмотр версии данных")
    st.code(st.session_state.viewing_version, language='json')
    
    if st.button("← Назад к истории"):
        st.session_state.page = "version_history"
        st.rerun()
def show_payments_report():
    st.header("📊 Отчет по оплатам")
    
    if not st.session_state.data['payments']:
        st.info("Нет данных по оплатам.")
        return
    
    df_payments = pd.DataFrame(st.session_state.data['payments'])
    
    df_payments['date'] = pd.to_datetime(df_payments['date'])
    student_id_to_name = {s['id']: s['name'] for s in st.session_state.data['students']}
    df_payments['student'] = df_payments['student_id'].map(student_id_to_name)
    
    with st.expander("🔍 Фильтры", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Начальная дата", 
                value=df_payments['date'].min().date(),
                key="payments_start_date"
            )
        with col2:
            end_date = st.date_input(
                "Конечная дата", 
                value=df_payments['date'].max().date(),
                key="payments_end_date"
            )
        
        direction_filter = st.multiselect(
            "Фильтр по направлениям",
            options=df_payments['direction'].unique(),
            key="payments_direction_filter"
        )
        
        type_filter = st.multiselect(
            "Фильтр по типам оплат",
            options=df_payments['type'].unique(),
            key="payments_type_filter"
        )
    
    df_filtered = df_payments[
        (df_payments['date'].dt.date >= start_date) & 
        (df_payments['date'].dt.date <= end_date)
    ]
    
    if direction_filter:
        df_filtered = df_filtered[df_filtered['direction'].isin(direction_filter)]
    
    if type_filter:
        df_filtered = df_filtered[df_filtered['type'].isin(type_filter)]
    
    if df_filtered.empty:
        st.info("Нет данных по оплатам за выбранный период.")
        return
    
    df_filtered['Удалить'] = False
    
    # ---> ИЗМЕНЕНИЕ ЗДЕСЬ: Собираем список всех направлений для выпадающего списка
    main_directions = [d['name'] for d in st.session_state.data['directions']]
    sub_directions = [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]
    all_direction_options = sorted(list(set(main_directions + sub_directions)))
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    st.subheader("Редактирование оплат")
    edited_df = st.data_editor(
        df_filtered[['id', 'student_id', 'student', 'date', 'amount', 'direction', 'type', 'notes', 'Удалить']],
        use_container_width=True,
        hide_index=True,
        disabled=['id', 'student'],
        column_config={
            "student_id": None, # Скрываем колонку
            "date": st.column_config.DateColumn("Дата", format="DD.MM.YYYY"),
            "amount": st.column_config.NumberColumn("Сумма", format="%.2f ₽"),
            
            # ---> ИЗМЕНЕНИЕ ЗДЕСЬ: TextColumn заменен на SelectboxColumn
            "direction": st.column_config.SelectboxColumn(
                "Направление",
                help="Выберите направление из списка",
                options=all_direction_options,
                required=True
            ),
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            "type": st.column_config.SelectboxColumn("Тип оплаты", options=["Абонемент", "Разовое", "Пробное", "Другое"]),
            "notes": st.column_config.TextColumn("Примечание"),
            "Удалить": st.column_config.CheckboxColumn("Удалить?", default=False)
        }
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Сохранить изменения", key="save_payments_changes"):
            # Обновляем данные
            for _, row in edited_df.iterrows():
                if not row['Удалить']:
                    payment_id = row['id']
                    for payment in st.session_state.data['payments']:
                        if payment['id'] == payment_id:
                            payment['date'] = row['date'].strftime("%Y-%m-%d")
                            payment['amount'] = float(row['amount'])
                            payment['direction'] = row['direction']
                            payment['type'] = row['type']
                            payment['notes'] = row['notes']
                            
                            if payment['type'] == "Абонемент":
                                student_id = payment['student_id']
                                p_date = row['date']
                                direction = payment['direction']
                                
                                for schedule_item in st.session_state.data['schedule'] + st.session_state.data.get('archived_schedule', []):
                                    if schedule_item['direction'] == direction:
                                        day_map = {"Понедельник": 0, "Вторник": 1, "Среда": 2, "Четверг": 3, "Пятница": 4, "Суббота": 5, "Воскресенье": 6}
                                        target_weekday = day_map.get(schedule_item['day'])
                                        
                                        if target_weekday is not None:
                                            current_date = p_date.replace(day=1)
                                            while current_date.month == p_date.month:
                                                if current_date.weekday() == target_weekday and current_date >= p_date:
                                                    date_key = current_date.strftime("%Y-%m-%d")
                                                    lesson_id = schedule_item['id']
                                                    
                                                    st.session_state.data['attendance'].setdefault(date_key, {}).setdefault(lesson_id, {}).setdefault(student_id, {'present': False, 'note': 'Абонемент'})
                                                    st.session_state.data['attendance'][date_key][lesson_id][student_id]['paid'] = True
                                                
                                                current_date += timedelta(days=1)
                            break
            
            payments_to_delete = edited_df[edited_df['Удалить']]['id'].tolist()
            st.session_state.data['payments'] = [p for p in st.session_state.data['payments'] if p['id'] not in payments_to_delete]
            
            save_data(st.session_state.data)
            log_action(st.session_state.username, "Edit Payments", "Updated payments table")
            st.success("Изменения сохранены и синхронизированы!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Сбросить фильтры", key="reset_payments_filters"):
            st.session_state.pop('payments_start_date', None)
            st.session_state.pop('payments_end_date', None)
            st.session_state.pop('payments_direction_filter', None)
            st.session_state.pop('payments_type_filter', None)
            st.rerun()
    
    with col3:
        csv = df_filtered.drop(columns=['Удалить']).to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Экспорт в CSV",
            data=csv,
            file_name=f"payments_report_{start_date}_{end_date}.csv",
            mime="text/csv",
            key="export_payments"
        )
    # Умный калькулятор
    with st.expander("🧮 Умный калькулятор переноса занятий", expanded=True):
        calc_col1, calc_col2 = st.columns([3, 2])
        
        with calc_col1:
            calc_input = st.text_input("Введите выражение (например: 5000*15%):", 
                                    key="payment_calculator")
            try:
                if calc_input:
                    # Поддержка процентов и математических операций
                    calc_input = calc_input.replace('%', '/100')
                    result = eval(calc_input)
                    st.success(f"Результат: {result:.2f} ₽")
            except Exception as e:
                st.error(f"Ошибка в выражении: {str(e)}")
        
        with calc_col2:
            direction_transfer = st.selectbox(
                "Направление для переноса",
                [None] + [d['name'] for d in st.session_state.data['directions']],
                key="transfer_direction"
            )
            
            if direction_transfer:
                direction = next((d for d in st.session_state.data['directions'] 
                                if d['name'] == direction_transfer), None)
                
                if direction:
                    monthly_cost = direction.get('cost', 0)
                    lessons_in_month = calculate_lessons_in_month(direction_transfer, datetime.now())
                    
                    if lessons_in_month > 0:
                        cost_per_lesson = monthly_cost / lessons_in_month
                        st.markdown(f"""
                        **Расчет:**  
                        Абонемент: {monthly_cost} ₽  
                        Занятий в этом месяце: {lessons_in_month}  
                        Стоимость одного занятия: {cost_per_lesson:.2f} ₽
                        """)
                        
                        num_lessons = st.number_input("Кол-во переносимых занятий", 
                                                    min_value=1, value=1, 
                                                    key="num_transfer_lessons")
                        transfer_cost = cost_per_lesson * num_lessons
                        
                        if st.button("Рассчитать сумму переноса", key="calculate_transfer"):
                            st.success(f"**Сумма к переносу:** {transfer_cost:.2f} ₽")
                            
                            # Поиск альтернативных занятий
                            st.subheader("Можно перенести на:")
                            alternatives = []
                            for alt_dir in st.session_state.data['directions']:
                                if alt_dir['name'] != direction_transfer:
                                    alt_lessons = calculate_lessons_in_month(alt_dir['name'], datetime.now())
                                    if alt_lessons > 0:
                                        alt_cost_per = alt_dir.get('cost', 0) / alt_lessons
                                        alt_num = transfer_cost / alt_cost_per
                                        alternatives.append((
                                            alt_dir['name'],
                                            alt_num,
                                            alt_cost_per
                                        ))
                            
                            # Сортируем по близости количества занятий
                            alternatives.sort(key=lambda x: abs(x[1] - num_lessons))
                            
                            for alt in alternatives[:3]:  # Показываем топ-3 варианта
                                st.write(
                                    f"- {alt[0]}: {alt[1]:.1f} занятий "
                                    f"(цена {alt[2]:.2f} ₽/занятие)"
                                )
                    else:
                        st.warning("Для выбранного направления нет занятий в этом месяце!")
    # Статистика
    if st.session_state.role != 'reception':
        st.subheader("📈 Статистика")
        total_payments = df_filtered['amount'].sum()
        st.metric("Общая сумма оплат", f"{total_payments:.2f} ₽")
        
        tab1, tab2 = st.tabs(["По направлениям", "По типам оплат"])
        
        with tab1:
            if not df_filtered.empty:
                payments_by_direction = df_filtered.groupby('direction')['amount'].sum().reset_index()
                st.bar_chart(payments_by_direction.set_index('direction'))
                
                with st.expander("Таблица данных"):
                    st.dataframe(
                        payments_by_direction.sort_values('amount', ascending=False),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "direction": "Направление",
                            "amount": st.column_config.NumberColumn(
                                "Сумма",
                                format="%.2f ₽"
                            )
                        }
                    )
        
        with tab2:
            if not df_filtered.empty:
                payments_by_type = df_filtered.groupby('type')['amount'].sum().reset_index()
                st.bar_chart(payments_by_type.set_index('type'))
                
                with st.expander("Таблица данных"):
                    st.dataframe(
                        payments_by_type.sort_values('amount', ascending=False),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "type": "Тип оплаты",
                            "amount": st.column_config.NumberColumn(
                                "Сумма",
                                format="%.2f ₽"
                            )
                        }
                    )

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
    
     # Создаем вкладки
    tab1, tab2 = st.tabs(["Подбор направлений",  "Запись на разовые занятия"])

    with tab1:
        # Создаем словарь категорий направлений
        direction_categories = {
            "Языки и коммуникация": [
                "Занимательный английский",
                "Занимательный французский", 
                "Речевая студия \"Говоруша\" (3-5 лет)",
                "Логопедические занятия"
            ],
            
            "Творчество и искусство": [
                "Театральная студия с 5 лет",
                "Студия рисования и творчества \"Разноцветные ладошки\" (3-6 лет)",
                "Студия живописи и творчества \"Юный Пикассо\" с 7 лет",
                "Студия лепки с 5 лет",
                "Студия рисования Мастерская чудес (4-6 лет)",
                "Студия творчества Арт-фантазия (с 7 лет)"
            ],
            "Музыка":[
                "Вокальная студия \"Творческий пульс\" с 9 лет",
                "Вокальная студия с 4 лет",
                "Вокально-инструментальный ансамбль \"Мелодия сердца\" (с 11 лет)",
                "Индивидуальные занятия по гитаре"
            ],
            
            "Танцы и движение": [
                "Танцевальная студия \"Грация\" с 7 лет",
                "Танцевальная студия \"Бусинки\" с 3 лет"
            ],
            
            "Наука и технологии": [
                "Программирование \"Проги Дарования\" с 11 лет",
                "Курс \"Юные биологи\" (5-8 кл)",
                "Курс \"Мир химии: от теории к практике\" (7-9 кл)"
            ],
            
            "Интеллектуальное развитие": [
                "Шахматный клуб \"CHESSVEB\" с 4 лет",
                "Курс \"Машина времени: приключения в прошлое\" (5-7 кл)",
                "Курс \"Ты - общество. Просто о важном\" (14-17 лет)"
            ],
            
            "Подготовка к школе": [
                "\"Скоро в школу\" (5-6 лет)",
                "Курс \"Пишу красиво\" (1-3 класс) в группе",
                "Курс \"Пишу красиво\" (1-4 класс) индивидуально"
            ],
            
            "Школьные предметы": [
                "Увлекательный русский язык (5-9 класс) в группе",
                "Увлекательная математика (5-9 класс) в группе",
                "Индивидуальные занятия по математике",
                "Индивидуальные занятия по чтению", 
                "Индивидуальные занятия по русскому языку",
                "Курс \"Юные биологи\" (5-8 кл)",
                "Курс \"Мир химии: от теории к практике\" (7-9 кл)",
                "Курс \"Машина времени: приключения в прошлое\" (5-7 кл)",
                "Курс \"Ты - общество. Просто о важном\" (14-17 лет)"
            ]
        }
        
        with st.form("child_info_form"):
            col1, col2 = st.columns(2)
            with col1:
                child_age = st.number_input("Возраст ребенка", min_value=0, max_value=30, value=5)
                gender = st.selectbox("Пол ребенка", ["Не важно", "Девочка", "Мальчик"])
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
                                        st.write(f"**Разовое занятие:** {direction.get('trial_cost', '?')} руб.")
                                        
                                        if direction.get('description'):
                                            st.caption(direction['description'])
                else:
                    st.info("К сожалению, нет подходящих направлений для указанных параметров.")
                # Умный калькулятор
        with st.expander("🧮 Умный калькулятор переноса занятий", expanded=True):
            calc_col1, calc_col2 = st.columns([3, 2])
            
            with calc_col1:
                calc_input = st.text_input("Введите выражение (например: 5000*15%):", 
                                        key="payment_calculator")
                try:
                    if calc_input:
                        # Поддержка процентов и математических операций
                        calc_input = calc_input.replace('%', '/100')
                        result = eval(calc_input)
                        st.success(f"Результат: {result:.2f} ₽")
                except Exception as e:
                    st.error(f"Ошибка в выражении: {str(e)}")
            
            with calc_col2:
                direction_transfer = st.selectbox(
                    "Направление для переноса",
                    [None] + [d['name'] for d in st.session_state.data['directions']],
                    key="transfer_direction"
                )
                
                if direction_transfer:
                    direction = next((d for d in st.session_state.data['directions'] 
                                    if d['name'] == direction_transfer), None)
                    
                    if direction:
                        monthly_cost = direction.get('cost', 0)
                        lessons_in_month = calculate_lessons_in_month(direction_transfer, datetime.now())
                        
                        if lessons_in_month > 0:
                            cost_per_lesson = monthly_cost / lessons_in_month
                            st.markdown(f"""
                            **Расчет:**  
                            Абонемент: {monthly_cost} ₽  
                            Занятий в этом месяце: {lessons_in_month}  
                            Стоимость одного занятия: {cost_per_lesson:.2f} ₽
                            """)
                            
                            num_lessons = st.number_input("Кол-во переносимых занятий", 
                                                        min_value=1, value=1, 
                                                        key="num_transfer_lessons")
                            transfer_cost = cost_per_lesson * num_lessons
                            
                            if st.button("Рассчитать сумму переноса", key="calculate_transfer"):
                                st.success(f"**Сумма к переносу:** {transfer_cost:.2f} ₽")
                                
                                # Поиск альтернативных занятий
                                st.subheader("Можно перенести на:")
                                alternatives = []
                                for alt_dir in st.session_state.data['directions']:
                                    if alt_dir['name'] != direction_transfer:
                                        alt_lessons = calculate_lessons_in_month(alt_dir['name'], datetime.now())
                                        if alt_lessons > 0:
                                            alt_cost_per = alt_dir.get('cost', 0) / alt_lessons
                                            alt_num = transfer_cost / alt_cost_per
                                            alternatives.append((
                                                alt_dir['name'],
                                                alt_num,
                                                alt_cost_per
                                            ))
                                
                                # Сортируем по близости количества занятий
                                alternatives.sort(key=lambda x: abs(x[1] - num_lessons))
                                
                                for alt in alternatives[:3]:  # Показываем топ-3 варианта
                                    st.write(
                                        f"- {alt[0]}: {alt[1]:.1f} занятий "
                                        f"(цена {alt[2]:.2f} ₽/занятие)"
                                    )
                        else:
                            st.warning("Для выбранного направления нет занятий в этом месяце!")
    with tab2:
        st.header("📝 Запись на разовые занятия / В группу")
        # 1. Выбор или добавление ученика
        with st.expander("👦 Выбор ученика", expanded=True):
            students = st.session_state.data['students']
            student_options = {s['id']: s['name'] for s in students}
            
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_student_id = st.selectbox(
                    "Выберите ученика",
                    options=["Новый ученик"] + list(student_options.keys()),
                    format_func=lambda x: "Новый ученик" if x == "Новый ученик" else student_options[x],
                    key="single_lesson_student"
                )
            
            # Форма для нового ученика
            if selected_student_id == "Новый ученик":
                with st.form("new_student_form_single"):
                    name = st.text_input("ФИО*", key="single_lesson_name")
                    dob = st.date_input("Дата рождения*", key="single_lesson_dob")
                    gender = st.selectbox("Пол", ["Мальчик", "Девочка"], key="single_lesson_gender")
                    parent_name = st.text_input("Имя родителя", key="single_lesson_parent_name")
                    parent_phone = st.text_input("Телефон родителя", key="single_lesson_parent_phone")
                    
                    if st.form_submit_button("Добавить ученика"):
                        if name and dob:
                            new_parent = {
                                'id': str(uuid.uuid4()),
                                'name': parent_name,
                                'phone': parent_phone,
                                'children_ids': []
                            }
                            st.session_state.data['parents'].append(new_parent)
                            
                            new_student = {
                                'id': str(uuid.uuid4()),
                                'name': name,
                                'dob': str(dob),
                                'gender': gender,
                                'parent_id': new_parent['id'],
                                'directions': [],
                                'registration_date': str(date.today())
                            }
                            st.session_state.data['students'].append(new_student)
                            selected_student_id = new_student['id']
                            save_data(st.session_state.data)
                            log_action(st.session_state.username, "Add Student (Reception)", f"Added {name}")
                            st.success("Ученик добавлен!")
                            st.rerun()
        
        if selected_student_id == "Новый ученик":
            return
        
        # 2. Выбор направления/поднаправления
        with st.expander("🎯 Выбор занятия", expanded=True):
            dir_options = [d['name'] for d in st.session_state.data['directions']]
            subdir_options = [f"{s['parent']} ({s['name']})" for s in st.session_state.data.get('subdirections', [])]
            selected_direction = st.selectbox(
                "Направление*",
                options=dir_options + subdir_options,
                key="single_lesson_direction"
            )
        
        # 3. Выбор даты
        with st.expander("📅 Дата занятия", expanded=True):
            selected_date = st.date_input(
                "Дата занятия*",
                min_value=date.today(),
                max_value=date.today() + timedelta(days=90),
                key="single_lesson_date"
            )
            date_str = selected_date.strftime("%Y-%m-%d")
            day_name = selected_date.strftime("%A")
            russian_day = {
                "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
                "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
            }.get(day_name, day_name)
        
        # 4. Поиск преподавателей и классов
        with st.expander("👩‍🏫 Преподаватели и классы", expanded=True):
            # --- ИЗМЕНЕНИЕ: Добавлена возможность показать всех преподавателей ---
            show_all_teachers = st.checkbox("Показать всех преподавателей (для замены)", value=False)
            
            if show_all_teachers:
                 teachers_for_direction = st.session_state.data['teachers']
            else:
                # Преподаватели для выбранного направления (старая логика)
                teachers_for_direction = [
                    t for t in st.session_state.data['teachers']
                    if (selected_direction in t.get('directions', []) or
                        any(f"{s['parent']} ({s['name']})" in t.get('directions', [])
                            for s in st.session_state.data.get('subdirections', [])
                            if f"{s['parent']} ({s['name']})" == selected_direction))
                ]
            
            if not teachers_for_direction:
                st.error("Нет преподавателей для выбранного направления (попробуйте галочку 'Показать всех')")
                return
            
            teacher_options = {t['id']: t['name'] for t in teachers_for_direction}
            selected_teacher_id = st.selectbox(
                "Преподаватель*",
                options=list(teacher_options.keys()),
                format_func=lambda x: teacher_options[x],
                key="single_lesson_teacher"
            )
            selected_teacher = next((t for t in teachers_for_direction if t['id'] == selected_teacher_id), None)
            
            # Поиск подходящего класса
            classrooms = st.session_state.data.get('classrooms', [])
            suitable_classroom = None
            for room in classrooms:
                if selected_direction in room.get('directions', []):
                    suitable_classroom = room
                    break
            if not suitable_classroom:
                suitable_classroom = next((r for r in classrooms if r.get('name') == 'Малый класс'), None)
            
            if suitable_classroom:
                st.info(f"**Класс:** {suitable_classroom.get('name', 'Неизвестно')}")
        
        with st.expander("🕒 Выбор времени", expanded=True):
            # Получаем все занятия на выбранную дату
            regular_lessons = [l for l in st.session_state.data['schedule'] if l['day'] == russian_day]
            single_lessons = [l for l in st.session_state.data.get('single_lessons', []) if l['date'] == date_str]
            all_lessons = regular_lessons + single_lessons
            
            time_slots = [f"{h:02d}:{m:02d}" for h in range(9, 20) for m in [0, 15, 30, 45]]
            schedule_df = pd.DataFrame(index=time_slots)
            schedule_df['Преподаватель'] = "✅ Свободно"
            schedule_df['Класс'] = "✅ Свободно"
            
            # --- ИЗМЕНЕНИЕ: Логика проверки преподавателя ---
            for lesson in all_lessons:
                if lesson.get('teacher') == selected_teacher['name']:
                    lesson_start = datetime.strptime(lesson['start_time'], "%H:%M")
                    lesson_end = datetime.strptime(lesson['end_time'], "%H:%M")

                    for slot in time_slots:
                        slot_time = datetime.strptime(slot, "%H:%M")
                        if lesson_start <= slot_time < lesson_end:
                            # Если направление совпадает, разрешаем присоединиться!
                            if lesson['direction'] == selected_direction:
                                schedule_df.at[slot, 'Преподаватель'] = f"👥 Группа ({lesson['start_time']})"
                            else:
                                schedule_df.at[slot, 'Преподаватель'] = f"❌ {lesson['start_time']}-{lesson['end_time']} ({lesson['direction']})"

            # --- ИЗМЕНЕНИЕ: Логика проверки класса ---
            for lesson in all_lessons:
                # Проверяем занятость класса, только если это не тот же урок (по направлению)
                # Если мы присоединяемся к группе, мы идем в тот же класс, это ОК.
                if lesson.get('classroom') == suitable_classroom['id']:
                    lesson_start = datetime.strptime(lesson['start_time'], "%H:%M")
                    lesson_end = datetime.strptime(lesson['end_time'], "%H:%M")
                    
                    for slot in time_slots:
                        slot_time = datetime.strptime(slot, "%H:%M")
                        if lesson_start <= slot_time < lesson_end:
                             if lesson['direction'] == selected_direction:
                                 schedule_df.at[slot, 'Класс'] = f"👥 Группа тут"
                             else:
                                 schedule_df.at[slot, 'Класс'] = f"❌ {lesson['start_time']}..."
            
            # Определяем доступные слоты (Свободно ИЛИ Группа по теме)
            available_slots = [
                slot for slot in time_slots
                if ("✅" in schedule_df.at[slot, 'Преподаватель'] or "👥" in schedule_df.at[slot, 'Преподаватель']) and 
                   ("✅" in schedule_df.at[slot, 'Класс'] or "👥" in schedule_df.at[slot, 'Класс'])
            ]
            
            def color_availability(val):
                if "✅" in val: return 'background-color: lightgreen'
                if "👥" in val: return 'background-color: lightblue' # Цвет для групп
                return 'background-color: lightcoral'
            
            st.dataframe(
                schedule_df.style.applymap(color_availability),
                use_container_width=True,
                height=400,
                column_config={
                    "Преподаватель": st.column_config.TextColumn("Занятость преподавателя"),
                    "Класс": st.column_config.TextColumn("Занятость класса")
                }
            )
            
            if not available_slots:
                st.error("Нет подходящих окон (занято другим предметом)")
                return
            
            col1, col2 = st.columns(2)
            with col1:
                selected_time = st.selectbox("Выберите время начала*", options=available_slots, key="single_lesson_time")
            with col2:
                duration = st.selectbox("Продолжительность*", options=["30 мин", "45 мин", "60 мин"], index=1)
            
            # Расчет конца занятия
            start_dt = datetime.strptime(selected_time, "%H:%M")
            duration_mins = int(duration.split()[0])
            end_time = (start_dt + timedelta(minutes=duration_mins)).strftime("%H:%M")
            
            st.success(f"Выбрано время: {selected_time}-{end_time}")

        with st.expander("📝 Дополнительно", expanded=False):
            notes = st.text_area("Примечание", key="single_lesson_notes")
        
        # 7. Подтверждение и сохранение
        if st.button("✅ Записать (Разовое/В группу)", key="single_lesson_submit"):
            new_lesson = {
                'id': str(uuid.uuid4()),
                'student_id': selected_student_id,
                'direction': selected_direction,
                'teacher': selected_teacher['name'], # Здесь сохраняется выбранный вами преподаватель (даже если это замена)
                'teacher_id': selected_teacher_id,
                'date': date_str,
                'start_time': selected_time,
                'end_time': end_time,
                'classroom': suitable_classroom['id'],
                'classroom_name': suitable_classroom.get('name', ''),
                'notes': notes,
                'type': 'single', # Маркер, что это запись конкретного ученика
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'created_by': st.session_state.username
            }
            
            st.session_state.data.setdefault('single_lessons', []).append(new_lesson)
            
            # Создаем запись о посещении
            if date_str not in st.session_state.data['attendance']:
                st.session_state.data['attendance'][date_str] = {}
            
            # Важно: создаем отдельную запись посещения для этого "разового" входа
            st.session_state.data['attendance'][date_str][new_lesson['id']] = {
                selected_student_id: {
                    'present': False,
                    'paid': False,
                    'note': notes or "Разовое/В группе"
                }
            }
            
            save_data(st.session_state.data)
            log_action(st.session_state.username, "Book Single Lesson", f"Booked {selected_direction} for {selected_student_id}")
            st.success(f"Ученик записан к преподавателю {selected_teacher['name']}!")
            st.rerun()
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
        with st.sidebar.expander("🔐 Администрирование", expanded=False):
            st.button("⚙️ Управление данными", on_click=lambda: _navigate_to('data_management'))
            st.button("🔄 История версий", on_click=lambda: _navigate_to('version_history'))
            st.button("📦 Архивы данных", on_click=lambda: _navigate_to('data_archives'))
            
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("🎨 Направления", on_click=lambda: _navigate_to('directions'))
        st.sidebar.button("👦 Ученики и оплаты", on_click=lambda: _navigate_to('students'))
        st.sidebar.button("👩‍🏫 Преподаватели", on_click=lambda: _navigate_to('teachers'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: _navigate_to('schedule'))
        st.sidebar.button("💰 Финансы и Абонементы", on_click=lambda: _navigate_to('financial_control'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        #st.sidebar.button("🖼️ Медиа-галерея", on_click=lambda: _navigate_to('media_gallery'))
        st.sidebar.button("📤 Массовая загрузка", on_click=lambda: _navigate_to('bulk_upload'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: _navigate_to('reception_helper'))
        
        st.sidebar.markdown("---")
        st.sidebar.button("🕵️ История действий", on_click=lambda: _navigate_to('audit_log'))
        st.sidebar.button("📊 Отчет по оплатам", on_click=lambda: _navigate_to('payments_report'))
        st.sidebar.button("📊 Отчет по закупкам", on_click=lambda: _navigate_to('materials_report'))
        
    elif st.session_state.role == 'teacher':
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("👩‍🏫 Преподаватели", on_click=lambda: _navigate_to('teachers'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        #st.sidebar.button("🖼️ Медиа-галерея", on_click=lambda: _navigate_to('media_gallery'))
    
    elif st.session_state.role == 'reception':
        st.sidebar.button("🏠 Главная", on_click=lambda: _navigate_to('home'))
        st.sidebar.button("🎨 Направления", on_click=lambda: _navigate_to('directions'))
        st.sidebar.button("👦 Ученики и оплаты", on_click=lambda: _navigate_to('students'))
        st.sidebar.button("📅 Расписание и посещения", on_click=lambda: _navigate_to('schedule'))
        st.sidebar.button("💰 Финансы и Абонементы", on_click=lambda: _navigate_to('financial_control'))
        st.sidebar.button("🛍️ Материалы и закупки", on_click=lambda: _navigate_to('materials'))
        st.sidebar.button("📌 Канбан-доска", on_click=lambda: _navigate_to('kanban'))
        st.sidebar.button("👋 Помощник ресепшена", on_click=lambda: _navigate_to('reception_helper'))
        st.sidebar.markdown("---")
        st.sidebar.button("📊 Отчет по оплатам", on_click=lambda: _navigate_to('payments_report'))
    elif st.session_state.page == 'audit_log':
        show_audit_log_page()
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
                    'subdirections': [], 
                    'students': [],
                    'teachers': [],
                    'parents': [],
                    'payments': [],
                    'schedule': [],
                    'materials': [],
                    'single_lessons': [], 
                    'kanban_tasks': {'ToDo': [], 'InProgress': [], 'Done': []},
                    'attendance': {},
                    'settings': {'trial_cost': 500, 'single_cost_multiplier': 1.5},
                    'classrooms': [
                                    {
                                        'id': 'classroom_1',
                                        'name': 'Танцзал',
                                        'capacity': 15,
                                        'directions': [
                                            "Вокальная студия \"Творческий пульс\" с 9 лет",
                                            "Вокальная студия с 4 лет",
                                            "Театральная студия с 5 лет",
                                            "Танцевальная студия \"Грация\" с 7 лет",
                                            "Танцевальная студия \"Бусинки\" с 3 лет",
                                            "Вокально-инструментальный ансамбль \"Мелодия сердца\" (с 11 лет)",
                                            "Индивидуальные занятия по гитаре"
                                        ]
                                    },
                                    {
                                        'id': 'classroom_2',
                                        'name': 'Большой класс',
                                        'capacity': 10,
                                        'directions': [
                                            "Занимательный английский",
                                            "Занимательный французский",
                                            "Программирование \"Проги Дарования\" с 11 лет",
                                            "Шахматный клуб \"CHESSVEB\" с 4 лет",
                                            "\"Скоро в школу\" (5-6 лет)",
                                            "Курс \"Машина времени: приключения в прошлое\" (5-7 кл)",
                                            "Курс \"Юные биологи\" (5-8 кл)",
                                            "Курс \"Мир химии: от теории к практике\" (7-9 кл)",
                                            "Курс \"Ты - общество. Просто о важном\"          (14-17 лет)",
                                            "Увлекательный русский язык (5-9 класс) в группе",
                                            "Увлекательная математика (5-9 класс) в группе",
                                            "Студия рисования и творчества \"Разноцветные ладошки\" (3-6 лет)",
                                            "Студия живописи и творчества \"Юный Пикассо\" с 7 лет",
                                            "Студия лепки с 5 лет",
                                            "Речевая студия \"Говоруша\" (3-5 лет)",
                                            "Курс \"Пишу красиво\" (1-3 класс) в группе",
                                            "Курс \"Пишу красиво\" (1-4 класс) индивидуально",
                                            "Логопедические занятия",
                                            "Индивидуальные занятия по математике",
                                            "Индивидуальные занятия по чтению",
                                            "Индивидуальные занятия по русскому языку"
                                        ]  
                                    },
                                    {
                                        'id': 'classroom_3',
                                        'name': 'Малый класс',
                                        'capacity': 6,
                                        'directions': [
                                            "Занимательный английский",
                                            "Занимательный французский",
                                            "Программирование \"Проги Дарования\" с 11 лет",
                                            "Шахматный клуб \"CHESSVEB\" с 4 лет",
                                            "\"Скоро в школу\" (5-6 лет)",
                                            "Курс \"Машина времени: приключения в прошлое\" (5-7 кл)",
                                            "Курс \"Юные биологи\" (5-8 кл)",
                                            "Курс \"Мир химии: от теории к практике\" (7-9 кл)",
                                            "Курс \"Ты - общество. Просто о важном\"          (14-17 лет)",
                                            "Увлекательный русский язык (5-9 класс) в группе",
                                            "Увлекательная математика (5-9 класс) в группе",
                                            "Студия рисования и творчества \"Разноцветные ладошки\" (3-6 лет)",
                                            "Студия живописи и творчества \"Юный Пикассо\" с 7 лет",
                                            "Студия творчества Арт-фантазия (с 7 лет)",
                                            "Студия рисования Мастерская чудес (4-6 лет)",
                                            "Студия лепки с 5 лет",
                                            "Речевая студия \"Говоруша\" (3-5 лет)",
                                            "Курс \"Пишу красиво\" (1-3 класс) в группе",
                                            "Курс \"Пишу красиво\" (1-4 класс) индивидуально",
                                            "Индивидуальные занятия по математике",
                                            "Индивидуальные занятия по чтению",
                                            "Индивидуальные занятия по русскому языку"
                                        ]
                                    }
                                ]
                }
                save_data(initial_data)
                st.session_state.data = load_data()
                log_action(st.session_state.username, "Clear Data", "Cleared all data")
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
    elif st.session_state.page == 'financial_control':
        show_financial_control_page()
    elif st.session_state.page == 'materials':
        show_materials_page()
    elif st.session_state.page == 'kanban':
        show_kanban_board()
    elif st.session_state.page == 'bulk_upload':
        show_bulk_upload_page()
    elif st.session_state.page == 'payments_report':
        show_payments_report()
    elif st.session_state.page == 'materials_report':
        show_materials_report()
    elif st.session_state.page == 'reception_helper':
        show_reception_helper()
    elif st.session_state.page == 'data_management':
        show_data_management_page()
    elif st.session_state.page == 'version_history':
        show_version_history_page()
    elif st.session_state.page == 'data_archives':
        show_data_archives_page()
    elif st.session_state.page == 'view_version':
        show_version_view_page()
    else:
        st.info("Выберите раздел в меню слева.")
