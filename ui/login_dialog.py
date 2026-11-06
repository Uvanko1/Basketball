from PyQt5 import QtWidgets

from Project.data.database import DatabaseManager


class UserLoginDialog(QtWidgets.QDialog):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.user_id: int | None = None
        self.user_fio: str | None = None

        self.setWindowTitle("Выбор пользователя")
        self.setMinimumWidth(360)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Кто тренируется?")
        title.setObjectName("title")
        hint = QtWidgets.QLabel("Если вы здесь впервые, профиль создастся автоматически.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        self.last_name = QtWidgets.QLineEdit()
        self.last_name.setPlaceholderText("Фамилия")

        self.first_name = QtWidgets.QLineEdit()
        self.first_name.setPlaceholderText("Имя")

        self.middle_name = QtWidgets.QLineEdit()
        self.middle_name.setPlaceholderText("Отчество")

        self.button = QtWidgets.QPushButton("Продолжить")
        self.button.setObjectName("primary")
        self.button.setDefault(True)
        for field in (self.last_name, self.first_name, self.middle_name):
            field.returnPressed.connect(self.on_continue)
        self.button.clicked.connect(self.on_continue)

        for widget in (self.last_name, self.first_name, self.middle_name, self.button):
            layout.addWidget(widget)

        self.setLayout(layout)

    def on_continue(self) -> None:
        last = self.last_name.text().strip()
        first = self.first_name.text().strip()
        middle = self.middle_name.text().strip()

        if not last or not first:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Введите фамилию и имя")
            return

        self.user_fio = f"{last} {first} {middle}".strip()

        user_id = self.db.get_user(last, first, middle)
        if user_id is not None:
            self.user_id = user_id
        else:
            self.user_id = self.db.create_user(last, first, middle)
            self.db.create_default_settings(self.user_id)

        self.accept()
