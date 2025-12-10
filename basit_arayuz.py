import customtkinter as ctk
import subprocess
import threading
import sys
import os
import re
from PIL import Image

# Görünüm Ayarları
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class DualSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GIT ⇌ JIRA Operasyon Merkezi")
        self.geometry("1100x800")

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

        # --- 1. JQL GİRİŞ ALANI ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.input_label = ctk.CTkLabel(self.top_frame, text="JQL FİLTRESİ (Sadece Sol Taraf İçin):", font=("Roboto", 12, "bold"), text_color="gray")
        self.input_label.pack(anchor="w", pady=(0, 5))

        self.jql_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Örn: project = GYT", height=40, font=("Consolas", 14), border_width=0, fg_color="#D3D3D3")
        self.jql_entry.pack(fill="x")
        self.jql_entry.insert(0, "project = GYT AND created >= -1d")

        # --- 2. ANA BÖLÜNMÜŞ EKRAN ---
        self.split_container = ctk.CTkFrame(self, fg_color="transparent")
        self.split_container.pack(fill="both", expand=True, padx=20, pady=10)

        # ============ SOL PANEL (MAVİ) ============
        self.left_frame = ctk.CTkFrame(self.split_container, fg_color="#CEE3FA", corner_radius=15)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.lbl_left = ctk.CTkLabel(self.left_frame, text="  JIRA ➔ GITLAB", font=self.font_title, text_color="#2B709B", image=self.jira_icon, compound="left")
        self.lbl_left.pack(pady=(15, 10))

        # Mavi Buton (Önizleme)
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

        # --- DİNAMİK AKSİYON PANELİ (Onay, İptal, Progress, Temizle) ---
        self.action_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        
        # 1. Aşama Butonları
        self.btn_confirm_left = ctk.CTkButton(
            self.action_frame, text="✅ ONAYLA VE BAŞLAT",
            fg_color="#27AE60", hover_color="#1E8449",
            height=50, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.baslat_sol_thread_execute
        )
        
        self.btn_cancel_left = ctk.CTkButton(
            self.action_frame, text="❌ İPTAL",
            fg_color="#C0392B", hover_color="#922B21",
            height=50, width=100, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.islem_iptal_et
        )

        # 2. Aşama: Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.action_frame, height=20, corner_radius=10, progress_color="#27AE60")
        self.progress_bar.set(0) 

        self.progress_label = ctk.CTkLabel(self.action_frame, text="İşleniyor: 0%", font=("Roboto", 12))

        # 3. Aşama: Temizle ve Başa Dön Butonu
        self.btn_reset = ctk.CTkButton(
            self.action_frame, text="🔄 EKRANI TEMİZLE VE YENİ SORGU YAP",
            fg_color="#2980B9", hover_color="#1F618D", # Mavi Ton
            height=50, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.ekrani_sifirla
        )

        # ============ SAĞ PANEL (TURUNCU) ============
        self.right_frame = ctk.CTkFrame(self.split_container, fg_color="#F7E1C0", corner_radius=15)
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

    def setup_tags(self, textbox):
        textbox._textbox.tag_config("error", foreground="#FF5555")
        textbox._textbox.tag_config("success", foreground="#50FA7B")
        textbox._textbox.tag_config("warning", foreground="#FFB86C")
        textbox._textbox.tag_config("info", foreground="#8BE9FD")
        textbox._textbox.tag_config("dim", foreground="#8FA0D4")

    # --- DURUM YÖNETİMİ (STATE MANAGEMENT) ---
    def goster_onay_iptal(self):
        """Yeşil ve Kırmızı butonları gösterir."""
        self.action_frame.pack(fill="x", padx=15, pady=10)
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        self.btn_reset.pack_forget()
        
        self.btn_confirm_left.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_cancel_left.pack(side="right", padx=(5, 0))

    def goster_progress_bar(self):
        """Butonları kaldırır, sadece progress bar gösterir."""
        self.btn_confirm_left.pack_forget()
        self.btn_cancel_left.pack_forget()
        
        self.progress_label.pack(pady=(0, 5))
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_label.configure(text="Başlatılıyor...")

    def goster_reset_butonu(self):
        """İşlem bitince veya kayıt yoksa Mavi temizle butonunu gösterir."""
        self.action_frame.pack(fill="x", padx=15, pady=10) # Frame'i görünür yap
        self.btn_confirm_left.pack_forget()
        self.btn_cancel_left.pack_forget()
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        
        self.btn_reset.pack(fill="x", pady=0)

    # --- AKSİYONLAR ---
    def ekrani_sifirla(self):
        """Her şeyi siler, başa döner."""
        self.islem_iptal_et(silent=True) # Dosyaları sil
        self.console_left.delete("0.0", "end") # Konsolu temizle
        self.log_yaz(self.console_left, "✨ Ekran temizlendi. Yeni işlem için hazır.\n", "info")
        
        # Reset butonunu gizle, Mavi butonu aç
        self.action_frame.pack_forget()
        self.btn_left.configure(state="normal")
        self.jql_entry.configure(state="normal")

    def islem_iptal_et(self, silent=False):
        """Kullanıcı vazgeçerse her şeyi temizler."""
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
        self.action_frame.pack_forget() # Önceki butonlar varsa gizle

        t = threading.Thread(
            target=self.scripti_calistir, 
            args=("sync_to_gitlab.py", self.console_left, self.btn_left, "AKTARIMI BAŞLAT (ÖN İZLEME)", jql, "--preview", self.on_preview_complete)
        )
        t.start()

    def baslat_sol_thread_execute(self):
        jql = self.jql_entry.get() 
        self.btn_left.configure(state="disabled") # Üst butonu kilitle
        self.jql_entry.configure(state="disabled") # Giriş alanını kilitle

        # ARAYÜZ DEĞİŞİMİ: Butonlar gider, Progress Gelir
        self.goster_progress_bar()

        t = threading.Thread(
            target=self.scripti_calistir, 
            args=("sync_to_gitlab.py", self.console_left, None, "", jql, "--execute", self.on_execute_complete)
        )
        t.start()

    # --- CALLBACK FONKSİYONLARI ---
    def on_preview_complete(self, return_code, output_text):
        if return_code != 0:
            self.btn_left.configure(state="normal")
            self.action_frame.pack_forget()
            return

        # 0 issue durumu veya tamamen güncel durumu kontrolü
        is_empty = ("Aktarılacak toplam 0 issue tespit edildi" in output_text or 
                    "Aktarılacak yeni kayıt bulunamadı" in output_text or 
                    "Tüm issue'lar zaten güncel" in output_text)

        if is_empty:
            self.log_yaz(self.console_left, "\nℹ️ Aktarılacak yeni kayıt bulunamadı.\n", "warning")
            # --- DÜZELTME BURADA ---
            self.goster_reset_butonu() # Reset butonunu göster
            self.btn_left.configure(state="disabled") # Mavi butonu kilitli tut (Reset'e zorla)
        
        elif "Gitlab'e aktarılacak toplam" in output_text:
            self.goster_onay_iptal() # Onay butonlarını aç
            self.log_yaz(self.console_left, "\n⬇️ Lütfen işlemi ONAYLAYIN veya İPTAL edin.\n", "success")
            self.btn_left.configure(state="normal")

    def on_execute_complete(self, return_code, output_text):
        # İşlem bitince Progress gider, Reset butonu gelir
        self.goster_reset_butonu()
        
        if return_code == 0:
             self.log_yaz(self.console_left, "\n✅ Tüm aktarım tamamlandı.\n", "success")
             self.progress_label.configure(text="Tamamlandı: 100%")
             self.progress_bar.set(1)

    # --- THREAD İŞLEMLERİ (SAĞ TARAF) ---
    def baslat_sag_thread(self):
        self.btn_right.configure(state="disabled", text="⏳ GİTLAB BAĞLANIYOR...")
        self.console_right.delete("0.0", "end")
        t = threading.Thread(target=self.scripti_calistir, args=("sync_gitlab_status_to_jira.py", self.console_right, self.btn_right, "STATÜLERİ GÜNCELLE"))
        t.start()

    # --- GENEL ÇALIŞTIRICI ---
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

            # --- REGEX DESENİ (Progress Hesaplamak için) ---
            progress_pattern = re.compile(r"--- (\d+)/(\d+):")

            for line in process.stdout: 
                self.akilli_log_yaz(target_console, line)
                full_output += line
                
                # --- Progress Bar Güncelleme ---
                if mode_flag == "--execute":
                    match = progress_pattern.search(line)
                    if match:
                        current = int(match.group(1))
                        total = int(match.group(2))
                        if total > 0:
                            percent = current / total
                            self.progress_bar.set(percent)
                            self.progress_label.configure(text=f"İşleniyor: {current}/{total} (%{int(percent*100)})")

            for line in process.stderr: 
                self.log_yaz(target_console, f"⚠️ {line}", "warning")

            process.wait()
            
            # Execute modunda değilse butonu aç
            if mode_flag != "--execute" and target_btn:
                self.btn_left.configure(state="normal")

            if callback:
                self.after(100, lambda: callback(process.returncode, full_output))

        except Exception as e: 
            self.log_yaz(target_console, f"\n❌ Kritik Hata: {e}\n", "error")
            if target_btn: target_btn.configure(state="normal")
        finally: 
            if target_btn and mode_flag != "--execute":
                target_btn.configure(state="normal", text=btn_reset_text)

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