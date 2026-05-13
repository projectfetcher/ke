# ════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Install dependencies
# ════════════════════════════════════════════════════════════════════════════
import subprocess, sys

def pip(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])

print("📦 Installing dependencies…")
pip(
    "pandas",
    "requests",
    "sentence-transformers",
    "language-tool-python==2.7.1",
    "nltk",
)
print("✅ Dependencies installed.\n")


# ════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Imports
# ════════════════════════════════════════════════════════════════════════════
import os, re, time, base64, hashlib, logging, warnings, io
from datetime import datetime

import pandas as pd
import requests
import nltk
from sentence_transformers import SentenceTransformer, util
import language_tool_python

warnings.filterwarnings("ignore")

for _resource, _name in [
    ("tokenizers/punkt_tab",               "punkt_tab"),
    ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
]:
    try:
        nltk.data.find(_resource)
    except LookupError:
        nltk.download(_name, quiet=True)

# ── Logging ──────────────────────────────────────────────────────────────────
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)
_root_logger.handlers.clear()

_fh = logging.FileHandler("debug.log")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_root_logger.addHandler(_fh)

_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_root_logger.addHandler(_ch)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Mistral API setup  ← replaces local GGUF model entirely
# ════════════════════════════════════════════════════════════════════════════

MISTRAL_API_KEY = "cmQo3yPkhr8gmJUsV7Mr3wltVBNAHGwU"   # ← paste your key here
MISTRAL_MODEL   = "mistral-small-latest"         # free tier model
MISTRAL_URL     = "https://api.mistral.ai/v1/chat/completions"

def mistral_generate(prompt: str, max_tokens: int = 400, temperature: float = 0.7) -> str:
    """Call Mistral API and return the generated text."""
    try:
        response = requests.post(
            MISTRAL_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       MISTRAL_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  max_tokens,
                "temperature": temperature,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        return ""

print("✅ Mistral API configured — no model download needed.\n")


# ════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Configuration
# ════════════════════════════════════════════════════════════════════════════

SHEET_ID  = "1z5sCu0wTBkDSHJRWoMZ1jlNd0ExJodzgb7jj4F0XZe0"
SHEET_GID = "0"

WP_BASE         = "https://kenya.mimusjobs.com/wp-json/wp/v2"
WP_URL          = f"{WP_BASE}/job-listings"
WP_COMPANY_URL  = f"{WP_BASE}/companies"
WP_MEDIA_URL    = f"{WP_BASE}/media"
WP_USERNAME     = "calolina"
WP_APP_PASSWORD = "2IJ6 DRql ivkQ uH19 h9cG Zide"

PROCESSED_IDS_FILE = "kenya_processed_job_ids.csv"

JOB_TYPE_MAPPING = {
    "full-time":  "full-time",  "full time":  "full-time",  "fulltime":    "full-time",
    "part-time":  "part-time",  "part time":  "part-time",  "parttime":    "part-time",
    "contract":   "contract",   "contractor": "contract",   "contracting": "contract",
    "temporary":  "temporary",  "temp":       "temporary",
    "freelance":  "freelance",
    "internship": "internship", "intern":     "internship",
    "volunteer":  "volunteer",
}


# ════════════════════════════════════════════════════════════════════════════
#  STEP 5 — Column definitions
# ════════════════════════════════════════════════════════════════════════════

APPSCRIPT_COLUMNS = [
    "Job Title", "Job Type", "Job Qualifications", "Job Experience",
    "Job Location", "Job Field", "Date Posted", "Deadline",
    "Job Description", "Application", "Company URL", "Company Name",
    "Company Logo", "Company Industry", "Company Founded", "Company Type",
    "Company Website", "Company Address", "Company Details", "Job URL",
    "Estimated Deadline", "Salary Range",
]


# ════════════════════════════════════════════════════════════════════════════
#  STEP 6 — Google Sheet reader
# ════════════════════════════════════════════════════════════════════════════

def fetch_sheet_as_df(sheet_id: str, gid: str = "0") -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    print(f"📥 Fetching Google Sheet…")
    resp = requests.get(url, timeout=30)
    if resp.status_code == 403:
        raise PermissionError(
            "\n❌ Google Sheet is not public.\n"
            "Fix: Sheet → Share → General access → 'Anyone with the link' → Viewer\n"
        )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    df = pd.read_csv(io.StringIO(resp.text), encoding="utf-8", encoding_errors="replace")
    df = df.dropna(how="all").reset_index(drop=True)
    print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns.\n")
    return df


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_lookup = {c.lower().strip(): c for c in df.columns}
    rename_map = {}

    ALIASES = {
        "Job Title":          ["title", "position", "role", "vacancy", "job name"],
        "Job Type":           ["type", "employment type", "contract type", "work type"],
        "Job Qualifications": ["qualifications", "qualification", "education", "degree"],
        "Job Experience":     ["experience", "exp", "years experience", "work experience"],
        "Job Location":       ["location", "city", "town", "region", "county", "place"],
        "Job Field":          ["field", "sector", "category", "job category"],
        "Date Posted":        ["posted", "post date", "published", "created"],
        "Deadline":           ["closing date", "expiry", "apply by", "close date", "end date"],
        "Job Description":    ["description", "details", "duties", "responsibilities",
                               "summary", "content", "job details"],
        "Application":        ["apply", "apply url", "apply link", "application url",
                               "application link", "apply email", "application email",
                               "email", "contact email", "how to apply"],
        "Company URL":        ["company url", "company link", "employer url"],
        "Company Name":       ["company", "employer", "organisation", "organization", "firm"],
        "Company Logo":       ["logo", "logo url", "company image", "company logo url"],
        "Company Industry":   ["industry", "company sector", "business type"],
        "Company Founded":    ["founded", "year founded", "established"],
        "Company Type":       ["company type", "org type"],
        "Company Website":    ["website", "company web", "web", "site", "company site"],
        "Company Address":    ["address", "location address"],
        "Company Details":    ["company description", "about company", "company bio",
                               "company profile", "about", "company info"],
        "Job URL":            ["url", "source url", "source", "link", "job link",
                               "original url", "reference url"],
        "Estimated Deadline": ["estimated expiry", "calculated deadline", "auto deadline"],
        "Salary Range":       ["salary", "salary range", "pay", "remuneration",
                               "compensation", "pay range", "wage", "wages"],
    }

    for internal, aliases in ALIASES.items():
        if internal in df.columns:
            continue
        for alias in aliases:
            if alias in col_lookup:
                rename_map[col_lookup[alias]] = internal
                df = df.rename(columns={col_lookup[alias]: internal})
                col_lookup = {c.lower().strip(): c for c in df.columns}
                break

    for col in APPSCRIPT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


def print_column_mapping(df: pd.DataFrame):
    print("┌─ COLUMN MAPPING " + "─"*42 + "┐")
    for col in APPSCRIPT_COLUMNS:
        has_data = (
            col in df.columns
            and df[col].notna().any()
            and (df[col].astype(str).str.strip() != "").any()
        )
        if has_data:
            sample = str(df[col].replace("", pd.NA).dropna().iloc[0])[:50]
            print(f"│  ✅ {col:<25} → {sample!r}")
        else:
            print(f"│  ⚠️  {col:<25} → NOT FOUND / empty")
    print("└" + "─"*59 + "┘\n")


# ════════════════════════════════════════════════════════════════════════════
#  STEP 7 — Utilities
# ════════════════════════════════════════════════════════════════════════════

grammar_tool     = language_tool_python.LanguageTool(
    "en-US", remote_server="https://api.languagetool.org"
)
similarity_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

_MOJIBAKE = [
    ("Â", ""), ("â€™", "'"), ("â€œ", '"'), ("â€\x9d", '"'), ("â€", '"'),
    ("â€¢", "•"), ("â„¢", "™"), ("\u00a0", " "), ("\u200b", ""), ("\ufeff", ""),
]

def _fix_mojibake(text: str) -> str:
    for pattern, replacement in _MOJIBAKE:
        text = text.replace(pattern, replacement)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text


def sanitize_text(text, is_url=False, is_email=False) -> str:
    if not isinstance(text, str):
        text = str(text) if pd.notna(text) else ""
    text = text.strip()
    if text in ("nan", "None", "NaN", "", "N/A", "n/a", "NA", "na"):
        return ""
    text = _fix_mojibake(text)
    if is_url or is_email:
        return re.sub(r"[ \t\r\n\f\v]+", " ", text).strip()
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*\*",  "", text)
    text = re.sub(r"[^\x20-\x7E\n\u00C0-\u017F\u2013\u2014\u2018-\u201D\u2022]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def grammar_correct(text: str) -> str:
    try:
        return language_tool_python.utils.correct(text, grammar_tool.check(text))
    except Exception:
        return text


def similarity_score(a: str, b: str) -> float:
    try:
        emb = similarity_model.encode([a, b], convert_to_tensor=True)
        return float(util.pytorch_cos_sim(emb[0], emb[1]))
    except Exception:
        return 0.0


def clean_output(text: str) -> str:
    text = _fix_mojibake(text)
    for pat in [r"\[/?INST\]", r"</?s>",
                r"(?i)(rewritten?|rephrased?|output|paraphrase[d]?)[:\s]+",
                r"\*\*", r"###", r"---"]:
        text = re.sub(pat, "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return grammar_correct(text.strip())


def normalise_job_type(raw: str) -> str:
    return JOB_TYPE_MAPPING.get(raw.lower().strip(), "full-time")


def make_job_id(row: pd.Series, idx: int) -> str:
    src = sanitize_text(str(row.get("Job URL", "")), is_url=True)
    if src:
        return hashlib.md5(src.encode()).hexdigest()[:16]
    seed = f"{row.get('Job Title','')}{row.get('Company Name','')}{idx}"
    return hashlib.md5(seed.encode()).hexdigest()[:16]


# ════════════════════════════════════════════════════════════════════════════
#  STEP 8 — Duplicate tracker
# ════════════════════════════════════════════════════════════════════════════

def _init_tracker():
    if not os.path.exists(PROCESSED_IDS_FILE):
        pd.DataFrame(columns=[
            "Job ID", "Job URL", "Job Title", "Company Name",
            "Status", "Timestamp", "Sheet Row",
        ]).to_csv(PROCESSED_IDS_FILE, index=False)


def load_processed_ids() -> tuple:
    _init_tracker()
    df = pd.read_csv(PROCESSED_IDS_FILE)
    return (
        set(df["Job ID"].fillna("").astype(str)),
        set(df.get("Job URL", pd.Series()).fillna("").astype(str)),
    )


def _upsert_row(job_id: str, updates: dict):
    _init_tracker()
    df   = pd.read_csv(PROCESSED_IDS_FILE)
    mask = df["Job ID"].astype(str) == str(job_id)
    if mask.any():
        for col, val in updates.items():
            if col in df.columns:
                df.loc[mask, col] = val
        df.loc[mask, "Timestamp"] = datetime.now().isoformat()
    else:
        row = {"Job ID": job_id, "Timestamp": datetime.now().isoformat()}
        row.update(updates)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(PROCESSED_IDS_FILE, index=False)


def mark_read(job_id, job_url, title, company, sheet_row):
    _upsert_row(job_id, {"Job URL": job_url, "Job Title": title,
                          "Company Name": company, "Status": "read",
                          "Sheet Row": sheet_row})

def mark_posted(job_id, wp_id, wp_url):
    _upsert_row(job_id, {"Status": f"posted|wp_id={wp_id}|{wp_url}"})

def mark_failed(job_id, reason):
    _upsert_row(job_id, {"Status": f"failed|{reason}"})


def print_tracker_summary():
    if not os.path.exists(PROCESSED_IDS_FILE):
        return
    df = pd.read_csv(PROCESSED_IDS_FILE)
    print(f"\n{'═'*55}")
    print(f"  TRACKER SUMMARY  ({len(df)} total records)")
    print(f"{'═'*55}")
    counts = df["Status"].str.split("|").str[0].value_counts()
    icons  = {"read": "🔵", "paraphrased": "🟡", "posted": "✅", "failed": "❌"}
    for status, count in counts.items():
        print(f"  {icons.get(status,'⚪')}  {status:<15} {count}")
    print(f"{'═'*55}\n")


# ════════════════════════════════════════════════════════════════════════════
#  STEP 9 — Paraphrase functions  (powered by Mistral API)
# ════════════════════════════════════════════════════════════════════════════

def paraphrase_title(title: str) -> str:
    clean = sanitize_text(title)
    if not clean:
        return title

    print(f"\n  ┌─ TITLE PARAPHRASE {'─'*40}")
    print(f"  │  Original : {clean}")

    prompt = (
        f"Rewrite this job title professionally using different words. "
        f"Output ONLY the rewritten title, nothing else. "
        f"Keep it between 4 and 12 words.\n\nJob title: {clean}"
    )

    best_result, best_sim = None, 0.0

    for attempt in range(3):
        temp   = round(0.70 + attempt * 0.05, 2)
        raw    = mistral_generate(prompt, max_tokens=40, temperature=temp)
        result = clean_output(raw).split("\n")[0].strip().strip('"').strip("'")
        wc     = len(result.split()) if result else 0
        sim    = similarity_score(clean, result) if result else 0.0
        is_dup = result.lower().strip() == clean.lower().strip()
        valid  = bool(result) and 3 <= wc <= 15 and sim >= 0.50 and not is_dup

        print(f"  │  Attempt {attempt+1} (temp={temp}): {result!r}  "
              f"words={wc} sim={sim:.3f} → {'✅' if valid else '❌'}")

        if valid and sim > best_sim:
            best_sim, best_result = sim, result

        time.sleep(1)  # respect 1 req/sec free tier limit

    if best_result:
        print(f"  │  ✅ BEST: {best_result!r} (sim={best_sim:.3f})")
        print(f"  └{'─'*58}")
        return best_result

    print(f"  │  ⚠️  Keeping original")
    print(f"  └{'─'*58}")
    return clean


def paraphrase_description(text: str) -> str:
    clean = sanitize_text(text)
    if not clean:
        return text

    paragraphs    = [p.strip() for p in clean.split("\n") if p.strip()]
    rewritten     = []
    success_count = 0

    print(f"\n  ┌─ DESCRIPTION PARAPHRASE  ({len(paragraphs)} paragraphs) {'─'*25}")

    for i, para in enumerate(paragraphs):
        orig_wc = len(para.split())
        print(f"  │  Para {i+1}/{len(paragraphs)} ({orig_wc}w): "
              f"{para[:80]}{'…' if len(para)>80 else ''}")

        prompt = (
            f"Rewrite this job description paragraph professionally. "
            f"Keep ALL facts, requirements, and responsibilities. "
            f"Use different sentence structure and vocabulary. "
            f"Output ONLY the rewritten paragraph — no labels, no explanation.\n\n"
            f"Original:\n{para}"
        )

        raw    = mistral_generate(prompt, max_tokens=500, temperature=0.68)
        result = clean_output(raw)
        rw     = len(result.split()) if result else 0
        sim    = similarity_score(para, result) if result and rw >= 5 else 0.0

        print(f"  │    → words={orig_wc}→{rw}  sim={sim:.3f}", end="  ")

        if result and rw >= 5 and sim >= 0.45:
            print("✅ ACCEPTED")
            rewritten.append(result)
            success_count += 1
        else:
            print("❌ keeping original")
            rewritten.append(para)

        time.sleep(1)  # respect 1 req/sec free tier limit

    print(f"  │  RESULT: {success_count}/{len(paragraphs)} paragraphs rewritten")
    print(f"  └{'─'*58}")
    return "\n\n".join(rewritten)


def paraphrase_company(text: str) -> str:
    clean = sanitize_text(text)
    if not clean:
        return text
    prompt = (
        f"Rewrite this company description professionally. "
        f"Preserve all facts. Use different wording. "
        f"Output ONLY the rewritten description.\n\nOriginal:\n{clean}"
    )
    raw    = mistral_generate(prompt, max_tokens=600, temperature=0.68)
    result = clean_output(raw)
    time.sleep(1)
    return result if result and len(result.split()) >= 10 else clean


def paraphrase_tagline(text: str) -> str:
    clean = sanitize_text(text[:300])
    if not clean:
        return text
    prompt = (
        f"Rewrite this company tagline as a crisp, professional phrase. "
        f"Output ONLY the rewritten tagline (5–12 words). No explanation.\n\n"
        f"Original: {clean}"
    )
    raw    = mistral_generate(prompt, max_tokens=35, temperature=0.75)
    result = clean_output(raw).split("\n")[0].strip().strip('"').strip("'")
    wc     = len(result.split()) if result else 0
    time.sleep(1)
    return result if result and 3 <= wc <= 15 else clean


# ════════════════════════════════════════════════════════════════════════════
#  STEP 10 — WordPress helpers
# ════════════════════════════════════════════════════════════════════════════

def wp_headers():
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def upload_logo(logo_url: str):
    logo_url = sanitize_text(logo_url, is_url=True)
    if not logo_url or not logo_url.startswith("http"):
        return None
    ext = logo_url.lower().rsplit(".", 1)[-1]
    if ext not in ("png", "jpg", "jpeg", "webp"):
        return None
    try:
        img = requests.get(logo_url, timeout=10)
        img.raise_for_status()
        h = wp_headers()
        h["Content-Disposition"] = f"attachment; filename={logo_url.split('/')[-1]}"
        h["Content-Type"] = img.headers.get("content-type", "image/jpeg")
        r = requests.post(WP_MEDIA_URL, headers=h, data=img.content,
                          auth=(WP_USERNAME, WP_APP_PASSWORD), timeout=15, verify=False)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        logger.error(f"Logo upload error: {e}")
        return None


def get_or_create_term(taxonomy_url: str, name: str):
    if not name or not name.strip():
        return None
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())
    try:
        r = requests.get(f"{taxonomy_url}?slug={slug}",
                         headers=wp_headers(), timeout=10, verify=False)
        terms = r.json()
        if isinstance(terms, list) and terms:
            return terms[0]["id"]
    except Exception:
        pass
    try:
        r = requests.post(taxonomy_url,
                          json={"name": name, "slug": slug},
                          headers=wp_headers(),
                          auth=(WP_USERNAME, WP_APP_PASSWORD),
                          timeout=10, verify=False)
        return r.json().get("id")
    except Exception as e:
        logger.error(f"Term create error '{name}': {e}")
        return None


def save_company(company_data: dict):
    name = sanitize_text(company_data.get("company_name", ""))
    if not name or name in ("Unknown Company", "nan"):
        return None, None

    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    try:
        r = requests.get(f"{WP_COMPANY_URL}?slug={slug}",
                         headers=wp_headers(), timeout=10, verify=False)
        posts = r.json()
        if isinstance(posts, list) and posts:
            logger.info(f"⏭  Company exists: {name}")
            return posts[0]["id"], posts[0].get("link")
    except Exception:
        pass

    attachment_id = upload_logo(company_data.get("company_logo", ""))
    raw           = company_data.get("company_details", "")
    details       = paraphrase_company(raw) if raw else ""
    tagline       = paraphrase_tagline(raw[:300]) if raw else ""

    payload = {
        "title":          name,
        "content":        details,
        "status":         "publish",
        "featured_media": attachment_id or 0,
        "meta": {
            "_company_name":     name,
            "_company_logo":     str(attachment_id) if attachment_id else "",
            "_company_industry": sanitize_text(company_data.get("company_industry", "")),
            "_company_website":  sanitize_text(company_data.get("company_website", ""), is_url=True),
            "_company_tagline":  tagline,
        },
    }
    try:
        r = requests.post(WP_COMPANY_URL, json=payload, headers=wp_headers(),
                          auth=(WP_USERNAME, WP_APP_PASSWORD), timeout=15, verify=False)
        r.raise_for_status()
        post = r.json()
        logger.info(f"✅ Company posted: {name} → ID {post.get('id')}")
        return post.get("id"), post.get("link")
    except Exception as e:
        logger.error(f"Company post error '{name}': {e}")
        return None, None


def save_job(row: pd.Series, title: str, description: str) -> tuple:
    h = wp_headers()

    for jt_label in ["Full Time", "Part Time", "Contract",
                     "Temporary", "Freelance", "Internship", "Volunteer"]:
        get_or_create_term(f"{WP_BASE}/job_listing_type", jt_label)

    location    = sanitize_text(str(row.get("Job Location",       "Kenya")))
    raw_type    = sanitize_text(str(row.get("Job Type",           "Full-time")))
    job_type_s  = normalise_job_type(raw_type)
    company     = sanitize_text(str(row.get("Company Name",       "")))
    application = sanitize_text(str(row.get("Application",        "")), is_url=True)
    deadline    = sanitize_text(str(row.get("Deadline",           "")))
    logo_url    = sanitize_text(str(row.get("Company Logo",       "")), is_url=True)
    co_website  = sanitize_text(str(row.get("Company Website",    "")), is_url=True)
    qualif      = sanitize_text(str(row.get("Job Qualifications", "")))
    experience  = sanitize_text(str(row.get("Job Experience",     "")))
    industry    = sanitize_text(str(row.get("Company Industry",   "")))
    co_address  = sanitize_text(str(row.get("Company Address",    "")))
    job_field   = sanitize_text(str(row.get("Job Field",          "")))
    job_url     = sanitize_text(str(row.get("Job URL",            "")), is_url=True)
    co_founded  = sanitize_text(str(row.get("Company Founded",    "")))
    co_type     = sanitize_text(str(row.get("Company Type",       "")))
    salary      = sanitize_text(str(row.get("Salary Range",       "")))

    if not deadline:
        deadline = sanitize_text(str(row.get("Estimated Deadline", "")))

    is_email = bool(re.match(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", application))
    is_url_v = bool(re.match(r"^https?://[^\s]+$", application))
    if not (is_email or is_url_v):
        application = ""

    slug = re.sub(r"[^a-z0-9-]", "-", title.lower())[:80]
    try:
        r = requests.get(f"{WP_URL}?slug={slug}", headers=h, timeout=10, verify=False)
        posts = r.json()
        if isinstance(posts, list) and posts:
            logger.info(f"⏭  Job already on WP: {title}")
            return posts[0]["id"], posts[0].get("link")
    except Exception:
        pass

    attachment_id    = upload_logo(logo_url)
    region_term_id   = get_or_create_term(f"{WP_BASE}/job_listing_region", location)
    job_type_term_id = get_or_create_term(f"{WP_BASE}/job_listing_type",
                                          job_type_s.replace("-", " ").title())

    payload = {
        "title":          title,
        "content":        description,
        "status":         "publish",
        "featured_media": attachment_id or 0,
        "meta": {
            "_job_title":          title,
            "_job_location":       location,
            "_job_type":           job_type_s,
            "_job_description":    description,
            "_application":        application,
            "_job_expires":        deadline,
            "_company_name":       company,
            "_company_website":    co_website,
            "_company_logo":       str(attachment_id) if attachment_id else "",
            "_company_industry":   industry,
            "_company_address":    co_address,
            "_company_founded":    co_founded,
            "_company_type":       co_type,
            "_job_qualifications": qualif,
            "_job_experiences":    experience,
            "_job_field":          job_field,
            "_job_source_url":     job_url,
            "_job_salary":         salary,
        },
    }
    if region_term_id:
        payload["job_listing_region"] = [region_term_id]
    if job_type_term_id:
        payload["job_listing_type"]   = [job_type_term_id]

    for attempt in range(3):
        try:
            r = requests.post(WP_URL, json=payload, headers=h,
                              auth=(WP_USERNAME, WP_APP_PASSWORD),
                              timeout=20, verify=False)
            r.raise_for_status()
            post = r.json()
            logger.info(f"✅ Job posted: '{title}' → WP ID {post.get('id')}")
            return post.get("id"), post.get("link")
        except Exception as e:
            logger.error(f"Job post attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None, None


# ════════════════════════════════════════════════════════════════════════════
#  STEP 11 — Core processing
# ════════════════════════════════════════════════════════════════════════════

def process_sheet():
    df_raw = fetch_sheet_as_df(SHEET_ID, SHEET_GID)
    df     = map_columns(df_raw)
    print_column_mapping(df)

    processed_ids, processed_urls = load_processed_ids()
    print(f"📋 {len(processed_ids)} jobs already in tracker.")
    print_tracker_summary()

    processed_companies = set()
    total        = len(df)
    posted_count = skipped_count = failed_count = 0

    for idx, row in df.iterrows():
        sheet_row   = idx + 2
        title       = sanitize_text(str(row.get("Job Title",      "")))
        desc        = sanitize_text(str(row.get("Job Description", "")))
        company     = sanitize_text(str(row.get("Company Name",    "")))
        job_url     = sanitize_text(str(row.get("Job URL",         "")), is_url=True)
        application = sanitize_text(str(row.get("Application",     "")))
        job_id      = make_job_id(row, idx)

        print(f"\n{'═'*60}")
        print(f"  Row {sheet_row}/{total+1}  |  Job ID: {job_id}")
        print(f"  Title   : {title or '(empty)'}")
        print(f"  Company : {company or '(empty)'}")
        print(f"{'═'*60}")

        if not title:
            print("  ⏭  SKIP — empty Job Title.")
            skipped_count += 1; continue
        if not desc:
            print("  ⏭  SKIP — empty Job Description.")
            skipped_count += 1; continue
        if not application:
            print("  ⏭  SKIP — empty Application.")
            skipped_count += 1; continue
        if job_id in processed_ids:
            print(f"  ⏭  SKIP — already processed.")
            skipped_count += 1; continue
        if job_url and job_url in processed_urls:
            print(f"  ⏭  SKIP — URL already processed.")
            skipped_count += 1; continue

        mark_read(job_id, job_url, title, company, sheet_row)
        processed_ids.add(job_id)
        if job_url:
            processed_urls.add(job_url)

        if company and company not in processed_companies:
            company_data = {
                "company_name":     company,
                "company_logo":     sanitize_text(str(row.get("Company Logo",    "")), is_url=True),
                "company_website":  sanitize_text(str(row.get("Company Website", "")), is_url=True),
                "company_industry": sanitize_text(str(row.get("Company Industry",""))),
                "company_details":  sanitize_text(str(row.get("Company Details", ""))),
            }
            print(f"\n  🏢 Processing company: {company}")
            save_company(company_data)
            processed_companies.add(company)

        print(f"\n  ✍️  Paraphrasing with Mistral…")
        new_title = paraphrase_title(title)
        new_desc  = paraphrase_description(desc)
        _upsert_row(job_id, {"Status": "paraphrased"})

        print(f"\n  📤 Posting to WordPress…")
        post_id, post_url = save_job(row, new_title, new_desc)

        if post_id:
            mark_posted(job_id, post_id, post_url or "")
            posted_count += 1
            print(f"  ✅ SUCCESS — WP ID={post_id}  🔗 {post_url}")
        else:
            mark_failed(job_id, "wp_post_failed")
            failed_count += 1
            print(f"  ❌ WordPress post failed.")

        if (idx + 1) % 10 == 0:
            print(f"\n  ⏸  Pausing 20s after every 10 jobs…")
            time.sleep(20)

    print(f"\n{'#'*60}")
    print(f"  CYCLE COMPLETE  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"  ✅ Posted  : {posted_count}")
    print(f"  ⏭  Skipped : {skipped_count}")
    print(f"  ❌ Failed  : {failed_count}")
    print(f"{'#'*60}")
    print_tracker_summary()


# ════════════════════════════════════════════════════════════════════════════
#  STEP 12 — Entry point
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🚀 Kenya MimusJobs — Starting with Mistral API…\n")
    process_sheet()
    print("\n✅ Done. All jobs processed.")
