import customtkinter as ctk
import subprocess
import threading
import sys
import os
from PIL import Image

# Görünüm Ayarları
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class DualSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GIT ⇌ JIRA Operasyon Merkezi")
        self.geometry("1100x750")

        self.font_title = ("Roboto Medium", 20)
        self.font_console = ("JetBrains Mono", 12)

        # --- RESİM VE KLASÖR AYARLARI ---
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Resimlerin olduğu klasör: "LOGOLAR"
        logo_folder = os.path.join(current_dir, "logo")

        # Yardımcı Fonksiyon: Resmi Yükle ve Beyaz Arkplanı Sil
        def load_and_clean_image(filename):
            try:
                path = os.path.join(logo_folder, filename)
                if not os.path.exists(path):
                    print(f"⚠️ Dosya bulunamadı: {path}")
                    return None
                
                # Resmi aç ve RGBA (Şeffaflık destekli) moduna çevir
                img = Image.open(path).convert("RGBA")
                
                # --- OTOMATİK BEYAZ SİLME (Magic Eraser) ---
                data = img.getdata()
                new_data = []
                for item in data:
                    # Eğer piksel çok beyazsa (R,G,B > 220), onu şeffaf yap (Alpha=0)
                    if item[0] > 220 and item[1] > 220 and item[2] > 220:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                img.putdata(new_data)
                # -------------------------------------------

                return ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
            except Exception as e:
                print(f"Resim işleme hatası ({filename}): {e}")
                return None

        # 1. Logoları Yükle
        # Dosya isimlerinin klasördekiyle AYNI olduğundan emin ol!
        self.jira_icon = load_and_clean_image("jira-software-logo.png")
        self.git_icon = load_and_clean_image("gitlab-logo.png")

        # --- 1. JQL GİRİŞ ALANI ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.input_label = ctk.CTkLabel(self.top_frame, text="JQL FİLTRESİ (Sadece Sol Taraf İçin):", font=("Roboto", 12, "bold"), text_color="gray")
        self.input_label.pack(anchor="w", pady=(0, 5))

        self.jql_entry = ctk.CTkEntry(
            self.top_frame, 
            placeholder_text="Örn: project = GYT AND created >= -15d", 
            height=40, font=("Consolas", 14), border_width=0, fg_color="#D3D3D3"   #"#2B2B2B"
        )
        self.jql_entry.pack(fill="x")
        self.jql_entry.insert(0, "project = GYT AND created >= -1d")

        # --- 2. ANA BÖLÜNMÜŞ EKRAN ---
        self.split_container = ctk.CTkFrame(self, fg_color="transparent")
        self.split_container.pack(fill="both", expand=True, padx=20, pady=10)

        # ============ SOL PANEL (MAVİ - JIRA TO GITLAB) ============
        self.left_frame = ctk.CTkFrame(self.split_container, fg_color="#CEE3FA", corner_radius=15)  ##181818
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.lbl_left = ctk.CTkLabel(
            self.left_frame, 
            text="  JIRA ➔ GITLAB",
            font=self.font_title, 
            text_color="#2B709B",  #4BADE8
            image=self.jira_icon, 
            compound="left"
        )
        self.lbl_left.pack(pady=(15, 10))

        self.btn_left = ctk.CTkButton(
            self.left_frame, text="AKTARIMI BAŞLAT", 
            fg_color="#0065FF", hover_color="#0747A6",
            height=50, corner_radius=10, font=("Roboto", 14, "bold"),
            command=self.baslat_sol_thread
        )
        self.btn_left.pack(fill="x", padx=15, pady=10)

        self.console_left = ctk.CTkTextbox(self.left_frame, font=self.font_console, fg_color="#0f0f0f", text_color="#D4D4D4", corner_radius=10)
        self.console_left.pack(fill="both", expand=True, padx=10, pady=10)
        self.setup_tags(self.console_left)
        self.console_left.insert("0.0", "Hazır. Jira verilerini çekmek için MAVİ butona basın.\n", "dim")

        # ============ SAĞ PANEL (TURUNCU - GITLAB TO JIRA) ============
        self.right_frame = ctk.CTkFrame(self.split_container, fg_color="#F7E1C0", corner_radius=15)  ##181818
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.lbl_right = ctk.CTkLabel(
            self.right_frame, 
            text="  GITLAB ➔ JIRA",
            font=self.font_title, 
            text_color="#E67E22",
            image=self.git_icon, 
            compound="left"
        )
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

    # --- THREAD İŞLEMLERİ ---
    def baslat_sol_thread(self):
        jql = self.jql_entry.get()
        if not jql.strip():
            self.log_yaz(self.console_left, "⚠️ HATA: JQL boş olamaz!\n", "error")
            return
        self.btn_left.configure(state="disabled", text="⏳ JIRA BAĞLANIYOR...")
        self.console_left.delete("0.0", "end")
        t = threading.Thread(target=self.scripti_calistir, args=("sync_to_gitlab.py", self.console_left, self.btn_left, "AKTARIMI BAŞLAT", jql))
        t.start()

    def baslat_sag_thread(self):
        self.btn_right.configure(state="disabled", text="⏳ GİTLAB BAĞLANIYOR...")
        self.console_right.delete("0.0", "end")
        t = threading.Thread(target=self.scripti_calistir, args=("sync_gitlab_status_to_jira.py", self.console_right, self.btn_right, "STATÜLERİ GÜNCELLE"))
        t.start()

    def scripti_calistir(self, script_name, target_console, target_btn, btn_reset_text, arguman=None):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, script_name)
            python_exe = sys.executable

            self.log_yaz(target_console, f"📂 Script: {script_name}\n", "dim")
            if arguman: self.log_yaz(target_console, f"📡 JQL: {arguman}\n", "info")

            if not os.path.exists(script_path):
                self.log_yaz(target_console, f"❌ HATA: {script_name} bulunamadı!\n", "error")
                return

            cmd = [python_exe, "-u", script_path]
            if arguman: cmd.append(arguman)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, cwd=current_dir, encoding='utf-8', errors='replace', env=env)

            for line in process.stdout: self.akilli_log_yaz(target_console, line)
            for line in process.stderr: self.log_yaz(target_console, f"⚠️ {line}", "warning")

            process.wait()
            if process.returncode == 0: self.log_yaz(target_console, "\n✅ İŞLEM BAŞARIYLA TAMAMLANDI.\n", "success")
            else: self.log_yaz(target_console, f"\n❌ Hata Kodu: {process.returncode}\n", "error")

        except Exception as e: self.log_yaz(target_console, f"\n❌ Kritik Hata: {e}\n", "error")
        finally: target_btn.configure(state="normal", text=btn_reset_text)

    def akilli_log_yaz(self, console, line):
        tag = "normal"
        if "❌" in line or "Hata" in line or "Error" in line: tag = "error"
        elif "⚠️" in line or "Uyarı" in line: tag = "warning"
        elif "✅" in line or "Başarılı" in line or "Tamamlandı" in line: tag = "success"
        elif "🆕" in line or "✨" in line or "Info" in line: tag = "info"
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