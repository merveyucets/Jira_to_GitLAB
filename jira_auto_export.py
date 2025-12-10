import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
CSV_FOLDER = "csv_folder"
LATEST_FILE = os.path.join(CSV_FOLDER, "jira_latest.csv")

def fetch_jira_csv(gelen_jql):
    start_at = 0
    max_results = 100
    all_issues = []

    JQL = gelen_jql
    print(f"Jira Sorgusu Çalıştırılıyor")
    
    
    headers = {
        "Authorization": f"Bearer {JIRA_API_TOKEN}",
        "Accept": "application/json"
    }

    while True:
        url = f"{JIRA_URL}/rest/api/2/search"
        response = requests.get(
            url,
            params={
                "jql": JQL,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": [
                    "summary",
                    "description",
                    "assignee",
                    "reporter",
                    "priority",
                    "status",
                    "duedate",
                    "issuetype",
                    "project",
                    "labels",
                    "timeoriginalestimate",
                    "timespent",
                    "customfield_10601"
                ]
            },
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Jira API Hatası: {response.status_code} {response.text}")
            return

        data = response.json()
        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            fields = issue.get("fields", {})
            row = {
                "Summary": fields.get("summary"),
                "Issue key": issue.get("key"),
                "Issue id": issue.get("id"),
                "Issue Type": fields.get("issuetype", {}).get("name"),
                "Status": fields.get("status", {}).get("name"),
                "Project key": fields.get("project", {}).get("key"),
                "Project name": fields.get("project", {}).get("name"),
                "Priority": fields.get("priority", {}).get("name") if fields.get("priority") else "",
                "Assignee": fields.get("assignee", {}).get("name") if fields.get("assignee") else "",
                "Reporter": fields.get("reporter", {}).get("name") if fields.get("reporter") else "",
                "Description": fields.get("description") or "",
                "Due Date": fields.get("duedate") or "",
                "Original Estimate": fields.get("timeoriginalestimate"),
                "Time Spent": fields.get("timespent"),
                "Labels": ",".join(fields.get("labels", [])),
                "İlgili Stajyerler": ",".join([u.get("name") for u in fields.get("customfield_10601", [])]) if fields.get("customfield_10601") else ""
            }
            all_issues.append(row)

        start_at += max_results
        if start_at >= data.get("total", 0):
            break
     
     # Klasör yoksa oluştur
    if not os.path.exists(CSV_FOLDER):
        os.makedirs(CSV_FOLDER)
        print(f"🆕 '{CSV_FOLDER}' klasörü oluşturuldu (boş).")

    file_existed_before_write = os.path.exists(LATEST_FILE) # <--- YENİ SATIR: Dosya var mıydı?

    # Jira'dan gelen tüm kolon adlarının listesi
    JIRA_COLUMNS = [
        "Summary", "Issue key", "Issue id", "Issue Type", "Status", "Project key", 
        "Project name", "Priority", "Assignee", "Reporter", "Description", 
        "Due Date", "Original Estimate", "Time Spent", "Labels", "İlgili Stajyerler"
    ]
    
    issue_count = len(all_issues)
    
    if issue_count > 0:
        df = pd.DataFrame(all_issues)
        print(f"✅ Jira'dan sorgu ile eşleşen --{issue_count}-- issue çekildi.")
    else:
        # Hata vermemek için boş başlık satırı oluşturulur.
        df = pd.DataFrame(columns=JIRA_COLUMNS)
        
    df.to_csv(LATEST_FILE, index=False, encoding="utf-8-sig")
        
    # --- YENİ ÇIKTI KONTROLÜ ---
    if not file_existed_before_write :  #and issue_count == 0
        # 1. Durum: Dosya hiç yoktu VE içi boş yazıldı.
        print(f"🆕 '{LATEST_FILE}' oluşturuldu (boş).")
    else:
        # 2. Durum: Dosya vardı VEYA içi dolu yazıldı (Normal güncelleme).
        print(f"✅ --{issue_count}-- Issue Latest CSV'ye eklendi.")
    
    # ÖNEMLİ: Bulunan issue sayısını geri döndür
    return issue_count