import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from datetime import datetime, date
import sqlite3
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from tkcalendar import DateEntry
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import requests
import json
from dotenv import load_dotenv
import os
from groq import Groq  # sesuai instruksi

WA_API_URL = "https://wa.zulzario.my.id/api/whatsapp"
WA_API_DOC_URL = "https://wa.zulzario.my.id/api/whatsapp/document"
APP_TITLE = "Aplikasi Manajemen Skripsi"
APP_GEOMETRY = "900x700"
APP_BG_COLOR = "#1e2a38"
WINDOW_GEOMETRY = "700x600"
WINDOW_BG_COLOR = "#1e2a38"
DB_NAME = "thesis_management.db"
PDF_HEADER_COLOR = "#2c3e50"
PDF_HEADER_TEXT_COLOR = colors.white
PDF_HEADER_TITLE = "Laporan Kinerja Skripsi"
PDF_HEADER_FONT = "Helvetica-Bold"
PDF_HEADER_FONT_SIZE = 22
PDF_HEADER_DATE_FONT = "Helvetica"
PDF_HEADER_DATE_FONT_SIZE = 12
PDF_HEADER_LINE_COLOR = "#2980b9"
PDF_SECTION_TITLE_COLOR = "#2980b9"
PDF_TABLE_HEADER_BG = "#ecf0f1"
PDF_TABLE_HEADER_TEXT = "#34495e"
PDF_TABLE_ROW_ALT_BG = "#f8f9fa"
PDF_TABLE_ROW_BG = colors.white
PDF_STATUS_DONE_COLOR = "#27ae60"
PDF_STATUS_NOT_DONE_COLOR = "#e74c3c"
PDF_FOOTER_LINE_COLOR = "#bdc3c7"
PDF_FOOTER_TEXT_COLOR = "#7f8c8d"
PDF_FOOTER_TEXT = "Aplikasi Manajemen Skripsi - Laporan Otomatis"
PDF_FOOTER_FONT = "Helvetica-Oblique"
PDF_FOOTER_FONT_SIZE = 9

# --- AI Groq Chat Constants ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def send_wa_notification(chapter_name, days_left, lewat=False):
    """
    Function to send WhatsApp notification for chapter deadline.
    """
    if lewat:
        message = f"Deadline bab '{chapter_name}' sudah lewat {abs(days_left)} hari!"
    elif days_left == 3:
        message = f"Reminder: 3 hari lagi deadline bab '{chapter_name}'."
    else:
        message = f"Reminder bab '{chapter_name}', sisa {days_left} hari."

    print(f"WA: {message}")

    payload = {
        "message": message
    }

    try:
        response = requests.post(WA_API_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print("Gagal mengirim notifikasi WA:", e)

def send_wa_pdf_notification(pdf_path):
    """
    Function to send WhatsApp notification with PDF document attachment.
    """
    message = "Berikut terlampir laporan PDF kinerja skripsi Anda."
    try:
        with open(pdf_path, "rb") as f:
            files = {
                "document": (pdf_path.split("/")[-1], f, "application/pdf")
            }
            data = {
                "message": message
            }
            # Assuming the API endpoint supports multipart/form-data for document upload
            response = requests.post(WA_API_DOC_URL, data=data, files=files)
            response.raise_for_status()
        print("WA: PDF report sent successfully.")
    except Exception as e:
        print("Gagal mengirim PDF ke WhatsApp:", e)

def send_wa_test_message():
    """
    Fungsi untuk mengirim pesan WhatsApp test.
    """
    test_message = "Ini adalah pesan test WhatsApp dari aplikasi manajemen skripsi."
    payload = {
        "message": test_message
    }
    try:
        response = requests.post(WA_API_URL, json=payload)
        response.raise_for_status()
        messagebox.showinfo("Sukses", "Pesan test WhatsApp berhasil dikirim.")
    except Exception as e:
        messagebox.showerror("Gagal", f"Gagal mengirim pesan test WhatsApp:\n{e}")

# Simpan history chat ke memory sementara
chat_history_memory = []

def ask_groq_ai(prompt):
    """
    Fungsi untuk mengirim prompt ke Groq AI dan mengembalikan respon.
    Menyimpan history chat ke memory sementara (chat_history_memory).
    """
    try:
        # Tambahkan prompt user ke history
        chat_history_memory.append({"role": "user", "content": prompt})

        # Siapkan pesan untuk dikirim ke Groq, gunakan seluruh history
        messages = [
            {
                "role": "system",
                "content": "okey."
            }
        ] + chat_history_memory[-10:]  # Kirim maksimal 10 pesan terakhir (bisa diubah sesuai kebutuhan)

        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages
        )
        # Ambil isi jawaban dari response Groq
        if hasattr(response, "choices") and response.choices:
            ai_reply = response.choices[0].message.content
            # Simpan jawaban AI ke history
            chat_history_memory.append({"role": "assistant", "content": ai_reply})
            return ai_reply
        else:
            return "Tidak ada jawaban dari AI."
    except Exception as e:
        return f"Terjadi error saat menghubungi AI: {e}"

class ThesisApp:

    def __init__(self, root):
        # Inisialisasi jendela utama
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(APP_GEOMETRY)
        self.root.configure(bg=APP_BG_COLOR)

        self.setup_style()  # Set tema dan gaya widget

        try:
            # Koneksi ke SQLite dan inisialisasi database
            self.conn = sqlite3.connect(DB_NAME)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.cursor = self.conn.cursor()
            self.create_tables()  # Membuat tabel jika belum ada
        except Exception as e:
            messagebox.showerror("Database Error", str(e))
            self.root.destroy()

        # Cek notifikasi bab (H-3 dan lewat deadline)
        self.check_chapter_deadlines()

        self.build_menu()  # Tampilkan menu utama

    def check_chapter_deadlines(self):
        # Ambil semua bab yang statusnya 'Belum Selesai'
        self.cursor.execute("SELECT chapter_name, target_date FROM chapters WHERE status = 'Belum Selesai'")
        chapters = self.cursor.fetchall()
        today = date.today()
        for bab in chapters:
            chapter_name, target_date_str = bab
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except Exception:
                continue  # skip jika format tanggal salah
            days_left = (target_date - today).days
            print(f"Bab: {chapter_name}, Target: {target_date}, Hari: {days_left}")
            if days_left == 3:
                send_wa_notification(chapter_name, 3)
            elif days_left < 0:
                send_wa_notification(chapter_name, days_left, lewat=True)

    def setup_style(self):
        # Mengatur tampilan dan warna widget
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", background="#3498db", foreground="white", font=("Arial", 10, "bold"))
        style.configure("TLabel", background=APP_BG_COLOR, foreground="white", font=("Arial", 10))
        style.configure("TLabelframe", background="#2c3e50", foreground="white", font=("Arial", 10, "bold"))
        style.configure("TLabelframe.Label", background="#2c3e50", foreground="white")

    def create_tables(self):
        # Membuat tabel-tabel database
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_name TEXT,
                target_date TEXT,
                status TEXT
            )
        """)
        # consultations dan revisions sekarang punya kolom chapter_id (FK)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                lecturer TEXT,
                chapter_id INTEGER,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notes TEXT,
                date TEXT,
                chapter_id INTEGER,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            )
        """)
        # Hapus tabel relasi N:M, tidak dipakai lagi
        self.cursor.execute("DROP TABLE IF EXISTS chapter_consultation")
        self.cursor.execute("DROP TABLE IF EXISTS chapter_revision")
        self.conn.commit()

        # Data dummy hanya akan diinsert jika tabel chapters masih kosong
        self.cursor.execute("SELECT COUNT(*) FROM chapters")
        if self.cursor.fetchone()[0] == 0:
            # Insert dummy chapters
            dummy_chapters = [
                ("Bab 1 Pendahuluan", "2024-06-20", "Belum Selesai"),
                ("Bab 2 Tinjauan Pustaka", "2024-06-25", "Belum Selesai"),
                ("Bab 3 Metodologi", "2024-07-01", "Belum Selesai"),
                ("Bab 4 Hasil dan Pembahasan", "2024-07-10", "Belum Selesai"),
                ("Bab 5 Kesimpulan", "2024-07-15", "Belum Selesai"),
            ]
            self.cursor.executemany(
                "INSERT INTO chapters (chapter_name, target_date, status) VALUES (?, ?, ?)",
                dummy_chapters
            )
            self.conn.commit()

            # Ambil id chapter untuk relasi dummy
            self.cursor.execute("SELECT id FROM chapters ORDER BY id")
            chapter_ids = [row[0] for row in self.cursor.fetchall()]

            # Insert dummy consultations
            dummy_consultations = [
                ("2024-06-10", "Dr. Budi", chapter_ids[0]),
                ("2024-06-15", "Dr. Sari", chapter_ids[1]),
                ("2024-06-22", "Dr. Budi", chapter_ids[2]),
                ("2024-06-28", "Dr. Sari", chapter_ids[3]),
            ]
            self.cursor.executemany(
                "INSERT INTO consultations (date, lecturer, chapter_id) VALUES (?, ?, ?)",
                dummy_consultations
            )

            # Insert dummy revisions
            dummy_revisions = [
                ("Perbaiki rumusan masalah.", "2024-06-12", chapter_ids[0]),
                ("Tambahkan referensi terbaru.", "2024-06-18", chapter_ids[1]),
                ("Lengkapi diagram alur.", "2024-06-24", chapter_ids[2]),
                ("Perjelas hasil pengujian.", "2024-07-05", chapter_ids[3]),
            ]
            self.cursor.executemany(
                "INSERT INTO revisions (notes, date, chapter_id) VALUES (?, ?, ?)",
                dummy_revisions
            )
            self.conn.commit()

    def build_menu(self):
        # Menampilkan tombol menu utama
        frame = tk.Frame(self.root, bg=APP_BG_COLOR)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        menu = [
            ("Target Bab", self.target_page),
            ("Jadwal Konsultasi", self.consult_page),
            ("Catatan Revisi", self.revision_page),
            ("Statistik Progress", self.statistic_page),
            ("Cetak Laporan PDF", self.print_pdf_report)  # Tambahkan tombol PDF
        ]

        for label, cmd in menu:
            tk.Button(frame, text=label, command=cmd, bg="#3498db", fg="white",
                      font=("Arial", 11, "bold"), relief="flat", width=25, height=2).pack(pady=10)

        # Tambahkan tombol untuk test message WA
        tk.Button(
            frame,
            text="Test Pesan WhatsApp",
            command=send_wa_test_message,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            relief="flat",
            width=25,
            height=2
        ).pack(pady=10)

        # Tambahkan tombol untuk Chat AI Groq
        tk.Button(
            frame,
            text="Chat dengan AI Groq",
            command=self.open_groq_chat_window,
            bg="#8e44ad",
            fg="white",
            font=("Arial", 11, "bold"),
            relief="flat",
            width=25,
            height=2
        ).pack(pady=10)

    def open_groq_chat_window(self):
        # Jendela chat dengan AI Groq (Tampilan Modern)
        import os
        import threading

        # Warna dan style modern
        PRIMARY_COLOR = "#6C63FF"
        SECONDARY_COLOR = "#F5F6FA"
        ACCENT_COLOR = "#00B894"
        TEXT_COLOR = "#222"
        ENTRY_BG = "#fff"
        BUTTON_BG = PRIMARY_COLOR
        BUTTON_FG = "#fff"
        LABEL_FG = "#555"
        BORDER_RADIUS = 10

        chat_win = tk.Toplevel(self.root)
        chat_win.title("Chat dengan AI Groq")
        chat_win.geometry("800x750")
        chat_win.configure(bg=SECONDARY_COLOR)

        # --- Header Modern ---
        header = tk.Frame(chat_win, bg=PRIMARY_COLOR, height=60)
        header.pack(fill="x")
        header_label = tk.Label(
            header, text="💬 Chat AI Groq Skripsi", bg=PRIMARY_COLOR, fg="white",
            font=("Segoe UI", 18, "bold"), pady=10
        )
        header_label.pack(side="left", padx=20)

        # --- Fitur Upload Skripsi ---
        upload_frame = tk.Frame(chat_win, bg=SECONDARY_COLOR)
        upload_frame.pack(fill="x", padx=20, pady=(18, 0))

        self.uploaded_skripsi_path = None
        self.uploaded_skripsi_text = None

        def extract_text_from_file(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            try:
                if ext == ".pdf":
                    try:
                        import PyPDF2
                    except ImportError:
                        messagebox.showerror("Error", "PyPDF2 belum terinstall. Install dengan 'pip install PyPDF2'")
                        return ""
                    text = ""
                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            text += page.extract_text() or ""
                    return text
                elif ext in [".doc", ".docx"]:
                    try:
                        import docx
                    except ImportError:
                        messagebox.showerror("Error", "python-docx belum terinstall. Install dengan 'pip install python-docx'")
                        return ""
                    doc = docx.Document(file_path)
                    return "\n".join([p.text for p in doc.paragraphs])
                else:
                    messagebox.showerror("Error", "Format file tidak didukung. Hanya PDF, DOC, DOCX.")
                    return ""
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membaca file: {e}")
                return ""

        def upload_skripsi():
            file_path = tk.filedialog.askopenfilename(
                title="Pilih file skripsi (PDF, DOC, DOCX)",
                filetypes=[("Dokumen Skripsi", "*.pdf *.doc *.docx")]
            )
            if file_path:
                chat_win.config(cursor="watch")
                chat_win.update()
                text = extract_text_from_file(file_path)
                chat_win.config(cursor="")
                if text:
                    self.uploaded_skripsi_path = file_path
                    self.uploaded_skripsi_text = text
                    upload_label.config(
                        text=f"✔ {os.path.basename(file_path)} terupload",
                        fg=ACCENT_COLOR
                    )
                    messagebox.showinfo("Sukses", "File skripsi berhasil diupload dan diproses.")
                else:
                    self.uploaded_skripsi_path = None
                    self.uploaded_skripsi_text = None
                    upload_label.config(text="Belum ada file terupload", fg="red")

        upload_btn = tk.Button(
            upload_frame,
            text="Upload Skripsi (PDF/DOC/DOCX)",
            command=upload_skripsi,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            activebackground=ACCENT_COLOR,
            activeforeground="white",
            padx=18, pady=6,
            bd=0,
            cursor="hand2"
        )
        upload_btn.pack(side="left", padx=(0, 12))

        upload_label = tk.Label(
            upload_frame,
            text="Belum ada file terupload",
            bg=SECONDARY_COLOR,
            fg="red",
            font=("Segoe UI", 9, "italic")
        )
        upload_label.pack(side="left", padx=(0, 8))

        # --- Fitur Pilih Skripsi (Bab) ---
        select_frame = tk.Frame(chat_win, bg=SECONDARY_COLOR)
        select_frame.pack(fill="x", padx=20, pady=(12, 0))

        ttk.Style().configure("Modern.TLabel", background=SECONDARY_COLOR, foreground=LABEL_FG, font=("Segoe UI", 10, "bold"))
        ttk.Label(
            select_frame,
            text="Pilih Bab Skripsi untuk Diskusi AI:",
            style="Modern.TLabel"
        ).pack(side="left", padx=(0, 10))

        # Ambil daftar bab
        chapter_list = self.get_chapter_list()
        chapter_names = [c[1] for c in chapter_list]
        chapter_var = tk.StringVar()
        chapter_combo = ttk.Combobox(
            select_frame,
            textvariable=chapter_var,
            state="readonly",
            width=38,
            font=("Segoe UI", 10)
        )
        chapter_combo['values'] = chapter_names
        chapter_combo.pack(side="left", padx=(0, 8))
        if chapter_names:
            chapter_combo.current(0)
        else:
            chapter_combo.set('')

        # --- Area chat history modern ---
        chat_frame = tk.Frame(chat_win, bg=SECONDARY_COLOR)
        chat_frame.pack(padx=20, pady=18, fill="both", expand=True)

        chat_history = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            height=22,
            width=90,
            state="disabled",
            font=("Segoe UI", 11),
            bg=ENTRY_BG,
            fg=TEXT_COLOR,
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightbackground="#e0e0e0"
        )
        chat_history.pack(fill="both", expand=True)

        # --- Frame input modern ---
        input_frame = tk.Frame(chat_win, bg=SECONDARY_COLOR)
        input_frame.pack(fill="x", padx=20, pady=(0, 18))

        input_var = tk.StringVar()
        input_entry = tk.Entry(
            input_frame,
            textvariable=input_var,
            font=("Segoe UI", 11),
            bg=ENTRY_BG,
            fg=TEXT_COLOR,
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightbackground="#e0e0e0",
            insertbackground=PRIMARY_COLOR
        )
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=6)

        def send_message(event=None):
            user_msg = input_var.get().strip()
            selected_bab = chapter_var.get().strip()
            skripsi_text = self.uploaded_skripsi_text
            if not user_msg:
                return
            if not selected_bab:
                messagebox.showwarning("Bab Belum Dipilih", "Silakan pilih bab skripsi terlebih dahulu untuk bertanya ke AI.")
                return
            if not skripsi_text:
                messagebox.showwarning("Skripsi Belum Diupload", "Silakan upload file skripsi (PDF/DOC/DOCX) terlebih dahulu agar AI dapat memahami konteks skripsi Anda.")
                return

            # Tampilkan pesan user (bubble style)
            chat_history.config(state="normal")
            chat_history.insert(tk.END, f"\n🧑 Anda ({selected_bab}):\n", "user_bold")
            chat_history.insert(tk.END, f"{user_msg}\n", "user_msg")
            chat_history.config(state="disabled")
            chat_history.see(tk.END)
            input_var.set("")
            chat_win.update_idletasks()

            # Kirim ke Groq AI
            chat_history.config(state="normal")
            chat_history.insert(tk.END, "🤖 AI: (memproses...)\n", "ai_bold")
            chat_history.config(state="disabled")
            chat_history.see(tk.END)
            chat_win.update_idletasks()

            def do_ai():
                # Prompt dengan konteks bab skripsi dan isi skripsi
                # Batasi panjang skripsi_text agar tidak terlalu besar untuk API (misal 2000 kata)
                max_words = 2000
                skripsi_words = skripsi_text.split()
                if len(skripsi_words) > max_words:
                    skripsi_excerpt = " ".join(skripsi_words[:max_words]) + "\n\n[Isi skripsi dipotong untuk ringkasan.]"
                else:
                    skripsi_excerpt = skripsi_text

                bab_prompt = (
                    f"Saya sedang mengerjakan skripsi pada bab '{selected_bab}'. "
                    f"Berikut adalah ringkasan isi skripsi saya (dari file yang diupload):\n"
                    f"{skripsi_excerpt}\n\n"
                    f"Berikut pertanyaan saya: {user_msg}\n"
                    f"Jawablah dengan relevan terhadap bab tersebut dan isi skripsi saya di atas."
                )
                ai_reply = ask_groq_ai(bab_prompt)
                chat_history.config(state="normal")
                # Hapus "(memproses...)" terakhir
                chat_content = chat_history.get("1.0", tk.END)
                lines = chat_content.strip().split("\n")
                if lines and lines[-1].startswith("🤖 AI: (memproses..."):
                    lines = lines[:-1]
                chat_history.delete("1.0", tk.END)
                chat_history.insert(tk.END, "\n".join(lines) + "\n")
                chat_history.insert(tk.END, "🤖 AI:\n", "ai_bold")
                chat_history.insert(tk.END, f"{ai_reply}\n", "ai_msg")
                chat_history.config(state="disabled")
                chat_history.see(tk.END)

            threading.Thread(target=do_ai, daemon=True).start()

        # Style untuk chat bubble
        chat_history.tag_configure("user_bold", font=("Segoe UI", 10, "bold"), foreground=PRIMARY_COLOR, spacing1=6)
        chat_history.tag_configure("user_msg", font=("Segoe UI", 11), foreground=TEXT_COLOR, lmargin1=18, lmargin2=18, spacing3=8)
        chat_history.tag_configure("ai_bold", font=("Segoe UI", 10, "bold"), foreground=ACCENT_COLOR, spacing1=6)
        chat_history.tag_configure("ai_msg", font=("Segoe UI", 11), foreground="#222", lmargin1=18, lmargin2=18, spacing3=12)

        input_entry.bind("<Return>", send_message)
        send_btn = tk.Button(
            input_frame,
            text="Kirim",
            command=send_message,
            bg=ACCENT_COLOR,
            fg="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            activebackground=PRIMARY_COLOR,
            activeforeground="white",
            padx=18, pady=6,
            bd=0,
            cursor="hand2"
        )
        send_btn.pack(side="right", padx=(10, 0))

        input_entry.focus_set()

    def get_chapter_list(self):
        self.cursor.execute("SELECT id, chapter_name FROM chapters ORDER BY id")
        return self.cursor.fetchall()

    def target_page(self):
        # Halaman input dan status target bab
        win = self.new_window("Target Bab")

        frame = ttk.LabelFrame(win, text="Tambah Target Bab")
        frame.pack(pady=10, fill="x", padx=10)

        ttk.Label(frame, text="Nama Bab:").grid(row=0, column=0, padx=5, pady=5)
        chapter_entry = ttk.Entry(frame)
        chapter_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Target Selesai:").grid(row=1, column=0, padx=5, pady=5)
        date_entry = DateEntry(frame, date_pattern='yyyy-mm-dd')
        date_entry.grid(row=1, column=1, padx=5, pady=5)

        def save():
            # Menyimpan target bab ke database
            try:
                self.cursor.execute("INSERT INTO chapters (chapter_name, target_date, status) VALUES (?, ?, ?)",
                                    (chapter_entry.get(), date_entry.get_date(), 'Belum Selesai'))
                self.conn.commit()
                chapter_entry.delete(0, tk.END)
                refresh()
            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Simpan", command=save).grid(row=2, column=1, pady=10)

        tree = ttk.Treeview(win, columns=("Bab", "Target", "Status"), show="headings")
        for col in ("Bab", "Target", "Status"):
            tree.heading(col, text=col)
        tree.pack(expand=True, fill="both", padx=10, pady=10)

        def mark_done():
            # Menandai bab sebagai selesai
            selected = tree.focus()
            if selected:
                item = tree.item(selected)['values']
                self.cursor.execute("UPDATE chapters SET status = 'Selesai' WHERE chapter_name = ?", (item[0],))
                self.conn.commit()
                refresh()

        def delete_selected():
            # Menghapus entri bab
            selected = tree.focus()
            if selected:
                item = tree.item(selected)['values']
                confirm = messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus Bab '{item[0]}'?")
                if confirm:
                    try:
                        self.cursor.execute("DELETE FROM chapters WHERE chapter_name = ?", (item[0],))
                        self.conn.commit()
                        refresh()
                        messagebox.showinfo("Berhasil", "Data berhasil dihapus.")
                    except Exception as e:
                        self.conn.rollback()
                        messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Tandai Selesai", command=mark_done).pack(pady=5)
        ttk.Button(win, text="Hapus", command=delete_selected).pack(pady=5)

        def refresh():
            # Menampilkan data terbaru pada tabel
            tree.delete(*tree.get_children())
            self.cursor.execute("SELECT chapter_name, target_date, status FROM chapters")
            for row in self.cursor.fetchall():
                tree.insert("", "end", values=row)

        refresh()

    def consult_page(self):
        # Halaman jadwal konsultasi
        win = self.new_window("Jadwal Konsultasi")

        frame = ttk.LabelFrame(win, text="Tambah Jadwal Konsultasi")
        frame.pack(pady=10, fill="x", padx=10)

        ttk.Label(frame, text="Tanggal:").grid(row=0, column=0, padx=5, pady=5)
        date_entry = DateEntry(frame, date_pattern='yyyy-mm-dd')
        date_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Nama Dosen:").grid(row=1, column=0, padx=5, pady=5)
        lecturer_entry = ttk.Entry(frame)
        lecturer_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Bab Terkait:").grid(row=2, column=0, padx=5, pady=5)
        chapter_list = self.get_chapter_list()
        chapter_ids = [c[0] for c in chapter_list]
        chapter_names = [c[1] for c in chapter_list]
        chapter_var = tk.StringVar()
        chapter_combo = ttk.Combobox(frame, textvariable=chapter_var, state="readonly")
        chapter_combo['values'] = chapter_names
        chapter_combo.grid(row=2, column=1, padx=5, pady=5)

        def save():
            # Menyimpan jadwal konsultasi dan relasi ke bab (hanya satu bab)
            try:
                selected_chapter = chapter_combo.get()
                if not selected_chapter:
                    raise Exception("Pilih satu Bab terkait.")
                chapter_id = None
                for idx, name in enumerate(chapter_names):
                    if name == selected_chapter:
                        chapter_id = chapter_ids[idx]
                        break
                if chapter_id is None:
                    raise Exception("Bab tidak valid.")
                self.cursor.execute("INSERT INTO consultations (date, lecturer, chapter_id) VALUES (?, ?, ?)",
                                    (date_entry.get_date(), lecturer_entry.get(), chapter_id))
                self.conn.commit()
                lecturer_entry.delete(0, tk.END)
                chapter_combo.set('')
                refresh()
                messagebox.showinfo("Success", "Berhasil menyimpan konsultasi.")
            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Simpan", command=save).grid(row=3, column=1, pady=10)

        tree = ttk.Treeview(win, columns=("Tanggal", "Dosen", "Bab Terkait"), show="headings")
        for col in ("Tanggal", "Dosen", "Bab Terkait"):
            tree.heading(col, text=col)
        tree.pack(expand=True, fill="both", padx=10, pady=10)

        # Fungsi hapus konsultasi
        def delete_selected():
            selected = tree.focus()
            if selected:
                item = tree.item(selected)['values']
                if not item:
                    return
                tanggal, dosen, bab = item
                # Cari id konsultasi berdasarkan data unik
                self.cursor.execute("""
                    SELECT c.id FROM consultations c
                    LEFT JOIN chapters ch ON c.chapter_id = ch.id
                    WHERE c.date = ? AND c.lecturer = ? AND ch.chapter_name = ?
                    LIMIT 1
                """, (tanggal, dosen, bab))
                row = self.cursor.fetchone()
                if row:
                    consult_id = row[0]
                    confirm = messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus konsultasi dengan Dosen '{dosen}' pada '{tanggal}' untuk Bab '{bab}'?")
                    if confirm:
                        try:
                            self.cursor.execute("DELETE FROM consultations WHERE id = ?", (consult_id,))
                            self.conn.commit()
                            refresh()
                            messagebox.showinfo("Berhasil", "Konsultasi berhasil dihapus.")
                        except Exception as e:
                            self.conn.rollback()
                            messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Hapus", command=delete_selected).pack(pady=5)

        def refresh():
            tree.delete(*tree.get_children())
            self.cursor.execute("""
                SELECT c.date, c.lecturer, ch.chapter_name
                FROM consultations c
                LEFT JOIN chapters ch ON c.chapter_id = ch.id
                ORDER BY c.date DESC
            """)
            for row in self.cursor.fetchall():
                tree.insert("", "end", values=row)

        refresh()

    def revision_page(self):
        # Halaman catatan revisi
        win = self.new_window("Catatan Revisi")

        frame = ttk.LabelFrame(win, text="Tambah Catatan Revisi")
        frame.pack(pady=10, fill="x", padx=10)

        ttk.Label(frame, text="Bab Terkait:").grid(row=0, column=0, padx=5, pady=5)
        chapter_list = self.get_chapter_list()
        chapter_ids = [c[0] for c in chapter_list]
        chapter_names = [c[1] for c in chapter_list]
        chapter_var = tk.StringVar()
        chapter_combo = ttk.Combobox(frame, textvariable=chapter_var, state="readonly")
        chapter_combo['values'] = chapter_names
        chapter_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Catatan:").grid(row=2, column=0, padx=5, pady=5)
        notes_text = tk.Text(frame, height=4)
        notes_text.grid(row=2, column=1, padx=5, pady=5)

        def save():
            try:
                notes = notes_text.get("1.0", "end-1c")
                if not notes.strip():
                    raise Exception("Catatan tidak boleh kosong.")
                selected_chapter = chapter_combo.get()
                if not selected_chapter:
                    raise Exception("Pilih satu Bab terkait.")
                chapter_id = None
                for idx, name in enumerate(chapter_names):
                    if name == selected_chapter:
                        chapter_id = chapter_ids[idx]
                        break
                if chapter_id is None:
                    raise Exception("Bab tidak valid.")
                self.cursor.execute("""
                    INSERT INTO revisions (notes, date, chapter_id)
                    VALUES (?, DATE('now'), ?)
                """, (notes, chapter_id))
                self.conn.commit()
                notes_text.delete("1.0", tk.END)
                chapter_combo.set('')
                refresh()
                messagebox.showinfo("Success", "Revisi tersimpan.")
            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Simpan", command=save).grid(row=3, column=1, pady=10)

        tree = ttk.Treeview(win, columns=("Bab", "Catatan"), show="headings")
        for col in ("Bab", "Catatan"):
            tree.heading(col, text=col)
        tree.pack(expand=True, fill="both", padx=10, pady=10)

        # Fungsi hapus revisi
        def delete_selected():
            selected = tree.focus()
            if selected:
                item = tree.item(selected)['values']
                if not item:
                    return
                bab, catatan = item
                # Cari id revisi berdasarkan data unik
                self.cursor.execute("""
                    SELECT r.id FROM revisions r
                    LEFT JOIN chapters ch ON r.chapter_id = ch.id
                    WHERE ch.chapter_name = ? AND r.notes = ?
                    ORDER BY r.id DESC
                    LIMIT 1
                """, (bab, catatan))
                row = self.cursor.fetchone()
                if row:
                    revision_id = row[0]
                    confirm = messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus catatan revisi untuk Bab '{bab}'?")
                    if confirm:
                        try:
                            self.cursor.execute("DELETE FROM revisions WHERE id = ?", (revision_id,))
                            self.conn.commit()
                            refresh()
                            messagebox.showinfo("Berhasil", "Catatan revisi berhasil dihapus.")
                        except Exception as e:
                            self.conn.rollback()
                            messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Hapus", command=delete_selected).pack(pady=5)

        def refresh():
            tree.delete(*tree.get_children())
            self.cursor.execute("""
                SELECT ch.chapter_name, r.notes
                FROM revisions r
                LEFT JOIN chapters ch ON r.chapter_id = ch.id
                ORDER BY r.id DESC
            """)
            for row in self.cursor.fetchall():
                tree.insert("", "end", values=row)

        refresh()

    def statistic_page(self):
        # Menampilkan grafik pie progress skripsi
        win = self.new_window("Statistik Progress")
        try:
            self.cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'Selesai' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'Belum Selesai' THEN 1 ELSE 0 END)
                FROM chapters
            """)
            selesai, belum = self.cursor.fetchone()
            selesai = selesai or 0
            belum = belum or 0

            fig, ax = plt.subplots()
            ax.pie([selesai, belum], labels=["Selesai", "Belum Selesai"],
                   autopct='%1.1f%%', colors=["green", "red"])
            ax.set_title("Progress Skripsi")
            FigureCanvasTkAgg(fig, win).get_tk_widget().pack()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def print_pdf_report(self):
        # Fungsi untuk mencetak laporan PDF kinerja skripsi dengan tampilan modern & profesional
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Simpan Laporan PDF"
            )
            if not file_path:
                return

            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            margin = 40
            padding_y = 8  # padding vertikal antar baris
            padding_x = 10 # padding horizontal antar kolom/tepi
            y = height - margin

            # Header dengan garis dan logo (jika ada)
            c.setFillColor(colors.HexColor(PDF_HEADER_COLOR))
            c.rect(0, height-70, width, 70, fill=1, stroke=0)
            c.setFillColor(PDF_HEADER_TEXT_COLOR)
            c.setFont(PDF_HEADER_FONT, PDF_HEADER_FONT_SIZE)
            c.drawString(margin + padding_x, height-50, PDF_HEADER_TITLE)
            c.setFont(PDF_HEADER_DATE_FONT, PDF_HEADER_DATE_FONT_SIZE)
            c.drawString(margin + padding_x, height-65, f"Tanggal Cetak: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
            c.setFillColor(colors.black)
            y = height - 90

            # Garis bawah header
            c.setStrokeColor(colors.HexColor(PDF_HEADER_LINE_COLOR))
            c.setLineWidth(2)
            c.line(margin, y+10, width-margin, y+10)
            y -= 10 + padding_y

            # Section: Target Bab
            c.setFont("Helvetica-Bold", 15)
            c.setFillColor(colors.HexColor(PDF_SECTION_TITLE_COLOR))
            c.drawString(margin + padding_x, y, "1. Target Bab")
            y -= 18 + padding_y
            c.setFillColor(colors.black)
            self.cursor.execute("SELECT chapter_name, target_date, status FROM chapters ORDER BY id")
            chapters = self.cursor.fetchall()
            if chapters:
                # Table header
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_BG))
                c.roundRect(margin-2, y-2, width-2*margin+4, 22, 5, fill=1, stroke=0)
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_TEXT))
                c.setFont("Helvetica-Bold", 11)
                c.drawString(margin+5+padding_x, y+4, "Bab")
                c.drawString(margin+180+padding_x, y+4, "Target Selesai")
                c.drawString(margin+320+padding_x, y+4, "Status")
                c.setFont("Helvetica", 11)
                y -= 22 + padding_y
                c.setFillColor(colors.black)
                for idx, (bab, tgl, status) in enumerate(chapters):
                    c.setFillColor(colors.HexColor(PDF_TABLE_ROW_ALT_BG) if (idx%2==0) else PDF_TABLE_ROW_BG)
                    c.roundRect(margin-2, y-2, width-2*margin+4, 18, 3, fill=1, stroke=0)
                    c.setFillColor(colors.black)
                    c.drawString(margin+5+padding_x, y+2, str(bab))
                    c.drawString(margin+180+padding_x, y+2, str(tgl))
                    # Status badge with padding
                    status_text = f"  {status}  "  # Tambahkan padding kiri dan kanan
                    if status == "Selesai":
                        c.setFillColor(colors.HexColor(PDF_STATUS_DONE_COLOR))
                    else:
                        c.setFillColor(colors.HexColor(PDF_STATUS_NOT_DONE_COLOR))
                    # Hitung lebar badge berdasarkan panjang status + padding
                    badge_font = "Helvetica-Bold"
                    badge_font_size = 10
                    c.setFont(badge_font, badge_font_size)
                    badge_width = c.stringWidth(status_text, badge_font, badge_font_size) + 8  # extra padding
                    badge_x = margin+320+padding_x
                    badge_y = y+2
                    c.roundRect(badge_x, badge_y, badge_width, 14, 4, fill=1, stroke=0)
                    c.setFillColor(colors.white)
                    c.drawCentredString(badge_x + badge_width/2, badge_y+4, status_text)
                    c.setFont("Helvetica", 11)
                    c.setFillColor(colors.black)
                    y -= 18 + padding_y
                    if y < 100:
                        c.showPage()
                        y = height - margin
            else:
                c.setFont("Helvetica-Oblique", 11)
                c.drawString(margin + padding_x, y, "Belum ada data target bab.")
                y -= 18 + padding_y

            y -= 10 + padding_y

            # Section: Jadwal Konsultasi
            c.setFont("Helvetica-Bold", 15)
            c.setFillColor(colors.HexColor(PDF_SECTION_TITLE_COLOR))
            c.drawString(margin + padding_x, y, "2. Jadwal Konsultasi")
            y -= 18 + padding_y
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 11)
            self.cursor.execute("""
                SELECT c.date, c.lecturer, ch.chapter_name
                FROM consultations c
                LEFT JOIN chapters ch ON c.chapter_id = ch.id
                ORDER BY c.date DESC
            """)
            consults = self.cursor.fetchall()
            if consults:
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_BG))
                c.roundRect(margin-2, y-2, width-2*margin+4, 22, 5, fill=1, stroke=0)
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_TEXT))
                c.setFont("Helvetica-Bold", 11)
                c.drawString(margin+5+padding_x, y+4, "Tanggal")
                c.drawString(margin+110+padding_x, y+4, "Dosen")
                c.drawString(margin+260+padding_x, y+4, "Bab Terkait")
                c.setFont("Helvetica", 11)
                y -= 22 + padding_y
                c.setFillColor(colors.black)
                for idx, (tgl, dosen, bab) in enumerate(consults):
                    c.setFillColor(colors.HexColor(PDF_TABLE_ROW_ALT_BG) if (idx%2==0) else PDF_TABLE_ROW_BG)
                    c.roundRect(margin-2, y-2, width-2*margin+4, 18, 3, fill=1, stroke=0)
                    c.setFillColor(colors.black)
                    c.drawString(margin+5+padding_x, y+2, str(tgl))
                    c.drawString(margin+110+padding_x, y+2, str(dosen))
                    c.drawString(margin+260+padding_x, y+2, str(bab))
                    y -= 18 + padding_y
                    if y < 100:
                        c.showPage()
                        y = height - margin
            else:
                c.setFont("Helvetica-Oblique", 11)
                c.drawString(margin + padding_x, y, "Belum ada data konsultasi.")
                y -= 18 + padding_y

            y -= 10 + padding_y

            # Section: Catatan Revisi
            c.setFont("Helvetica-Bold", 15)
            c.setFillColor(colors.HexColor(PDF_SECTION_TITLE_COLOR))
            c.drawString(margin + padding_x, y, "3. Catatan Revisi")
            y -= 18 + padding_y
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 11)
            self.cursor.execute("""
                SELECT ch.chapter_name, r.notes, r.date
                FROM revisions r
                LEFT JOIN chapters ch ON r.chapter_id = ch.id
                ORDER BY r.id DESC
            """)
            revisions = self.cursor.fetchall()
            if revisions:
                # Header background
                header_height = 22
                header_y = y
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_BG))
                c.roundRect(margin, header_y, width-2*margin, header_height, 5, fill=1, stroke=0)
                # Header text
                c.setFillColor(colors.HexColor(PDF_TABLE_HEADER_TEXT))
                c.setFont("Helvetica-Bold", 11)
                c.drawString(margin + padding_x + 5, header_y + 6, "Bab")
                c.drawString(margin + padding_x + 120, header_y + 6, "Catatan")
                c.drawString(margin + padding_x + 380, header_y + 6, "Tanggal")
                y -= header_height + padding_y
                c.setFont("Helvetica", 11)
                for idx, (bab, catatan, tgl) in enumerate(revisions):
                    row_height = 18
                    row_y = y
                    # Row background
                    c.setFillColor(colors.HexColor(PDF_TABLE_ROW_ALT_BG) if (idx % 2 == 0) else PDF_TABLE_ROW_BG)
                    c.roundRect(margin, row_y, width-2*margin, row_height, 3, fill=1, stroke=0)
                    # Row text
                    c.setFillColor(colors.black)
                    # Batasi bab maksimal 15 huruf
                    bab_str = str(bab)
                    if len(bab_str) > 15:
                        bab_str = bab_str[:12] + "..."
                    c.drawString(margin + padding_x + 5, row_y + 4, bab_str)
                    # Catatan wrap/ellipsis
                    catatan_str = str(catatan)
                    if len(catatan_str) > 50:
                        catatan_str = catatan_str[:47] + "..."
                    c.drawString(margin + padding_x + 120, row_y + 4, catatan_str)
                    c.drawString(margin + padding_x + 380, row_y + 4, str(tgl))
                    y -= row_height + padding_y
                    if y < 100:
                        c.showPage()
                        y = height - margin
            else:
                c.setFont("Helvetica-Oblique", 11)
                c.drawString(margin + padding_x, y, "Belum ada catatan revisi.")
                y -= 18 + padding_y

            y -= 10 + padding_y

            # Section: Statistik Progress
            c.setFont("Helvetica-Bold", 15)
            c.setFillColor(colors.HexColor(PDF_SECTION_TITLE_COLOR))
            c.drawString(margin + padding_x, y, "4. Statistik Progress")
            y -= 18 + padding_y
            c.setFillColor(colors.black)
            self.cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'Selesai' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'Belum Selesai' THEN 1 ELSE 0 END)
                FROM chapters
            """)
            selesai, belum = self.cursor.fetchone()
            selesai = selesai or 0
            belum = belum or 0
            total = selesai + belum
            c.setFont("Helvetica", 11)
            # Progress bar visual
            bar_x = margin + padding_x
            bar_y = y
            bar_width = width - 2*margin - 2*padding_x
            bar_height = 18
            if total > 0:
                percent = selesai / total
                # Text
                c.setFillColor(colors.black)
                c.drawString(bar_x, bar_y-5, f"Bab Selesai: {selesai}")
                c.drawString(bar_x+150, bar_y-5, f"Bab Belum Selesai: {belum}")
                c.drawString(bar_x+320, bar_y-5, f"Persentase Selesai: {percent*100:.1f}%")
                y -= 30 + padding_y
            else:
                c.setFont("Helvetica-Oblique", 11)
                c.drawString(margin + padding_x, y, "Belum ada data progress.")
                y -= 18 + padding_y

            # Footer
            c.setStrokeColor(colors.HexColor(PDF_FOOTER_LINE_COLOR))
            c.setLineWidth(1)
            c.line(margin, 50, width-margin, 50)
            c.setFont(PDF_FOOTER_FONT, PDF_FOOTER_FONT_SIZE)
            c.setFillColor(colors.HexColor(PDF_FOOTER_TEXT_COLOR))
            c.drawCentredString(width/2, 38, PDF_FOOTER_TEXT)
            c.save()
            messagebox.showinfo("Sukses", f"Laporan PDF berhasil disimpan di:\n{file_path}")
            send_wa_pdf_notification(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal mencetak laporan PDF:\n{e}")

    def new_window(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(WINDOW_GEOMETRY)
        win.configure(bg=WINDOW_BG_COLOR)
        return win

    def __del__(self):
        if hasattr(self, 'conn'):
            self.cursor.close()
            self.conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = ThesisApp(root)
    root.mainloop()