import sqlite3
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


class HourlyStorage:
    """Persists count events and aggregates into hour buckets for Excel export."""

    def __init__(self, db_path="counts.db"):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hourly_counts (
                    hour_bucket TEXT PRIMARY KEY,
                    count INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL
                )
            """)

    def increment(self, n=1):
        now = datetime.now()
        bucket = now.strftime("%Y-%m-%d %H:00")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO hourly_counts (hour_bucket, count) VALUES (?, ?)
                   ON CONFLICT(hour_bucket) DO UPDATE SET count = count + ?""",
                (bucket, n, n),
            )
            conn.executemany(
                "INSERT INTO events (ts) VALUES (?)",
                [(now.isoformat(),)] * n,
            )

    def get_current_hour_count(self):
        bucket = datetime.now().strftime("%Y-%m-%d %H:00")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT count FROM hourly_counts WHERE hour_bucket = ?",
                (bucket,),
            ).fetchone()
        return row[0] if row else 0

    def get_total(self):
        with self._connect() as conn:
            row = conn.execute("SELECT SUM(count) FROM hourly_counts").fetchone()
        return row[0] or 0

    def get_all_hourly(self):
        with self._connect() as conn:
            return conn.execute(
                "SELECT hour_bucket, count FROM hourly_counts ORDER BY hour_bucket"
            ).fetchall()

    def reset(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM hourly_counts")
            conn.execute("DELETE FROM events")

    def export_excel(self, path):
        rows = self.get_all_hourly()
        wb = Workbook()

        ws = wb.active
        ws.title = "Hourly Counts"
        self._write_hourly_sheet(ws, rows)

        ws2 = wb.create_sheet("Daily Summary")
        self._write_daily_sheet(ws2, rows)

        wb.save(path)

    @staticmethod
    def _header(cell):
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2B7FFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    def _write_hourly_sheet(self, ws, rows):
        headers = ["Date", "Hour", "Count"]
        for col, h in enumerate(headers, 1):
            self._header(ws.cell(row=1, column=col, value=h))

        total = 0
        for i, (bucket, count) in enumerate(rows, 2):
            date_part, hour_part = bucket.split(" ")
            ws.cell(row=i, column=1, value=date_part)
            ws.cell(row=i, column=2, value=hour_part)
            ws.cell(row=i, column=3, value=count)
            total += count

        total_row = max(2, len(rows) + 2)
        tc1 = ws.cell(row=total_row, column=1, value="TOTAL")
        tc1.font = Font(bold=True)
        tc1.fill = PatternFill("solid", fgColor="EEF2F7")
        ws.cell(row=total_row, column=2).fill = PatternFill("solid", fgColor="EEF2F7")
        tc3 = ws.cell(row=total_row, column=3, value=total)
        tc3.font = Font(bold=True)
        tc3.fill = PatternFill("solid", fgColor="EEF2F7")

        for col, width in enumerate([14, 10, 12], 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.freeze_panes = "A2"

    def _write_daily_sheet(self, ws, rows):
        headers = ["Date", "Total Count"]
        for col, h in enumerate(headers, 1):
            self._header(ws.cell(row=1, column=col, value=h))

        daily = {}
        for bucket, count in rows:
            date_part = bucket.split(" ")[0]
            daily[date_part] = daily.get(date_part, 0) + count

        for i, (date_part, count) in enumerate(sorted(daily.items()), 2):
            ws.cell(row=i, column=1, value=date_part)
            ws.cell(row=i, column=2, value=count)

        for col, width in enumerate([14, 14], 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.freeze_panes = "A2"
