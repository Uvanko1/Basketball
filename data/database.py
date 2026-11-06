import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from Project.config import DB_PATH, THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class UserSettings:
    threshold1: int
    threshold2: int
    threshold3: int
    alpha_freq_left: float
    alpha_freq_right: float
    emg: float

    def as_tuple(self):
        return (
            self.threshold1,
            self.threshold2,
            self.threshold3,
            self.alpha_freq_left,
            self.alpha_freq_right,
            self.emg,
        )


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self) -> None:
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                threshold1 INTEGER,
                threshold2 INTEGER,
                threshold3 INTEGER,
                alpha_freq_left REAL,
                alpha_freq_right REAL,
                emg INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                score INTEGER,
                edf_path TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        self.conn.commit()

    def get_user(self, last_name: str, first_name: str, middle_name: str) -> Optional[int]:
        self.cursor.execute(
            """
            SELECT id FROM users
            WHERE last_name=? AND first_name=? AND middle_name=?
            """,
            (last_name, first_name, middle_name),
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def create_user(self, last_name: str, first_name: str, middle_name: str) -> int:
        created_at = datetime.now().isoformat()
        self.cursor.execute(
            """
            INSERT INTO users (last_name, first_name, middle_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (last_name, first_name, middle_name, created_at),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def create_default_settings(self, user_id: int) -> None:
        self.cursor.execute(
            """
            INSERT INTO settings (user_id, threshold1, threshold2, threshold3, alpha_freq_left, alpha_freq_right, emg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                THRESHOLDS.threshold1_percent,
                THRESHOLDS.threshold2_percent,
                THRESHOLDS.threshold3_percent,
                THRESHOLDS.alpha_low_hz,
                THRESHOLDS.alpha_high_hz,
                THRESHOLDS.emg_threshold_uv,
            ),
        )
        self.conn.commit()

    def load_settings(self, user_id: int) -> Optional[UserSettings]:
        self.cursor.execute(
            """
            SELECT threshold1, threshold2, threshold3, alpha_freq_left, alpha_freq_right, emg
            FROM settings WHERE user_id=?
            """,
            (user_id,),
        )
        row = self.cursor.fetchone()
        return UserSettings(*row) if row else None

    def update_settings(
        self,
        user_id: int,
        threshold1: int,
        threshold2: int,
        threshold3: int,
        alpha_freq_left: float,
        alpha_freq_right: float,
        emg: float,
    ) -> None:
        self.cursor.execute(
            """
            UPDATE settings
            SET threshold1=?, threshold2=?, threshold3=?, alpha_freq_left=?, alpha_freq_right=?, emg=?
            WHERE user_id=?
            """,
            (threshold1, threshold2, threshold3, alpha_freq_left, alpha_freq_right, emg, user_id),
        )
        self.conn.commit()
        logger.debug("Настройки пользователя %s обновлены", user_id)

    def save_session(self, user_id: int, score: int, edf_path: str) -> None:
        date = datetime.now().isoformat()
        self.cursor.execute(
            """
            INSERT INTO sessions (user_id, date, score, edf_path)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, date, score, edf_path),
        )
        self.conn.commit()
        logger.debug("Сессия пользователя %s сохранена: %s (счёт=%s)", user_id, edf_path, score)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
