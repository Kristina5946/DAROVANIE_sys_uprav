import sys
import json
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QTableWidget, 
                             QTableWidgetItem, QTabWidget, QComboBox, QRadioButton, QButtonGroup,
                             QMessageBox, QHeaderView, QDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QClipboard

class ParentMessageDialog(QDialog):
    """
    Кастомное модальное окно для отображения сообщения и его копирования.
    """
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сообщение родителю")
        self.setGeometry(200, 200, 600, 400)
        
        self.layout = QVBoxLayout(self)

        # Метка и текстовое поле для сообщения
        self.message_label = QLabel("Сформированное сообщение:")
        self.layout.addWidget(self.message_label)

        self.message_text_edit = QTextEdit()
        self.message_text_edit.setPlainText(message)
        self.message_text_edit.setReadOnly(True)  # Запрещаем редактирование
        self.layout.addWidget(self.message_text_edit)

        # Кнопка для копирования текста
        self.copy_button = QPushButton("Копировать сообщение")
        self.copy_button.clicked.connect(self.copy_message)
        self.layout.addWidget(self.copy_button)
        
        # Кнопка для закрытия окна
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.accept) # Используем accept, чтобы закрыть окно
        self.layout.addWidget(self.close_button)

    def copy_message(self):
        """
        Копирует текст из QTextEdit в буфер обмена.
        """
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message_text_edit.toPlainText())
        QMessageBox.information(self, "Успешно", "Сообщение скопировано в буфер обмена.")


class EducationCenterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Образовательный центр - Управление")
        self.setGeometry(100, 100, 1000, 800)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Инициализация данных
        self.teachers_data = None
        self.payments_data = None
        self.students_data = None
        self.directions_data = None
        self.parents_data = None
        self.salary_results = None
        self.current_parent_phone = None
        
        # Создаем вкладки
        self.create_csv_tab()
        self.create_salary_tab()
        self.create_payment_calc_tab()
        
    def create_csv_tab(self):
        """Вкладка для обработки CSV файлов"""
        self.csv_tab = QWidget()
        self.csv_layout = QVBoxLayout()
        
        self.csv_label = QLabel("Обработка CSV файлов:")
        self.csv_layout.addWidget(self.csv_label)
        
        self.csv_button = QPushButton("Загрузить CSV файл")
        self.csv_button.clicked.connect(self.load_csv)
        self.csv_layout.addWidget(self.csv_button)
        
        self.csv_text = QTextEdit()
        self.csv_text.setReadOnly(True)
        self.csv_layout.addWidget(self.csv_text)
        
        self.csv_tab.setLayout(self.csv_layout)
        self.tabs.addTab(self.csv_tab, "Обработка CSV")
    
    def create_salary_tab(self):
        """Вкладка для расчета зарплаты"""
        self.salary_tab = QWidget()
        self.salary_layout = QVBoxLayout()
        
        self.salary_label = QLabel("Расчет зарплаты преподавателей:")
        self.salary_layout.addWidget(self.salary_label)
        
        self.json_button = QPushButton("Загрузить JSON с данными")
        self.json_button.clicked.connect(self.load_json)
        self.salary_layout.addWidget(self.json_button)
        
        self.payments_button = QPushButton("Загрузить CSV с платежами")
        self.payments_button.clicked.connect(self.load_payments)
        self.salary_layout.addWidget(self.payments_button)
        
        self.calculate_button = QPushButton("Рассчитать зарплату")
        self.calculate_button.clicked.connect(self.calculate_salary)
        self.salary_layout.addWidget(self.calculate_button)
        
        self.export_button = QPushButton("Экспорт в Excel")
        self.export_button.clicked.connect(self.export_salary)
        self.export_button.setEnabled(False)
        self.salary_layout.addWidget(self.export_button)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(['Преподаватель', 'Общая сумма', 'Зарплата (30%)'])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.salary_layout.addWidget(self.result_table)
        
        self.salary_tab.setLayout(self.salary_layout)
        self.tabs.addTab(self.salary_tab, "Расчет зарплаты")
    
    def create_payment_calc_tab(self):
        """Вкладка для расчета платежей"""
        self.payment_tab = QWidget()
        self.payment_layout = QVBoxLayout()
        
        # Загрузка данных
        self.load_data_button = QPushButton("Загрузить JSON с данными")
        self.load_data_button.clicked.connect(self.load_full_json)
        self.payment_layout.addWidget(self.load_data_button)
        
        # Выбор ученика
        self.student_label = QLabel("Выберите ученика:")
        self.payment_layout.addWidget(self.student_label)
        
        self.student_combo = QComboBox()
        self.student_combo.currentIndexChanged.connect(self.update_student_directions)
        self.payment_layout.addWidget(self.student_combo)
        
        # Таблица направлений
        self.directions_table = QTableWidget()
        self.directions_table.setColumnCount(4)
        self.directions_table.setHorizontalHeaderLabels([
            "Направление", "Абонемент", "Разовое", "Выбрать"
        ])
        self.directions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.payment_layout.addWidget(self.directions_table)
        
        # Кнопка расчета
        self.calculate_payment_button = QPushButton("Рассчитать сумму")
        self.calculate_payment_button.clicked.connect(self.calculate_payment)
        self.payment_layout.addWidget(self.calculate_payment_button)
        
        # Результаты
        self.payment_result = QTextEdit()
        self.payment_result.setReadOnly(True)
        self.payment_layout.addWidget(self.payment_result)
        
        # Кнопка для формирования сообщения
        self.generate_message_button = QPushButton("Сформировать сообщение родителю")
        self.generate_message_button.clicked.connect(self.generate_parent_message)
        self.generate_message_button.setEnabled(False)  # Изначально кнопка неактивна
        self.payment_layout.addWidget(self.generate_message_button)
        
        self.payment_tab.setLayout(self.payment_layout)
        self.tabs.addTab(self.payment_tab, "Расчет платежей")
    
    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть CSV файл", "", "CSV Files (*.csv)")
        if file_path:
            try:
                df = pd.read_csv(file_path)
                self.csv_text.append(f"Загружен файл: {file_path}")
                self.csv_text.append(f"Найдено {len(df)} записей")
                
                save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить Excel файл", "", "Excel Files (*.xlsx)")
                if save_path:
                    df.to_excel(save_path, index=False)
                    self.csv_text.append(f"Файл успешно сохранен как: {save_path}")
            except Exception as e:
                self.csv_text.append(f"Ошибка: {str(e)}")
    
    def load_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть JSON файл", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.teachers_data = data.get('teachers', [])
                self.csv_text.append(f"Загружен JSON файл: {file_path}")
            except Exception as e:
                self.csv_text.append(f"Ошибка загрузки JSON: {str(e)}")
    
    def load_full_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть JSON файл", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.teachers_data = data.get('teachers', [])
                    self.students_data = data.get('students', [])
                    self.directions_data = data.get('directions', [])
                    self.parents_data = data.get('parents', [])
                
                # Заполняем список учеников
                self.student_combo.clear()
                for student in self.students_data:
                    self.student_combo.addItem(student['name'], student['id'])
                
                self.payment_result.append("Данные успешно загружены")
            except Exception as e:
                self.payment_result.append(f"Ошибка загрузки JSON: {str(e)}")
    
    def load_payments(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть CSV с платежами", "", "CSV Files (*.csv)")
        if file_path:
            try:
                self.payments_data = pd.read_csv(file_path)
                self.csv_text.append(f"Загружен CSV файл с платежами: {file_path}")
                self.csv_text.append(f"Найдено {len(self.payments_data)} платежей")
            except Exception as e:
                self.csv_text.append(f"Ошибка загрузки CSV: {str(e)}")
    
    def calculate_salary(self):
        if not self.teachers_data or self.payments_data is None or self.payments_data.empty:
            self.csv_text.append("Ошибка: Не загружены все необходимые файлы")
            return
        
        try:
            # Создаем словарь направление -> преподаватели
            direction_to_teachers = {}
            for teacher in self.teachers_data:
                for direction in teacher['directions']:
                    if direction not in direction_to_teachers:
                        direction_to_teachers[direction] = []
                    direction_to_teachers[direction].append(teacher['name'])
            
            # Создаем словарь для хранения зарплаты
            teacher_salary = {}
            
            # Обрабатываем платежи
            for _, row in self.payments_data.iterrows():
                direction = row['direction']
                amount = float(row['amount'])
                
                if direction in direction_to_teachers:
                    for teacher in direction_to_teachers[direction]:
                        if teacher not in teacher_salary:
                            teacher_salary[teacher] = 0.0
                        teacher_salary[teacher] += amount
            
            # Формируем результаты
            self.salary_results = []
            for teacher, total in teacher_salary.items():
                salary = total * 0.3
                self.salary_results.append({
                    'Преподаватель': teacher,
                    'Общая сумма по направлениям': round(total, 2),
                    'Зарплата (30%)': round(salary, 2)
                })
            
            # Сортируем по убыванию зарплаты
            self.salary_results.sort(key=lambda x: x['Зарплата (30%)'], reverse=True)
            
            # Отображаем результаты
            self.show_results(self.salary_results)
            self.export_button.setEnabled(True)
            self.csv_text.append("Расчет зарплаты выполнен успешно")
            
        except Exception as e:
            self.csv_text.append(f"Ошибка расчета зарплаты: {str(e)}")
    
    def export_salary(self):
        if not self.salary_results:
            return
        
        try:
            df = pd.DataFrame(self.salary_results)
            save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет по зарплате", "", "Excel Files (*.xlsx)")
            if save_path:
                df.to_excel(save_path, index=False)
                self.csv_text.append(f"Отчет по зарплате сохранен как: {save_path}")
        except Exception as e:
            self.csv_text.append(f"Ошибка экспорта: {str(e)}")
    
    def update_student_directions(self):
        if not self.students_data or not self.directions_data:
            return
        
        student_id = self.student_combo.currentData()
        student = next((s for s in self.students_data if s['id'] == student_id), None)
        
        if not student:
            return
        
        self.directions_table.setRowCount(0)
        
        for direction_name in student['directions']:
            direction = next((d for d in self.directions_data if d['name'] == direction_name), None)
            if direction:
                row = self.directions_table.rowCount()
                self.directions_table.insertRow(row)
                
                # Направление
                self.directions_table.setItem(row, 0, QTableWidgetItem(direction_name))
                
                # Цены (абонемент и разовое)
                self.directions_table.setItem(row, 1, QTableWidgetItem(str(direction['cost'])))
                self.directions_table.setItem(row, 2, QTableWidgetItem(str(direction['trial_cost'])))
                
                # Радиокнопки для выбора типа оплаты
                payment_group = QButtonGroup(self) # Используем 'self' как родительский объект
                
                subscription_rb = QRadioButton("Абонемент")
                single_rb = QRadioButton("Разовое")
                none_rb = QRadioButton("Не выбрано")
                none_rb.setChecked(True)
                
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.addWidget(subscription_rb)
                layout.addWidget(single_rb)
                layout.addWidget(none_rb)
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                
                # Добавляем радиокнопки в группу
                payment_group.addButton(subscription_rb)
                payment_group.addButton(single_rb)
                payment_group.addButton(none_rb)
                
                self.directions_table.setCellWidget(row, 3, widget)
    
    def calculate_payment(self):
        if self.directions_table.rowCount() == 0:
            self.generate_message_button.setEnabled(False)
            return
        
        total = 0
        payment_details = []
        
        for row in range(self.directions_table.rowCount()):
            direction = self.directions_table.item(row, 0).text()
            widget = self.directions_table.cellWidget(row, 3)
            
            # Проверяем выбранный тип оплаты
            # Находим активную радиокнопку в группе
            layout = widget.layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), QRadioButton):
                        radio_button = item.widget()
                        if radio_button.isChecked():
                            if radio_button.text() == "Абонемент":
                                try:
                                    amount = float(self.directions_table.item(row, 1).text())
                                    total += amount
                                    payment_details.append(f" - {direction}: абонемент - {amount} руб.")
                                except (ValueError, TypeError):
                                    pass # Игнорируем ошибки, если цена не число
                            elif radio_button.text() == "Разовое":
                                try:
                                    amount = float(self.directions_table.item(row, 2).text())
                                    total += amount
                                    payment_details.append(f" - {direction}: разовое - {amount} руб.")
                                except (ValueError, TypeError):
                                    pass # Игнорируем ошибки, если цена не число
                            break
        
        self.payment_result.clear()
        if payment_details:
            self.payment_result.append("Детали платежа:\n")
            self.payment_result.append("\n".join(payment_details))
            self.payment_result.append(f"\nИтого к оплате: {total} руб.")
            self.generate_message_button.setEnabled(True)
        else:
            self.payment_result.append("Не выбрано ни одного направления для оплаты.")
            self.generate_message_button.setEnabled(False)

    def generate_parent_message(self):
        """
        Генерирует сообщение и отображает его в кастомном модальном окне.
        """
        student_id = self.student_combo.currentData()
        student = next((s for s in self.students_data if s['id'] == student_id), None)
        
        if not student or not self.parents_data:
            QMessageBox.warning(self, "Ошибка", "Ученик или данные родителей не загружены.")
            return
        
        parent = next((p for p in self.parents_data if p['id'] == student.get('parent_id')), None)
        
        if not parent:
            QMessageBox.warning(self, "Ошибка", "Родитель не найден для выбранного ученика.")
            return
        
        message = f"""Здравствуйте, {parent['name'].title()}!

Напоминаем о необходимости оплаты занятий для {student['name']} на следующий месяц:

{self.payment_result.toPlainText()}

Просим произвести оплату до конца текущего месяца.
С уважением, администрация образовательного центра.
"""
        # Отображаем сообщение в кастомном диалоге, чтобы можно было его скопировать
        dialog = ParentMessageDialog(message, self)
        dialog.exec_()
    
    def show_results(self, results):
        self.result_table.setRowCount(len(results))
        
        for row_idx, result in enumerate(results):
            self.result_table.setItem(row_idx, 0, QTableWidgetItem(result['Преподаватель']))
            self.result_table.setItem(row_idx, 1, QTableWidgetItem(f"{result['Общая сумма по направлениям']:.2f}"))
            self.result_table.setItem(row_idx, 2, QTableWidgetItem(f"{result['Зарплата (30%)']:.2f}"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EducationCenterApp()
    window.show()
    sys.exit(app.exec_())