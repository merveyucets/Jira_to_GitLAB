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
TEAM_PROJECT_MAP = json.loads(os.getenv("TEAM_PROJECT_MAP", "{}"))
GROUP_ID = os.getenv("GROUP_ID")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# --- ARGÜMAN YÖNETİMİ ---
JQL = "project = GYT AND created >= -15d"
MODE = "--preview"

if len(sys.argv) > 1:
    JQL = sys.argv[1]
    
if len(sys.argv) > 2:
    MODE = sys.argv[2]

HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN,
    "Content-Type": "application/json"
}

# --- Assignee Map ---
ASSIGNEE_MAP = {
    "merve.yucetas": 31250282,
    "affan.bugra.ozaytas": 31073378,
    "burak.kiraz": 31073379,
}

# --- Stajyer Map (Kullanıcı -> Proje ID) ---
STAJYER_PROJECT_MAP = {
    "affan.bugra.ozaytas": TEAM_PROJECT_MAP.get("GYT Test ve Otomasyon"),
    "merve.yucetas": TEAM_PROJECT_MAP.get("GYT Proje Yönetimi"),
    "burak.kiraz": TEAM_PROJECT_MAP.get("GYT Simülasyon")
}

# --- YENİ: Ters Harita (Kullanıcı -> Takım İsmi) ---
# Ekrana güzel yazdırmak için kullanacağız.
STAJYER_NAME_MAP = {
    "affan.bugra.ozaytas": "GYT Test ve Otomasyon",
    "merve.yucetas": "GYT Proje Yönetimi",
    "burak.kiraz": "GYT Simülasyon"
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
                
                issue["_stajyer_list"] = list(set(stajyer_list_raw))
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

def get_readable_team_names(stajyer_list):
    """Kullanıcı adlarını Takım İsimlerine çevirir."""
    readable_list = []
    for s in stajyer_list:
        # Haritada varsa takım ismini al, yoksa olduğu gibi kullanıcı adını yaz
        team_name = STAJYER_NAME_MAP.get(s, s)
        readable_list.append(team_name)
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
            stajyerler = row.get("_stajyer_list", [])
            
            # --- YENİ: Takım İsimlerini Dönüştür ---
            takim_isimleri = get_readable_team_names(stajyerler)
            
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
            
            stajyerler = row.get("_stajyer_list", [])
            
            # --- YENİ: Takım İsimlerini Dönüştür ---
            takim_isimleri = get_readable_team_names(stajyerler)
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
            for stajyer in stajyerler:
                proj_id = STAJYER_PROJECT_MAP.get(stajyer)
                if not proj_id:
                    print(f"  ⚠️  -> '{stajyer}' için Proje ID bulunamadı.")
                    continue
                
                c_assignee = ASSIGNEE_MAP.get(stajyer)
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
                    # Buradaki print'i de güzelleştirelim (Proje adı zaten var ama olsun)
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