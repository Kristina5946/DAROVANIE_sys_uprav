import json
from collections import defaultdict

def load_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def time_to_minutes(t):
    if isinstance(t, str):
        time_parts = t.split(':')
        return int(time_parts[0]) * 60 + int(time_parts[1])
    return 0

def minutes_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"

def is_time_overlap(slot_start, slot_end, lesson_start, lesson_end):
    return not (slot_end <= lesson_start or slot_start >= lesson_end)

def get_busy_times_for_teachers(data, day):
    teacher_busy = defaultdict(list)
    for lesson in data['schedule']:
        if lesson['day'] == day:
            start = time_to_minutes(lesson['start_time'])
            end = time_to_minutes(lesson['end_time'])
            teacher_busy[lesson['teacher']].append((start, end))
    return teacher_busy

def get_busy_times_for_classrooms(data, day):
    classroom_busy = defaultdict(list)
    for lesson in data['schedule']:
        if lesson['day'] == day:
            start = time_to_minutes(lesson['start_time'])
            end = time_to_minutes(lesson['end_time'])
            # Находим какие классы подходят для этого направления
            for classroom in data['classrooms']:
                if lesson['direction'] in classroom['directions']:
                    classroom_busy[classroom['name']].append((start, end))
    return classroom_busy

def find_available_slots(data, direction_name, day, min_duration=60):
    direction = next((d for d in data['directions'] if d['name'] == direction_name), None)
    if not direction:
        return []
    
    teachers = [t['name'] for t in data['teachers'] if direction_name in t['directions']]
    classrooms = [c['name'] for c in data['classrooms'] if direction_name in c['directions']]
    
    if not teachers or not classrooms:
        return []
    
    day_schedule = [lesson for lesson in data['schedule'] if lesson['day'] == day]
    day_schedule.sort(key=lambda x: time_to_minutes(x['start_time']))
    
    teacher_busy = get_busy_times_for_teachers(data, day)
    classroom_busy = get_busy_times_for_classrooms(data, day)
    
    work_start = 9 * 60
    work_end = 20 * 60
    available_slots = []
    prev_end = work_start
    
    for lesson in day_schedule:
        lesson_start = time_to_minutes(lesson['start_time'])
        lesson_end = time_to_minutes(lesson['end_time'])
        
        if lesson_start > prev_end:
            duration = lesson_start - prev_end
            if duration >= min_duration:
                slot = {
                    'start': prev_end,
                    'end': lesson_start,
                    'duration': duration,
                    'day': day,
                    'direction': direction_name,
                    'available_teachers': [],
                    'available_classrooms': []
                }
                
                # Проверяем доступность преподавателей
                for teacher in teachers:
                    teacher_available = True
                    for busy_start, busy_end in teacher_busy.get(teacher, []):
                        if is_time_overlap(prev_end, lesson_start, busy_start, busy_end):
                            teacher_available = False
                            break
                    if teacher_available:
                        slot['available_teachers'].append(teacher)
                
                # Проверяем доступность классов
                for classroom in classrooms:
                    classroom_available = True
                    for busy_start, busy_end in classroom_busy.get(classroom, []):
                        if is_time_overlap(prev_end, lesson_start, busy_start, busy_end):
                            classroom_available = False
                            break
                    if classroom_available:
                        slot['available_classrooms'].append(classroom)
                
                if slot['available_teachers'] and slot['available_classrooms']:
                    available_slots.append(slot)
        
        prev_end = max(prev_end, lesson_end)
    
    if work_end > prev_end:
        duration = work_end - prev_end
        if duration >= min_duration:
            slot = {
                'start': prev_end,
                'end': work_end,
                'duration': duration,
                'day': day,
                'direction': direction_name,
                'available_teachers': [],
                'available_classrooms': []
            }
            
            for teacher in teachers:
                teacher_available = True
                for busy_start, busy_end in teacher_busy.get(teacher, []):
                    if is_time_overlap(prev_end, work_end, busy_start, busy_end):
                        teacher_available = False
                        break
                if teacher_available:
                    slot['available_teachers'].append(teacher)
            
            for classroom in classrooms:
                classroom_available = True
                for busy_start, busy_end in classroom_busy.get(classroom, []):
                    if is_time_overlap(prev_end, work_end, busy_start, busy_end):
                        classroom_available = False
                        break
                if classroom_available:
                    slot['available_classrooms'].append(classroom)
            
            if slot['available_teachers'] and slot['available_classrooms']:
                available_slots.append(slot)
    
    return available_slots

def print_all_slots(slots):
    if not slots:
        print("Нет свободных окон в расписании.")
        return
    
    days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    slots_by_day = defaultdict(list)
    
    for slot in slots:
        slots_by_day[slot['day']].append(slot)
    
    for day in days_order:
        if day in slots_by_day:
            print(f"\n{day}:")
            for slot in sorted(slots_by_day[day], key=lambda x: x['start']):
                start = minutes_to_time(slot['start'])
                end = minutes_to_time(slot['end'])
                print(f"  {start} - {end} ({slot['duration']} мин)")
                print(f"  Доступные преподаватели: {', '.join(slot['available_teachers'])}")
                print(f"  Доступные классы: {', '.join(slot['available_classrooms'])}")

def main():
    data = load_data('center_data.json')
    
    directions = [d['name'] for d in data['directions']]
    print("Доступные направления:")
    for i, direction in enumerate(directions, 1):
        print(f"{i}. {direction}")
    
    while True:
        try:
            choice = int(input("\nВыберите номер направления: ")) - 1
            if 0 <= choice < len(directions):
                selected_direction = directions[choice]
                break
            print("Пожалуйста, введите номер из списка.")
        except ValueError:
            print("Пожалуйста, введите число.")
    
    min_duration = int(input("Минимальная продолжительность занятия (мин): ") or 45)
    
    all_slots = []
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    
    for day in days:
        slots = find_available_slots(data, selected_direction, day, min_duration)
        all_slots.extend(slots)
    
    print(f"\nВсе свободные окна для '{selected_direction}':")
    print_all_slots(all_slots)

if __name__ == "__main__":
    main()