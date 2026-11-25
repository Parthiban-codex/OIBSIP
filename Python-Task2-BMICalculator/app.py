"""
BMI Calculator - Advanced Tier
GUI (tkinter) + multi-user records (SQLite) + BMI trend graph (matplotlib)

Install:  py -m pip install matplotlib
(tkinter and sqlite3 come built-in with Python)
"""

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

DB_FILE = "bmi_data.db"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

CATEGORY_COLORS = {
    "Underweight": "#1E88E5",   # blue
    "Normal": "#2E9E4F",        # green
    "Overweight": "#F59E0B",    # orange
    "Obese": "#D32F2F",         # red
}


# ---------------------------------------------------------------- logic
def calculate_bmi(weight, height):
    return weight / (height ** 2)


def classify(bmi):
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    return "Obese"


def validate_inputs(weight_text, height_text):
    """Return (weight, height) as floats or raise ValueError with a helpful message."""
    try:
        weight = float(weight_text.strip())
        height = float(height_text.strip())
    except ValueError:
        raise ValueError("Please enter numbers only.\nExample: weight 68, height 1.72")
    if weight <= 0 or height <= 0:
        raise ValueError("Weight and height cannot be zero or negative.")
    if height > 3:
        raise ValueError("Height must be in METERS.\nExample: 1.75 (not 175).")
    if weight > 500:
        raise ValueError("Weight looks too large. Enter it in kilograms.")
    return weight, height


# ------------------------------------------------------------- database
def db_execute(query, params=(), fetch=False):
    """Run one SQL query. Raises sqlite3.Error on failure (caught by the GUI)."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute(query, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


def init_db():
    db_execute("""
        CREATE TABLE IF NOT EXISTS records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            weight      REAL NOT NULL,
            height      REAL NOT NULL,
            bmi         REAL NOT NULL,
            category    TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
    """)


# ------------------------------------------------------------------ GUI
class BMIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BMI Calculator")
        self.geometry("640x600")
        self.resizable(False, False)

        self.last_result = None   # (weight, height, bmi, category)
        self.build_ui()

        try:
            init_db()
            self.refresh_users()
            self.refresh_history()
        except sqlite3.Error as e:
            messagebox.showerror("Database error", f"Could not open the database:\n{e}")

    # ---------- layout
    def build_ui(self):
        ttk.Label(self, text="BMI Calculator", font=("Segoe UI", 18, "bold")).pack(pady=(14, 6))

        form = ttk.Frame(self, padding=10)
        form.pack()

        ttk.Label(form, text="User name:").grid(row=0, column=0, sticky="e", padx=6, pady=5)
        self.name_box = ttk.Combobox(form, width=24)       # type a new name or pick existing
        self.name_box.grid(row=0, column=1, pady=5)
        self.name_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())

        ttk.Label(form, text="Weight (kg):").grid(row=1, column=0, sticky="e", padx=6, pady=5)
        self.weight_entry = ttk.Entry(form, width=27)
        self.weight_entry.grid(row=1, column=1, pady=5)

        ttk.Label(form, text="Height (m):").grid(row=2, column=0, sticky="e", padx=6, pady=5)
        self.height_entry = ttk.Entry(form, width=27)
        self.height_entry.grid(row=2, column=1, pady=5)

        buttons = ttk.Frame(self)
        buttons.pack(pady=8)
        ttk.Button(buttons, text="Calculate", command=self.calculate).grid(row=0, column=0, padx=5)
        ttk.Button(buttons, text="Save Record", command=self.save_record).grid(row=0, column=1, padx=5)
        ttk.Button(buttons, text="Show Trend Graph", command=self.show_graph).grid(row=0, column=2, padx=5)

        self.result_label = tk.Label(self, text="Enter your details and press Calculate",
                                     font=("Segoe UI", 14, "bold"), width=34, height=2,
                                     bg="#E5E7EB", fg="#374151")
        self.result_label.pack(pady=8)

        ttk.Label(self, text="History (selected user)", font=("Segoe UI", 11, "bold")).pack()
        cols = ("Date", "Weight", "Height", "BMI", "Category")
        self.table = ttk.Treeview(self, columns=cols, show="headings", height=9)
        for c, w in zip(cols, (150, 80, 80, 80, 110)):
            self.table.heading(c, text=c)
            self.table.column(c, width=w, anchor="center")
        self.table.pack(padx=14, pady=6)

    # ---------- actions
    def calculate(self):
        """Validate input, compute BMI, show colour-coded result. Returns True on success."""
        try:
            weight, height = validate_inputs(self.weight_entry.get(), self.height_entry.get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return False

        bmi = round(calculate_bmi(weight, height), 2)
        category = classify(bmi)
        self.last_result = (weight, height, bmi, category)
        self.result_label.config(text=f"BMI: {bmi:.2f}  -  {category}",
                                 bg=CATEGORY_COLORS[category], fg="white")
        return True

    def save_record(self):
        name = self.name_box.get().strip()
        if not name:
            messagebox.showwarning("Name needed", "Please enter a user name to save the record.")
            return
        if not self.calculate():
            return
        weight, height, bmi, category = self.last_result
        try:
            db_execute(
                "INSERT INTO records (username, weight, height, bmi, category, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, weight, height, bmi, category, datetime.now().strftime(DATE_FMT)),
            )
        except sqlite3.Error as e:
            messagebox.showerror("Database error", f"Could not save the record:\n{e}")
            return
        messagebox.showinfo("Saved", f"Record saved for {name}.")
        self.refresh_users()
        self.refresh_history()

    def refresh_users(self):
        try:
            rows = db_execute("SELECT DISTINCT username FROM records ORDER BY username", fetch=True)
        except sqlite3.Error as e:
            messagebox.showerror("Database error", f"Could not read users:\n{e}")
            return
        self.name_box["values"] = [r[0] for r in rows]

    def refresh_history(self):
        for item in self.table.get_children():
            self.table.delete(item)
        name = self.name_box.get().strip()
        if not name:
            return
        try:
            rows = db_execute(
                "SELECT recorded_at, weight, height, bmi, category FROM records "
                "WHERE username = ? ORDER BY recorded_at DESC LIMIT 50", (name,), fetch=True)
        except sqlite3.Error as e:
            messagebox.showerror("Database error", f"Could not read history:\n{e}")
            return
        for r in rows:
            self.table.insert("", "end", values=(r[0], r[1], r[2], f"{r[3]:.2f}", r[4]))

    def show_graph(self):
        name = self.name_box.get().strip()
        if not name:
            messagebox.showwarning("Name needed", "Select or type a user name first.")
            return
        try:
            rows = db_execute(
                "SELECT recorded_at, bmi FROM records WHERE username = ? ORDER BY recorded_at",
                (name,), fetch=True)
        except sqlite3.Error as e:
            messagebox.showerror("Database error", f"Could not read records:\n{e}")
            return
        if not rows:
            messagebox.showinfo("No data", f"No saved records for {name} yet.")
            return

        dates = [datetime.strptime(r[0], DATE_FMT) for r in rows]
        values = [r[1] for r in rows]

        win = tk.Toplevel(self)
        win.title(f"BMI Trend - {name}")

        fig = Figure(figsize=(7, 4), dpi=100)
        ax = fig.add_subplot(111)
        # coloured health bands in the background
        ax.axhspan(0, 18.5, color=CATEGORY_COLORS["Underweight"], alpha=0.12)
        ax.axhspan(18.5, 25, color=CATEGORY_COLORS["Normal"], alpha=0.12)
        ax.axhspan(25, 30, color=CATEGORY_COLORS["Overweight"], alpha=0.12)
        ax.axhspan(30, 60, color=CATEGORY_COLORS["Obese"], alpha=0.12)

        ax.plot(dates, values, marker="o", linewidth=2, color="#1F3A5F")
        ax.set_ylim(min(values + [17]) - 1, max(values + [31]) + 1)
        ax.set_title(f"BMI trend for {name}")
        ax.set_xlabel("Date")
        ax.set_ylabel("BMI")
        ax.grid(alpha=0.3)
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    BMIApp().mainloop()

