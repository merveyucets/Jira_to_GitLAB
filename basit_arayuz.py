import customtkinter as ctk
import subprocess
import threading
import sys
import os
import re
import json
from dotenv import load_dotenv
from PIL import Image

# Görünüm Ayarları
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class DualSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GIT ⇌ JIRA Operasyon Merkezi")
        self.geometry("1100x900") # İki tablo sığsın diye biraz daha uzattık

        self.font_title = ("Roboto Medium", 20)
        self.font_console = ("JetBrains Mono", 12)

        # --- RESİM VE KLASÖR AYARLARI ---
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_folder = os.path.join(self.current_dir, "logo")
        self.csv_folder_path = os.path.join(self.current_dir, "csv_folder")

        def load_and_clean_image(filename):
            try:
                path = os.path.join(logo_folder, filename)
                if not os.path.exists(path): return None
                img = Image.open(path).convert("RGBA")
                data = img.getdata()
                new_data = []
                for item in data:
                    if item[0] > 220 and item[1] > 220 and item[2] > 220:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                img.putdata(new_data)
                return ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
            except Exception:
                return None

        self.jira_icon = load_and_clean_image("jira-software-logo.png")
        self.git_icon = load_and_clean_image("gitlab-logo.png")

        # ========================================================
        #              ANA SEKMELİ YAPI (TABVIEW)
        # ========================================================
        self.tabview = ctk.CTkTabview(self, width=1060, height=750)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(10, 10))

        # Sekmeleri Oluştur
        self.tab_main = self.tabview.add("🔄 Aktarım Merkezi")
        self.tab_settings = self.tabview.add("⚙️ Ayarlar")

        # ========================================================
        #           SEKME 1: AKTARIM MERKEZİ
        # ========================================================
        
        # --- JQL GİRİŞ ALANI ---
        self.input_label = ctk.CTkLabel(self.tab_main, text="JQL FİLTRESİ (Sadece Sol Taraf İçin):", font=("Roboto", 12, "bold"), text_color="gray")
        self.input_label.pack(anchor="w", pady=(0, 5), padx=10)

        self.jql_entry = ctk.CTkEntry(self.tab_main, placeholder_text="Örn: project = GYT", height=40, font=("Consolas", 14), border_width=0, fg_color="#D3D3D3")
        self.jql_entry.pack(fill="x", padx=10, pady=(0, 15))

        # --- BÖLÜNMÜŞ EKRAN YAPISI ---
        self.split_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.split_frame.pack(fill="both", expand=True)

        # >>> SOL PANEL (MAVİ) <<<
        self.left_frame = ctk.CTkFrame(self.split_frame, fg_color="#CEE3FA", corner_radius=15)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.lbl_left = ctk.CTkLabel(self.left_frame, text="  JIRA ➔ GITLAB", font=self.font_title, text_color="#2B709B", image=self.jira_icon, compound="left")
        self.lbl_left.pack(pady=(15, 10))

        self.btn_left = ctk.CTkButton(
            self.left_frame, text="AKTARIMI BAŞLAT (ÖN İZLEME)", 
            fg_color="#0065FF", hover_color="#0747A6",
            height=50, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.baslat_sol_thread_preview
        )
        self.btn_left.pack(fill="x", padx=15, pady=10)

        self.console_left = ctk.CTkTextbox(self.left_frame, font=self.font_console, fg_color="#0f0f0f", text_color="#D4D4D4", corner_radius=10)
        self.console_left.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.setup_tags(self.console_left)
        self.console_left.insert("0.0", "Hazır. Verileri çekmek ve ön izlemek için MAVİ butona basın.\n", "dim")

        # --- Aksiyon Paneli ---
        self.action_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        
        self.btn_confirm_left = ctk.CTkButton(self.action_frame, text="✅ ONAYLA VE BAŞLAT", fg_color="#27AE60", hover_color="#1E8449", height=50, corner_radius=10, font=("Roboto", 14, "bold"), command=self.baslat_sol_thread_execute)
        self.btn_cancel_left = ctk.CTkButton(self.action_frame, text="❌ İPTAL", fg_color="#C0392B", hover_color="#922B21", height=50, width=100, corner_radius=10, font=("Roboto", 14, "bold"), command=self.islem_iptal_et)
        self.progress_bar = ctk.CTkProgressBar(self.action_frame, height=20, corner_radius=10, progress_color="#27AE60")
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(self.action_frame, text="İşleniyor: 0%", font=("Roboto", 12))
        self.btn_reset = ctk.CTkButton(self.action_frame, text="🔄 EKRANI TEMİZLE VE YENİ SORGU YAP", fg_color="#2980B9", hover_color="#1F618D", height=50, corner_radius=10, font=("Roboto", 14, "bold"), command=self.ekrani_sifirla)

        # >>> SAĞ PANEL (TURUNCU) <<<
        self.right_frame = ctk.CTkFrame(self.split_frame, fg_color="#F7E1C0", corner_radius=15)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.lbl_right = ctk.CTkLabel(self.right_frame, text="  GITLAB ➔ JIRA", font=self.font_title, text_color="#E67E22", image=self.git_icon, compound="left")
        self.lbl_right.pack(pady=(15, 10))

        self.btn_right = ctk.CTkButton(
            self.right_frame, text="STATÜLERİ GÜNCELLE", 
            fg_color="#E67E22", hover_color="#D35400",
            height=50, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.baslat_sag_thread
        )
        self.btn_right.pack(fill="x", padx=15, pady=10)

        self.console_right = ctk.CTkTextbox(self.right_frame, font=self.font_console, fg_color="#0f0f0f", text_color="#D4D4D4", corner_radius=10)
        self.console_right.pack(fill="both", expand=True, padx=10, pady=10)
        self.setup_tags(self.console_right)
        self.console_right.insert("0.0", "Hazır. Status güncellemek için TURUNCU butona basın.\n", "dim")

        # ========================================================
        #           SEKME 2: AYARLAR PANELİ (YENİ YAPILANDIRMA)
        # ========================================================
        self.create_settings_tab() 
        self.load_initial_jql()

    # --- AYARLAR FONKSİYONLARI ---
    def create_settings_tab(self):
        """Ayarlar Sekmesini oluşturur: Global, Takım Map, User Map."""
        settings_tab = self.tab_settings
        
        # 1. Kaydet Butonu (En Üstte Olsun, Kolay Erişim)
        btn_save = ctk.CTkButton(settings_tab, text="💾 TÜM AYARLARI KAYDET VE UYGULA", 
                                 fg_color="#27AE60", hover_color="#1E8449", height=40, font=("Roboto", 14, "bold"),
                                 command=self.save_settings)
        btn_save.pack(fill="x", padx=10, pady=10)

        # --- SCROLLABLE ANA FRAME ---
        # Tüm ayarları içine alan kaydırılabilir bir alan
        self.main_scroll = ctk.CTkScrollableFrame(settings_tab, fg_color="transparent")
        self.main_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # --- A) GLOBAL AYARLAR ---
        self.global_frame = ctk.CTkFrame(self.main_scroll)
        self.global_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkLabel(self.global_frame, text="Global API & Proje Ayarları (.env)", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        self.api_entries = {}
        fields = [
            ("GITLAB_TOKEN", "GitLab Token", True), ("MASTER_PROJECT_ID", "Master Project ID", False),
            ("GROUP_ID", "Group ID (Milestone)", False), ("JIRA_URL", "Jira URL", False), ("JIRA_API_TOKEN", "Jira API Token", True)
        ]
        
        grid_api = ctk.CTkFrame(self.global_frame, fg_color="transparent")
        grid_api.pack(fill="x", padx=10, pady=5)
        grid_api.columnconfigure(1, weight=1)

        for i, (key, label, is_secret) in enumerate(fields):
            ctk.CTkLabel(grid_api, text=f"{label}:", anchor="w").grid(row=i, column=0, padx=5, pady=2, sticky="w")
            entry = ctk.CTkEntry(grid_api, show="*" if is_secret else None)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky="ew")
            self.api_entries[key] = entry

        # --- B) TAKIM & PROJE HARİTASI ---
        self.team_frame = ctk.CTkFrame(self.main_scroll)
        self.team_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkLabel(self.team_frame, text="1. Takım & Proje Eşleşmeleri (Jira Takım -> GitLab Proje)", font=("Roboto", 14, "bold"), text_color="#E67E22").pack(anchor="w", padx=10, pady=5)
        
        # Başlıklar
        t_head = ctk.CTkFrame(self.team_frame, fg_color="gray", height=30)
        t_head.pack(fill="x", padx=5)
        for i, t in enumerate(["Jira Takım Adı", "GitLab Proje ID", "Görünür İsim", "Sil"]):
            t_head.columnconfigure(i, weight=1 if i==3 else 3)
            ctk.CTkLabel(t_head, text=t, font=("Roboto", 12, "bold")).grid(row=0, column=i, sticky="ew")

        # Satırlar için container
        self.team_rows_container = ctk.CTkFrame(self.team_frame, fg_color="transparent")
        self.team_rows_container.pack(fill="x", padx=5, pady=5)
        self.team_entries = [] # Referansları tut

        ctk.CTkButton(self.team_frame, text="+ Yeni Takım Ekle", height=25, command=lambda: self.add_team_row({})).pack(pady=5)

        # --- C) KULLANICI HARİTASI ---
        self.user_frame = ctk.CTkFrame(self.main_scroll)
        self.user_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkLabel(self.user_frame, text="2. Kullanıcı Eşleşmeleri (Jira User -> GitLab User ID)", font=("Roboto", 14, "bold"), text_color="#2980B9").pack(anchor="w", padx=10, pady=5)
        
        # Başlıklar
        u_head = ctk.CTkFrame(self.user_frame, fg_color="gray", height=30)
        u_head.pack(fill="x", padx=5)
        for i, t in enumerate(["Jira Kullanıcı Adı", "GitLab User ID", "Sil"]):
            u_head.columnconfigure(i, weight=1 if i==2 else 3)
            ctk.CTkLabel(u_head, text=t, font=("Roboto", 12, "bold")).grid(row=0, column=i, sticky="ew")

        # Satırlar için container
        self.user_rows_container = ctk.CTkFrame(self.user_frame, fg_color="transparent")
        self.user_rows_container.pack(fill="x", padx=5, pady=5)
        self.user_entries = [] # Referansları tut

        ctk.CTkButton(self.user_frame, text="+ Yeni Kullanıcı Ekle", height=25, command=lambda: self.add_user_row({})).pack(pady=5)

        # Yükle
        self.load_global_settings()
        self.load_mapping_settings()

    # --- AYARLARI YÜKLEME ---
    def load_global_settings(self):
        load_dotenv() 
        for key, entry in self.api_entries.items():
            entry.delete(0, "end")
            entry.insert(0, os.getenv(key, ""))

    def load_mapping_settings(self):
        # Önce temizle (Yenileme için)
        for frame, _ in self.team_entries: frame.destroy()
        for frame, _ in self.user_entries: frame.destroy()
        self.team_entries = []
        self.user_entries = []

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except: data = {}

        # Takımları Yükle
        for item in data.get("team_mappings", []):
            self.add_team_row(item)
        
        # Kullanıcıları Yükle
        for item in data.get("user_mappings", []):
            self.add_user_row(item)

    # --- SATIR EKLEME METOTLARI ---
    def add_team_row(self, data):
        row = ctk.CTkFrame(self.team_rows_container, fg_color="white")
        row.pack(fill="x", pady=2)
        for i in range(4): row.columnconfigure(i, weight=1 if i==3 else 3)
        
        entries = {}
        keys = ["jira_team_name", "gitlab_project_id", "friendly_name"]
        
        for i, k in enumerate(keys):
            e = ctk.CTkEntry(row, text_color="black")
            e.insert(0, str(data.get(k, "")))
            e.grid(row=0, column=i, sticky="ew", padx=2)
            entries[k] = e
            
        btn_del = ctk.CTkButton(row, text="X", width=30, fg_color="#C0392B", command=lambda: self.remove_row(row, self.team_entries))
        btn_del.grid(row=0, column=3, padx=2)
        
        self.team_entries.append((row, entries))

    def add_user_row(self, data):
        row = ctk.CTkFrame(self.user_rows_container, fg_color="white")
        row.pack(fill="x", pady=2)
        for i in range(3): row.columnconfigure(i, weight=1 if i==2 else 3)
        
        entries = {}
        keys = ["jira_user", "gitlab_user_id"]
        
        for i, k in enumerate(keys):
            e = ctk.CTkEntry(row, text_color="black")
            e.insert(0, str(data.get(k, "")))
            e.grid(row=0, column=i, sticky="ew", padx=2)
            entries[k] = e
            
        btn_del = ctk.CTkButton(row, text="X", width=30, fg_color="#C0392B", command=lambda: self.remove_row(row, self.user_entries))
        btn_del.grid(row=0, column=2, padx=2)
        
        self.user_entries.append((row, entries))

    def remove_row(self, row_frame, list_ref):
        row_frame.destroy()
        # Listeden de silmemiz lazım, ancak lambda içinde direkt index bulmak zor.
        # Basitçe: Save sırasında destroy edilmiş widget'ları kontrol edeceğiz.
        
    # --- KAYDETME ---
    def save_settings(self):
        # 1. .env Kaydet
        env_lines = [f"{k}={e.get()}" for k, e in self.api_entries.items()]
        try:
            with open(".env", "w") as f: f.write("\n".join(env_lines))
            self.log_yaz(self.console_left, "✅ Global Ayarlar (.env) kaydedildi.\n", "success")
        except Exception as e:
            self.log_yaz(self.console_left, f"❌ .env Hatası: {e}\n", "error")

        # 2. config.json Kaydet
        try:
            with open("config.json", "r", encoding="utf-8") as f: 
                settings = json.load(f).get("settings", {})
        except: 
            settings = {"default_jql": "project = GYT AND created >= -15d"}

        # Takımları Topla
        new_teams = []
        for row, ent in self.team_entries:
            if row.winfo_exists() and ent["jira_team_name"].get().strip():
                try:
                    new_teams.append({
                        "jira_team_name": ent["jira_team_name"].get(),
                        "gitlab_project_id": int(ent["gitlab_project_id"].get() or 0),
                        "friendly_name": ent["friendly_name"].get()
                    })
                except ValueError:
                    self.log_yaz(self.console_left, "❌ HATA: Proje ID sayı olmalı.\n", "error"); return

        # Kullanıcıları Topla
        new_users = []
        for row, ent in self.user_entries:
            if row.winfo_exists() and ent["jira_user"].get().strip():
                try:
                    new_users.append({
                        "jira_user": ent["jira_user"].get(),
                        "gitlab_user_id": int(ent["gitlab_user_id"].get() or 0)
                    })
                except ValueError:
                    self.log_yaz(self.console_left, "❌ HATA: User ID sayı olmalı.\n", "error"); return

        # Yaz
        final_data = {
            "team_mappings": new_teams,
            "user_mappings": new_users,
            "settings": settings
        }
        
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            self.log_yaz(self.console_left, "✅ Config Ayarları (config.json) kaydedildi.\n", "success")
        except Exception as e:
            self.log_yaz(self.console_left, f"❌ config.json Hatası: {e}\n", "error")
            
        self.log_yaz(self.console_left, "🔄 Değişiklikler için uygulamayı yeniden başlatın.\n", "warning")

    # --- DİĞER STANDART FONKSİYONLAR (JQL, Log vb.) ---
    def load_initial_jql(self):
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    jql = json.load(f).get("settings", {}).get("default_jql", "")
                    if jql:
                        self.jql_entry.delete(0, "end")
                        self.jql_entry.insert(0, jql)
            except: pass

    def setup_tags(self, textbox):
        textbox._textbox.tag_config("error", foreground="#FF5555")
        textbox._textbox.tag_config("success", foreground="#50FA7B")
        textbox._textbox.tag_config("warning", foreground="#FFB86C")
        textbox._textbox.tag_config("info", foreground="#8BE9FD")
        textbox._textbox.tag_config("dim", foreground="#8FA0D4")

    # --- AKSİYONLAR ---
    def goster_onay_iptal(self):
        self.action_frame.pack(fill="x", padx=15, pady=10)
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        self.btn_reset.pack_forget()
        self.btn_confirm_left.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_cancel_left.pack(side="right", padx=(5, 0))

    def goster_progress_bar(self):
        self.btn_confirm_left.pack_forget()
        self.btn_cancel_left.pack_forget()
        self.progress_label.pack(pady=(0, 5))
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_label.configure(text="Başlatılıyor...")

    def goster_reset_butonu(self):
        self.action_frame.pack(fill="x", padx=15, pady=10)
        self.btn_confirm_left.pack_forget()
        self.btn_cancel_left.pack_forget()
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        self.btn_reset.pack(fill="x", pady=0)

    def ekrani_sifirla(self):
        self.islem_iptal_et(silent=True)
        self.console_left.delete("0.0", "end")
        self.log_yaz(self.console_left, "✨ Ekran temizlendi. Yeni işlem için hazır.\n", "info")
        self.action_frame.pack_forget()
        self.btn_left.configure(state="normal")
        self.jql_entry.configure(state="normal")

    def islem_iptal_et(self, silent=False):
        to_add_file = os.path.join(self.csv_folder_path, "jira_to_add.csv")
        try:
            if os.path.exists(to_add_file):
                os.remove(to_add_file)
                if not silent: print("🧹 Geçici dosya silindi.")
        except Exception: pass
        if not silent:
            self.console_left.delete("0.0", "end")
            self.log_yaz(self.console_left, "🚫 İşlem iptal edildi.\n", "warning")
            self.action_frame.pack_forget()
            self.btn_left.configure(state="normal", text="AKTARIMI BAŞLAT (ÖN İZLEME)")

    # --- THREAD İŞLEMLERİ (SOL TARAF) ---
    def baslat_sol_thread_preview(self):
        jql = self.jql_entry.get()
        if not jql.strip():
            self.log_yaz(self.console_left, "⚠️ HATA: JQL boş olamaz!\n", "error")
            return
        
        self.console_left.delete("0.0", "end")
        self.btn_left.configure(state="disabled", text="⏳ VERİ ÇEKİLİYOR...")
        self.action_frame.pack_forget()

        t = threading.Thread(
            target=self.scripti_calistir, 
            args=("sync_to_gitlab.py", self.console_left, self.btn_left, "AKTARIMI BAŞLAT (ÖN İZLEME)", jql, "--preview", self.on_preview_complete)
        )
        t.start()

    def baslat_sol_thread_execute(self):
        jql = self.jql_entry.get() 
        self.btn_left.configure(state="disabled")
        self.jql_entry.configure(state="disabled")
        self.goster_progress_bar()

        t = threading.Thread(
            target=self.scripti_calistir, 
            args=("sync_to_gitlab.py", self.console_left, None, "", jql, "--execute", self.on_execute_complete)
        )
        t.start()

    def on_preview_complete(self, return_code, output_text):
        if return_code != 0:
            self.btn_left.configure(state="normal")
            self.action_frame.pack_forget()
            return

        is_empty = ("Aktarılacak toplam 0 issue tespit edildi" in output_text or 
                    "Aktarılacak yeni kayıt bulunamadı" in output_text or 
                    "Tüm issue'lar zaten güncel" in output_text)

        if is_empty:
            self.log_yaz(self.console_left, "\nℹ️ Aktarılacak yeni kayıt bulunamadı.\n", "warning")
            self.goster_reset_butonu()
            self.btn_left.configure(state="disabled")
        elif "Gitlab'e aktarılacak toplam" in output_text:
            self.goster_onay_iptal()
            self.log_yaz(self.console_left, "\n⬇️ Lütfen işlemi ONAYLAYIN veya İPTAL edin.\n", "success")
            self.btn_left.configure(state="normal")

    def on_execute_complete(self, return_code, output_text):
        self.goster_reset_butonu()
        if return_code == 0:
             self.log_yaz(self.console_left, "\n✅ Tüm aktarım tamamlandı.\n", "success")
             self.progress_label.configure(text="Tamamlandı: 100%")
             self.progress_bar.set(1)

    def baslat_sag_thread(self):
        self.btn_right.configure(state="disabled", text="⏳ GİTLAB BAĞLANIYOR...")
        self.console_right.delete("0.0", "end")
        t = threading.Thread(target=self.scripti_calistir, args=("sync_gitlab_status_to_jira.py", self.console_right, self.btn_right, "STATÜLERİ GÜNCELLE"))
        t.start()

    def scripti_calistir(self, script_name, target_console, target_btn, btn_reset_text, arguman=None, mode_flag=None, callback=None):
        full_output = ""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, script_name)
            python_exe = sys.executable

            self.log_yaz(target_console, f"📂 Script: {script_name}\n", "dim")
            if arguman: self.log_yaz(target_console, f"📡 JQL: {arguman}\n", "info")

            cmd = [python_exe, "-u", script_path]
            if arguman: cmd.append(arguman)
            if mode_flag: cmd.append(mode_flag)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, cwd=current_dir, encoding='utf-8', errors='replace', env=env)
            progress_pattern = re.compile(r"--- (\d+)/(\d+):")

            for line in process.stdout: 
                self.akilli_log_yaz(target_console, line)
                full_output += line
                if mode_flag == "--execute":
                    match = progress_pattern.search(line)
                    if match:
                        current, total = int(match.group(1)), int(match.group(2))
                        if total > 0:
                            percent = current / total
                            self.progress_bar.set(percent)
                            self.progress_label.configure(text=f"İşleniyor: {current}/{total} (%{int(percent*100)})")

            for line in process.stderr: self.log_yaz(target_console, f"⚠️ {line}", "warning")
            process.wait()
            
            if mode_flag != "--execute" and target_btn: self.btn_left.configure(state="normal")
            if callback: self.after(100, lambda: callback(process.returncode, full_output))

        except Exception as e: 
            self.log_yaz(target_console, f"\n❌ Kritik Hata: {e}\n", "error")
            if target_btn: target_btn.configure(state="normal")
        finally: 
            if target_btn and mode_flag != "--execute": target_btn.configure(state="normal", text=btn_reset_text)

    def akilli_log_yaz(self, console, line):
        tag = "normal"
        if "❌" in line or "Hata" in line: tag = "error"
        elif "⚠️" in line: tag = "warning"
        elif "✅" in line or "Başarılı" in line: tag = "success"
        elif "➡️" in line: tag = "info"
        elif "---" in line: tag = "dim"
        self.log_yaz(console, line, tag)

    def log_yaz(self, console, mesaj, tag=None):
        console.configure(state="normal")
        if tag: console.insert("end", mesaj, tag)
        else: console.insert("end", mesaj)
        console.see("end")

if __name__ == "__main__":
    app = DualSyncApp()
    app.mainloop()