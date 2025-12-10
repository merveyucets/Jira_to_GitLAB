import csv
import requests
import pandas as pd
import os
from dateutil import parser
from dotenv import load_dotenv
from jira_auto_export import fetch_jira_csv
from compare_issues import compare_issues
import sys
import json

# .env dosyasını yükle
load_dotenv()

# --- .ENV DEĞİŞKENLERİ ---
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
MASTER_PROJECT_ID = os.getenv("MASTER_PROJECT_ID")
GROUP_ID = os.getenv("GROUP_ID")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# --- KONFİGÜRASYON VE MAP DEĞİŞKENLERİ ---
CONFIG_FILE = "config.json"

# Bu değişkenler load_config() ile doldurulacak
ASSIGNEE_MAP = {}         # { "jira_user": gitlab_user_id }
TEAM_PROJECT_MAP = {}     # { "jira_team_name": gitlab_project_id }
TEAM_NAME_MAP = {}        # { "jira_team_name": "Görünür İsim" }

JQL = "project = GYT AND created >= -15d" # Varsayılan

def load_config():
    """config.json dosyasını okur ve MAP değişkenlerini doldurur (Ayrıştırılmış Yapı)."""
    global ASSIGNEE_MAP, TEAM_PROJECT_MAP, TEAM_NAME_MAP, JQL
    
    if not os.path.exists(CONFIG_FILE):
        print(f"⚠️ UYARI: {CONFIG_FILE} bulunamadı! Varsayılan ayarlar kullanılacak.")
        return

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 1. JQL Ayarını Çek
        if "settings" in data and "default_jql" in data["settings"]:
            if len(sys.argv) <= 1: 
                JQL = data["settings"]["default_jql"]
                print(f"⚙️ Config dosyasından JQL yüklendi: {JQL}")

        # 2. User Mappings (Kişi Eşleşmeleri)
        if "user_mappings" in data:
            for item in data["user_mappings"]:
                j_user = item.get("jira_user")
                g_user_id = item.get("gitlab_user_id")
                
                if j_user and g_user_id:
                    ASSIGNEE_MAP[j_user] = g_user_id

        # 3. Team Mappings (Takım Eşleşmeleri)
        if "team_mappings" in data:
            for item in data["team_mappings"]:
                j_team = item.get("jira_team_name")
                g_proj_id = item.get("gitlab_project_id")
                f_name = item.get("friendly_name")

                if j_team:
                    if g_proj_id: TEAM_PROJECT_MAP[j_team] = g_proj_id
                    if f_name: TEAM_NAME_MAP[j_team] = f_name
            
        print("✅ Ayarlar ve veriler config dosyasından başarıyla yüklendi.")

    except Exception as e:
        print(f"❌ Config yükleme hatası: {e}")

# --- YÜKLEMEYİ BAŞLAT ---
load_config()

# --- ARGÜMAN YÖNETİMİ ---
if len(sys.argv) > 1:
    JQL = sys.argv[1]

MODE = "--preview"
if len(sys.argv) > 2:
    MODE = sys.argv[2]

HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN,
    "Content-Type": "application/json"
}

# CSV DOSYA YOLLARI
CSV_FOLDER = "csv_folder"
TO_ADD_FILE = os.path.join(CSV_FOLDER, "jira_to_add.csv")
UPLOADED_FILE = os.path.join(CSV_FOLDER, "jira_uploaded.csv")

# ------------------- ROBUST CSV OKUYUCU -------------------
def read_jira_csv_robustly(filename):
    issues = []
    try:
        with open(filename, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]
            # Jira'da takım bilgisi şu an "İlgili Stajyerler" alanından geliyor
            stajyer_indices = [i for i, col_name in enumerate(header) if "İlgili Stajyerler" in col_name]

            for row_data in reader:
                issue = {}
                stajyer_list_raw = []
                for idx in stajyer_indices:
                    if idx < len(row_data):
                        val = row_data[idx].strip()
                        if val:
                            stajyer_list_raw.extend([s.strip() for s in val.split(",") if s.strip()])
                
                for h, v in zip(header, row_data):
                    issue[h.strip()] = v.strip()
                
                # Burada _stajyer_list aslında mantıksal olarak "Takım Listesi"dir.
                issue["_team_list"] = list(set(stajyer_list_raw))
                issues.append(issue)
                
    except FileNotFoundError:
        print(f"❌ Hata: '{filename}' dosyası bulunamadı.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Hata: CSV okunamadı. Hata: {e}")
        sys.exit(1)
    return issues

# ------------------- YARDIMCI FONKSİYONLAR -------------------
def parse_date(date_str):
    if not date_str: return None
    try: return parser.parse(date_str).strftime("%Y-%m-%d")
    except: return None

def seconds_to_gitlab_duration(seconds):
    if not seconds: return None
    try: sec = int(float(seconds))
    except: return None
    if sec <= 0: return None
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    parts = []
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "0m"

def link_issues(parent_project_id, parent_iid, target_project_id, target_iid):
    url = f"https://gitlab.com/api/v4/projects/{parent_project_id}/issues/{parent_iid}/links"
    data = {"target_project_id": target_project_id, "target_issue_iid": target_iid, "link_type": "relates_to"}
    requests.post(url, headers=HEADERS, json=data)

def find_or_create_group_milestone(title):
    url = f"https://gitlab.com/api/v4/groups/{GROUP_ID}/milestones"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        for m in r.json():
            if m["title"].strip().lower() == title.strip().lower():
                return m
    payload = {"title": title}
    r = requests.post(url, headers=HEADERS, json=payload)
    if r.status_code == 201:
        print(f"✨ Issue Milestone'u oluşturuldu: {title}")
        return r.json()
    return None

def get_readable_team_names(team_list):
    """Takım kodlarını (şimdilik kullanıcı adı) Okunabilir Takım İsimlerine çevirir."""
    readable_list = []
    for t in team_list:
        readable_list.append(TEAM_NAME_MAP.get(t, t))
    return readable_list

# ==============================================================================
#                             ANA BLOK
# ==============================================================================
if __name__ == "__main__":
    
    # ------------------ MOD 1: PREVIEW (ÖN İZLEME) ------------------
    if MODE == "--preview":
        print(f"📡 Arayüzden Gelen JQL Kullanılıyor: {JQL}")
        
        try:
            test_resp = requests.get(f"{JIRA_URL}/rest/api/2/myself", headers={"Authorization": f"Bearer {JIRA_API_TOKEN}"})
            if test_resp.status_code == 200: print("✅ Jira API Bağlantısı Başarılı.")
        except: pass

        new_issue_count = fetch_jira_csv(JQL)
        
        if new_issue_count == 0:
            print("\n---------------------------------------------------------")
            print("🛑 Sorgu sonucunda JIRA'dan hiç veri dönmedi veya hata oluştu.")
            print("---------------------------------------------------------")
            sys.exit(0)

        compare_issues()
        
        if not os.path.exists(TO_ADD_FILE):
             print("⚠️ Eklenecek dosya bulunamadı.")
             sys.exit(0)

        rows = read_jira_csv_robustly(TO_ADD_FILE)
        count = len(rows)
        
        if count == 0:
            print("\n✅ Tüm issue'lar zaten güncel. Yeni aktarılacak kayıt yok.")
            sys.exit(0)

        print(f"\nGitlab'e aktarılacak toplam {count} issue tespit edildi.\n")
        
        for i, row in enumerate(rows, start=1):
            jira_key = row.get("Issue key", "")
            summary = row.get("Summary", "")
            teams = row.get("_team_list", []) # Artık _team_list kullanıyoruz
            
            takim_isimleri = get_readable_team_names(teams)
            
            print(f"--- {i}/{count}: {jira_key} - {summary} ---")
            print(f"➡️  Tespit Edilen Takımlar: {', '.join(takim_isimleri) if takim_isimleri else 'Yok'}\n")
            
        print("✅ ÖN İZLEME TAMAMLANDI. Devam etmek için 'AKTARIMI ONAYLA' butonuna basın.")

    # ------------------ MOD 2: EXECUTE (GERÇEKLEŞTİRME) ------------------
    elif MODE == "--execute":
        
        if not os.path.exists(TO_ADD_FILE):
             print("❌ HATA: Önce sorgulama yapmalısınız (jira_to_add.csv yok).")
             sys.exit(1)
             
        rows = read_jira_csv_robustly(TO_ADD_FILE)
        count = len(rows)
        
        if count == 0:
            print("⚠️ Aktarılacak issue bulunamadı.")
            sys.exit(0)

        print(f"🚀 Aktarım Başlıyor... Toplam {count} kayıt işlenecek.\n")
        synced_count = 0

        for i, row in enumerate(rows, start=1):
            title = (row.get("Summary") or "Untitled").strip()
            jira_key = row.get("Issue key") or ""
            
            print(f"\n--- {i}/{count}: İşleniyor {jira_key} - {title} ---")
            
            teams = row.get("_team_list", [])
            
            takim_isimleri = get_readable_team_names(teams)
            print(f"➡️  Tespit Edilen Takımlar: {', '.join(takim_isimleri) if takim_isimleri else 'Yok'}")
            
            # --- VERİ HAZIRLIĞI ---
            orig_desc = (row.get("Description") or "").strip()
            labels = [l for l in [jira_key, row.get("Priority")] if l]
            if row.get("Labels"): labels += [x.strip() for x in row["Labels"].split(",") if x.strip()]
            labels_str = ",".join(labels)
            
            due_date = parse_date(row.get("Due Date"))
            orig_est = seconds_to_gitlab_duration(row.get("Original Estimate"))
            time_spent = seconds_to_gitlab_duration(row.get("Time Spent"))
            
            desc_prefix = (
                f"**Jira Bilgileri**\n- Key: {jira_key}\n"
                f"**Zaman:**\n- Tahmin: {orig_est or 'N/A'}\n- Harcanan: {time_spent or 'N/A'}\n"
                f"**Bitiş:** {due_date or 'N/A'}\n\n--- Orijinal Açıklama ---\n\n"
            )
            full_desc = desc_prefix + orig_desc

            # --- 1. Milestone ---
            milestone = find_or_create_group_milestone(title)
            
            # --- 2. Master Issue ---
            # Assignee mapping, artık sadece USER MAP üzerinden yapılır
            assignee_id = ASSIGNEE_MAP.get(row.get("Assignee"))
            
            master_data = {
                "title": title, "description": full_desc, "labels": labels_str,
                "time_estimate": orig_est, "spent_time": time_spent
            }
            if due_date: master_data["due_date"] = due_date
            if assignee_id: master_data["assignee_ids"] = [assignee_id]
            if milestone: master_data["milestone_id"] = milestone["id"]
            
            m_resp = requests.post(f"https://gitlab.com/api/v4/projects/{MASTER_PROJECT_ID}/issues", headers=HEADERS, json=master_data)
            
            if m_resp.status_code == 201:
                m_issue = m_resp.json()
                m_iid = m_issue["iid"]
                print(f"✅ Ana Issue Oluşturuldu: {title}")
            else:
                print(f"❌ Master issue oluşturulamadı: {m_resp.text}")
                continue 
            
            # --- 3. Child Issues ---
            for team in teams:
                # Proje ID'si artık TEAM MAP üzerinden alınıyor
                proj_id = TEAM_PROJECT_MAP.get(team)
                
                if not proj_id:
                    print(f"  ⚠️  -> '{team}' takımı için Proje ID bulunamadı.")
                    continue
                
                # Child Assignee mantığı:
                # Şu anki geçici sistemde takım adı = kişi adı olduğu için, ASSIGNEE_MAP'ten de bakabiliriz.
                # İleride gerçek takım adları gelince, Child issue'ya kim atanacak?
                # Şimdilik takım adı ile aynı isimde bir kullanıcı varsa onu atayalım (Eski mantıkla uyumlu)
                c_assignee = ASSIGNEE_MAP.get(team) 
                
                c_desc = f"**Ana Issue:** {m_issue['web_url']}\n\n{full_desc}"
                
                try: p_name = requests.get(f"https://gitlab.com/api/v4/projects/{proj_id}", headers=HEADERS).json().get("name", "Team")
                except: p_name = "Team"

                c_data = {
                    "title": f"{title} ({p_name})", "description": c_desc, "labels": labels_str,
                    "time_estimate": orig_est, "spent_time": time_spent
                }
                if due_date: c_data["due_date"] = due_date
                if c_assignee: c_data["assignee_ids"] = [c_assignee]
                if milestone: c_data["milestone_id"] = milestone["id"]

                c_resp = requests.post(f"https://gitlab.com/api/v4/projects/{proj_id}/issues", headers=HEADERS, json=c_data)
                
                if c_resp.status_code == 201:
                    c_iid = c_resp.json()["iid"]
                    link_issues(int(MASTER_PROJECT_ID), m_iid, proj_id, c_iid)
                    print(f"  ✅ -> Child Issue Oluşturuldu ({p_name}) ve linklendi.")
                else:
                    print(f"  ⚠️ Child Issue hatası: {c_resp.status_code}")

            # --- 4. CSV Güncelle ---
            if os.path.exists(UPLOADED_FILE) and os.path.getsize(UPLOADED_FILE) > 0:
                udf = pd.read_csv(UPLOADED_FILE, encoding="utf-8-sig")
            else:
                udf = pd.DataFrame(columns=row.keys())
            
            if not ((udf.get('Issue key') == row['Issue key']).any()):
                udf = pd.concat([udf, pd.DataFrame([row])], ignore_index=True)
                udf.to_csv(UPLOADED_FILE, index=False, encoding="utf-8-sig")
                print(f"✔️  '{jira_key}' uploaded CSV'ye eklendi.")
                synced_count += 1
        
        print(f"\n✅ SÜREÇ TAMAMLANDI. Toplam {synced_count} issue aktarıldı.\n")