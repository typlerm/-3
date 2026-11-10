"""Лабораторна робота №3 — обробка виключень, модульність, документування.

Весь проєкт в одному файлі. Структура пакета student_app
(exceptions, services, utils) імітується через types.ModuleType
і sys.modules, тому працюють `import student_app.exceptions`,
`from student_app.services import parse_grade` та `__all__`.

Запуск: python lb3.py  (у Visual Studio краще Ctrl+F5).
"""

import datetime
import os
import sys
import tempfile
import types
from typing import Iterator, Union

# =====================================================================
# 0. ІМІТАЦІЯ ПАКЕТІВ
# =====================================================================


def _make_pkg(name: str) -> types.ModuleType:
    """Створює порожній пакет і реєструє його в sys.modules."""
    pkg = types.ModuleType(name)
    pkg.__path__ = []  # ознака пакета
    sys.modules[name] = pkg
    return pkg


app_pkg = _make_pkg("student_app")
exc_pkg = _make_pkg("student_app.exceptions")
utils_pkg = _make_pkg("student_app.utils")
serv_pkg = _make_pkg("student_app.services")
app_pkg.exceptions, app_pkg.utils, app_pkg.services = exc_pkg, utils_pkg, serv_pkg


# =====================================================================
# 1. student_app.exceptions — ієрархія виключень
# =====================================================================
class StudentAppError(Exception):
    """Базовий клас усіх доменних помилок застосунку.

    Attributes:
        code: Числовий код помилки.
        message: Текст повідомлення.
    """

    def __init__(self, message: str, code: int = 1000) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(StudentAppError):
    """Помилка валідації даних.

    Attributes:
        field: Ім'я поля, яке не пройшло перевірку.
    """

    def __init__(self, message: str, field: str, code: int = 1001) -> None:
        super().__init__(message, code)
        self.field = field

    def __str__(self) -> str:
        return f"[{self.code}] Поле '{self.field}': {self.message}"


class NotFoundError(StudentAppError):
    """Ресурс не знайдено.

    Attributes:
        resource_id: Ідентифікатор відсутнього ресурсу.
    """

    def __init__(self, message: str, resource_id: str, code: int = 1002) -> None:
        super().__init__(message, code)
        self.resource_id = resource_id

    def __str__(self) -> str:
        return f"[{self.code}] Ресурс '{self.resource_id}': {self.message}"


class StorageError(StudentAppError):
    """Помилка доступу до сховища (файлу).

    Attributes:
        path: Шлях, де сталася помилка.
    """

    def __init__(self, message: str, path: str, code: int = 1003) -> None:
        super().__init__(message, code)
        self.path = path

    def __str__(self) -> str:
        return f"[{self.code}] Сховище '{self.path}': {self.message}"


for _cls in (StudentAppError, ValidationError, NotFoundError, StorageError):
    _cls.__module__ = "student_app.exceptions"
    setattr(exc_pkg, _cls.__name__, _cls)
exc_pkg.__all__ = ["StudentAppError", "ValidationError", "NotFoundError", "StorageError"]


# =====================================================================
# 2. student_app.utils — логер
# =====================================================================
def log(level: str, message: str) -> None:
    """Виводить повідомлення з часовою міткою.

    Args:
        level: Рівень ('INFO', 'WARN', 'ERROR').
        message: Текст повідомлення.
    """
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level:<5} | {message}")


utils_pkg.log = log
utils_pkg.__all__ = ["log"]


# =====================================================================
# 3. student_app.services — валідація та файли
# =====================================================================
Numeric = Union[int, float]


def parse_grade(raw: str) -> int:
    """Перетворює рядок на оцінку 0–100.

    Args:
        raw: Рядок із цілим числом.

    Returns:
        Оцінка як int.

    Raises:
        ValidationError: Якщо це не число або воно поза діапазоном 0–100.
    """
    try:
        grade = int(raw)
    except (ValueError, TypeError) as exc:
        # Ланцюжок: низькорівнева помилка → доменна, причина зберігається
        raise ValidationError(f"некоректна оцінка: {raw!r}", field="grade") from exc
    if not 0 <= grade <= 100:
        raise ValidationError(f"оцінка {grade} поза діапазоном 0–100", field="grade")
    return grade


def validate_student(name: str, raw_grade: str) -> dict:
    """Перевіряє пару (ім'я, оцінка).

    Args:
        name: Ім'я студента.
        raw_grade: Оцінка рядком.

    Returns:
        Словник {'name': str, 'grade': int}.

    Raises:
        ValidationError: Якщо ім'я порожнє або оцінка некоректна.
    """
    if not name or not name.strip():
        raise ValidationError("ім'я не може бути порожнім", field="name")
    return {"name": name.strip(), "grade": parse_grade(raw_grade)}


def read_students(path: str) -> Iterator[dict]:
    """Читає файл із рядками 'ім'я,оцінка'; погані рядки пропускає з WARN.

    Args:
        path: Шлях до файлу.

    Yields:
        Словники {'name': str, 'grade': int}.

    Raises:
        StorageError: Якщо файл не знайдено або немає прав на читання.
    """
    try:
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    name, raw_grade = line.split(",")
                    yield validate_student(name, raw_grade)
                except (ValueError, ValidationError) as exc:
                    # ValueError — неправильна кількість полів у рядку
                    log("WARN", f"рядок {line_no} пропущено: {exc}")
    except FileNotFoundError as exc:
        raise StorageError(f"файл не знайдено: {path}", path=path) from exc
    except PermissionError as exc:
        raise StorageError(f"немає прав на читання: {path}", path=path) from exc


def write_report(path: str, students: list) -> None:
    """Записує студентів у файл.

    Args:
        path: Вихідний файл.
        students: Список словників {'name', 'grade'}.

    Raises:
        StorageError: Якщо записати файл не вдалося.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            for s in students:
                f.write(f"{s['name']},{s['grade']}\n")
    except OSError as exc:
        raise StorageError(f"не вдалося записати {path}", path=path) from exc


def find_student(students: list, name: str) -> dict:
    """Шукає студента за ім'ям.

    Args:
        students: Список словників {'name', 'grade'}.
        name: Ім'я для пошуку.

    Returns:
        Знайдений словник.

    Raises:
        NotFoundError: Якщо студента немає в списку.
    """
    for s in students:
        if s["name"] == name:
            return s
    raise NotFoundError("студента не знайдено", resource_id=name)


for _fn in (parse_grade, validate_student, read_students, write_report, find_student):
    _fn.__module__ = "student_app.services"
    setattr(serv_pkg, _fn.__name__, _fn)
serv_pkg.__all__ = [
    "parse_grade", "validate_student", "read_students", "write_report", "find_student",
]
log.__module__ = "student_app.utils"

app_pkg.__all__ = exc_pkg.__all__ + serv_pkg.__all__
for _name in app_pkg.__all__:
    setattr(app_pkg, _name, getattr(exc_pkg, _name, None) or getattr(serv_pkg, _name))


# =====================================================================
# 4. student_app.cli — демонстрація
# =====================================================================
def demo_exceptions() -> None:
    """Сценарії 1–3: різні форми try/except."""
    print("\n--- 1. Базовий try/except ---")
    try:
        parse_grade("abc")
    except StudentAppError as exc:
        print(f"Перехоплено доменну помилку: {exc}")
        print(f"  причина (__cause__): {exc.__cause__!r}")

    print("\n--- 2. try/except/else/finally ---")
    try:
        grade = parse_grade("75")
    except StudentAppError as exc:
        print(f"Помилка: {exc}")
    else:
        print(f"Успіх! Оцінка: {grade}")
    finally:
        print("(finally: виконується завжди)")

    print("\n--- 3. Кілька типів виключень в одному except ---")
    for raw in ("abc", "150", None, "42"):
        try:
            print(f"  {raw!r} → {parse_grade(raw)}")
        except (ValidationError, NotFoundError) as exc:
            print(f"  {raw!r} → {type(exc).__name__}: {exc}")

    print("\n--- 3б. Перехоплення всієї категорії через базовий клас ---")
    students = [{"name": "Олена", "grade": 95}]
    for name in ("Олена", "Богдан"):
        try:
            print(f"  знайдено: {find_student(students, name)}")
        except StudentAppError as exc:
            print(f"  {type(exc).__name__}: {exc}")


def demo_files(tmp_dir: str) -> None:
    """Сценарій 4: файли та контекстний менеджер."""
    print("\n--- 4. Читання файлу (контекстний менеджер) ---")
    good = os.path.join(tmp_dir, "data.txt")
    with open(good, "w", encoding="utf-8") as f:
        f.write("Олена,95\nІван,78\nМарія,92\nПетро,abc\nАнна,88\n")

    missing = os.path.join(tmp_dir, "missing.txt")
    for path in (good, missing):
        try:
            students = list(read_students(path))
            print(f"  {os.path.basename(path)}: {len(students)} записів")
        except StorageError as exc:
            log("ERROR", str(exc))
            print(f"  причина (__cause__): {type(exc.__cause__).__name__}")

    out = os.path.join(tmp_dir, "report.txt")
    write_report(out, list(read_students(good)))
    with open(out, encoding="utf-8") as f:
        print(f"  report.txt записано, рядків: {len(f.readlines())}")


def demo_reraise() -> None:
    """Сценарій 5: повторне піднесення виключення."""
    print("\n--- 5. Повторне піднесення (raise без аргументів) ---")
    try:
        try:
            parse_grade("999")
        except StudentAppError:
            log("WARN", "Перехоплено, зараз буде re-raise")
            raise
    except StudentAppError as exc:
        log("ERROR", f"Фінальне перехоплення: {exc}")


def demo_introspection() -> None:
    """Сценарій 6: __all__, __doc__, __annotations__, імпорти."""
    print("\n--- 6. Модулі, __all__, документація ---")
    from student_app.exceptions import ValidationError as VE
    from student_app.services import parse_grade as pg

    print("  exceptions.__all__:", exc_pkg.__all__)
    print("  services.__all__:  ", serv_pkg.__all__)
    print("  VE is ValidationError:", VE is ValidationError)
    print("  parse_grade.__module__:", pg.__module__)
    print("  parse_grade.__annotations__:", pg.__annotations__)
    print("  parse_grade.__doc__ (перший рядок):", pg.__doc__.strip().splitlines()[0])
    print("  MRO ValidationError:", [c.__name__ for c in ValidationError.__mro__])

    ns: dict = {}
    exec("from student_app.exceptions import *", ns)
    print("  import * дав:", sorted(k for k in ns if not k.startswith("__")))


def run() -> None:
    """Запускає всю демонстрацію."""
    log("INFO", "Старт Student App")
    demo_exceptions()
    with tempfile.TemporaryDirectory() as tmp:
        demo_files(tmp)
    demo_reraise()
    demo_introspection()
    log("INFO", "Завершення Student App")


if __name__ == "__main__":
    run()