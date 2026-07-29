# התקנה והרצה

## דרישות

| רכיב | גרסה | הערה |
|---|---|---|
| Python | 3.12+ | נדרש `StrEnum` ו-`datetime.UTC` |
| Node.js | 20+ | פותח ונבדק על 24 |

אין תלות בענן, אין Docker, אין שירותים חיצוניים.

---

## התקנה — פיתוח

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements-dev.txt
```

### 2. יצירת נתוני הדגמה

הרפוזיטורי כולל 28 ימי נתונים סינתטיים. ליצירה מחדש או להיסטוריה ארוכה יותר:

```bash
cd ..
python scripts/generate_seed.py --days 28
```

הנתונים דטרמיניסטיים לפי `--seed`, כך שאותה פקודה מפיקה תמיד את אותו מערך.

### 3. Frontend

```bash
cd frontend
npm install
```

---

## הרצה

שני מסופים:

```bash
# מסוף 1 — API על 8000
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload

# מסוף 2 — UI על 5173
cd frontend
npm run dev
```

פתח <http://localhost:5173>. שרת הפיתוח מעביר `/api` ל-8000, כך שהדפדפן מדבר עם
origin אחד — אותה צורה כמו בייצור.

תיעוד API אינטראקטיבי: <http://localhost:8000/api/docs>

---

## בנייה לייצור

```bash
cd frontend
npm run build          # מייצר frontend/dist

cd ../backend
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI מזהה את `frontend/dist` ומגיש אותו. **שירות אחד, פורט אחד** — הכול
זמין ב-<http://localhost:8000>.

---

## קונפיגורציה

כל המשתנים בתחילית `SERVIZON_`. ניתן להגדיר ב-`backend/.env` (ראה
`.env.example`).

| משתנה | ברירת מחדל | תיאור |
|---|---|---|
| `SERVIZON_DATA_SOURCE` | `csv` | `csv` או `sql` |
| `SERVIZON_SEED_DIR` | `backend/data/seed` | נתיב קובצי ה-CSV |
| `SERVIZON_DATABASE_URL` | SQLite מקומי | כל URL של SQLAlchemy |
| `SERVIZON_SCENARIOS_DATABASE_URL` | SQLite מקומי | אחסון תרחישים, תמיד נפרד |
| `SERVIZON_REFRESH_MINUTES` | `3` | תדירות רענון הנתונים |
| `SERVIZON_HOST` / `SERVIZON_PORT` | `127.0.0.1` / `8000` | |
| `SERVIZON_LOG_LEVEL` | `INFO` | |

---

## מעבר ל-SQL

```bash
# טעינת ה-CSV למסד מקומי לצורך בדיקה
python scripts/load_sql.py

# או ישירות למסד ייצור
python scripts/load_sql.py --url "mssql+pyodbc://user:pw@host/db?driver=ODBC+Driver+18+for+SQL+Server"
```

ואז:

```bash
SERVIZON_DATA_SOURCE=sql
SERVIZON_DATABASE_URL=<ה-URL שלך>
```

`SqlRepository` משתמש ב-SELECT פשוטים דרך SQLAlchemy Core, ולכן עובד מול
SQL Server, PostgreSQL, Oracle ו-SQLite ללא שינוי קוד.

---

## בדיקות

```bash
cd backend
.venv\Scripts\python -m pytest -q            # 109 בדיקות
.venv\Scripts\python -m pytest --cov=app     # עם כיסוי
```

```bash
cd frontend
npx tsc -b          # בדיקת טיפוסים
npm run lint
npm run build
```

---

## פתרון תקלות

**`Seed file not found`** — הרץ `python scripts/generate_seed.py`.

**`503 — הנתונים עדיין נטענים`** — הרענון הראשון עדיין רץ. שניות ספורות.

**המסך ריק, שגיאות רשת בקונסול** — ה-backend לא עלה. בדוק
<http://localhost:8000/api/health>.

**עברית מוצגת כריבועים** — הפונט לא נטען. ודא ש-`frontend/public/fonts/`
מכיל את קובצי ה-woff2. ליצירה מחדש: `python scripts/vendor_fonts.py`
(דורש אינטרנט; להרצה **לפני** ההעברה לרשת הסגורה).

**`git add` מנסה להוסיף את כל תיקיית הבית** — אתה מריץ מחוץ לרפוזיטורי הפרויקט.
ודא ש-`git rev-parse --show-toplevel` מצביע על תיקיית הפרויקט.
