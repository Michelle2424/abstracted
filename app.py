import base64
import json
import os
import urllib.parse
from typing import Dict, List, Optional

from Bio import Entrez
from google import genai
from google.genai import types
import streamlit as st
from supabase import Client, create_client

# -----------------------------------------------------------------------------
# App Configuration & Branding
# -----------------------------------------------------------------------------
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="8" fill="#1E1B4B"/>
<path d="M7 9C12 9 16 13 16 16C16 19 20 23 25 23" stroke="#818CF8" stroke-width="2.5" stroke-linecap="round"/>
<path d="M25 9C20 9 16 13 16 16C16 19 12 23 7 23" stroke="#38BDF8" stroke-width="2.5" stroke-linecap="round"/>
<circle cx="16" cy="16" r="3" fill="#C084FC"/>
</svg>"""

FAVICON_URI = f"data:image/svg+xml;base64,{base64.b64encode(FAVICON_SVG.encode()).decode()}"

st.set_page_config(
    page_title="Abstracted | Science News for Students",
    page_icon=FAVICON_URI,
    layout="wide",
    initial_sidebar_state="expanded",
)

Entrez.email = "abstracted.feed@service.internal"
Entrez.tool = "AbstractedApp"

# -----------------------------------------------------------------------------
# Global CSS & High-Contrast Typography Styles
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        color: #0F172A;
    }

    .stApp {
        background-color: #F8FAFC;
    }

    /* Vibrant Logo Brand Gradient matching Favicon Colors */
    .app-brand {
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
        display: inline-block;
    }

    /* News card container */
    .news-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.35rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .news-card:hover {
        border-color: #CBD5E1;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.07);
    }

    .news-headline {
        font-family: 'Newsreader', serif;
        font-size: 1.35rem;
        font-weight: 500;
        color: #0F172A;
        line-height: 1.35;
        margin-bottom: 0.6rem;
    }

    .teaser-line {
        color: #334155;
        font-size: 0.93rem;
        line-height: 1.55;
        margin-bottom: 0.4rem;
    }

    .why-it-matters-container {
        background: #F0FDF4;
        border-left: 3px solid #22C55E;
        padding: 0.75rem 0.9rem;
        border-radius: 0 8px 8px 0;
        color: #14532D;
        font-size: 0.91rem;
        line-height: 1.6;
        margin-top: 0.4rem;
        margin-bottom: 0.6rem;
    }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .badge-beginner { background: #DCFCE7; color: #15803D; }
    .badge-intermediate { background: #FEF3C7; color: #B45309; }
    .badge-advanced { background: #FEE2E2; color: #B91C1C; }

    /* Bottom-left user profile card */
    .user-profile-badge {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0.6rem 0.75rem;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }

    .user-avatar-circle {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, #38BDF8, #818CF8);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.85rem;
    }

    /* Contrast Fixes for Streamlit Tabs & Expanders */
    [data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {
        color: #1E293B !important;
        font-weight: 600;
    }

    [data-testid="stTabs"] [aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        color: #4F46E5 !important;
    }

    [data-testid="stExpander"] details {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
    }

    [data-testid="stExpander"] summary span {
        color: #0F172A !important;
        font-weight: 600;
    }

    .abstract-text-container {
        color: #0F172A !important;
        background: #F8FAFC;
        padding: 1rem;
        border-radius: 6px;
        line-height: 1.65;
        font-size: 0.92rem;
    }

    .lesson-section {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.3rem;
        margin-bottom: 1rem;
    }

    .takeaway-bullet {
        padding: 0.65rem 0.85rem;
        background: #F8FAFC;
        border-left: 3px solid #6366F1;
        border-radius: 0 6px 6px 0;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
        line-height: 1.5;
        color: #1E293B;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Topic Taxonomy Loading
# -----------------------------------------------------------------------------
DEFAULT_TOPICS_TAXONOMY = {
    "Genomics & Engineering": [
        "CRISPR",
        "Gene Therapy",
        "Synthetic Biology",
        "Base Editing",
    ],
    "Neuroscience & Psychology": [
        "Neuroplasticity",
        "Alzheimer's Disease",
        "Neural Interfaces",
        "Brain-Computer Interface",
    ],
    "Medicine & Therapeutics": [
        "mRNA Vaccines",
        "Immunotherapy",
        "CAR-T Cell Therapy",
        "Antibiotic Resistance",
    ],
    "AI & Computational Biology": [
        "AI in Medicine",
        "AlphaFold",
        "Protein Design",
        "Machine Learning Diagnostics",
    ],
    "Cellular Biology & Aging": [
        "Cellular Senescence",
        "Stem Cells",
        "Mitochondrial Biology",
        "Telomeres",
    ],
}


@st.cache_data(ttl=300)
def load_research_topics() -> Dict[str, List[str]]:
    """Loads categorized topics from topics.json with a structured fallback."""
    if os.path.exists("topics.json"):
        try:
            with open("topics.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            pass
    return DEFAULT_TOPICS_TAXONOMY


TOPICS_TAXONOMY = load_research_topics()
ALL_TOPICS_FLAT = [topic for category in TOPICS_TAXONOMY.values() for topic in category]

# -----------------------------------------------------------------------------
# Clients Initialization
# -----------------------------------------------------------------------------
def get_gemini_client() -> Optional[genai.Client]:
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def get_supabase_client() -> Optional[Client]:
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


# Session State Defaults
if "user" not in st.session_state:
    st.session_state.user = None
if "user_first_name" not in st.session_state:
    st.session_state.user_first_name = ""
if "user_interests" not in st.session_state:
    st.session_state.user_interests = ["CRISPR", "AI in Medicine"]
if "active_view" not in st.session_state:
    st.session_state.active_view = "fyp"
if "reader_pmid" not in st.session_state:
    st.session_state.reader_pmid = None
if "gemini_fyp_cache" not in st.session_state:
    st.session_state.gemini_fyp_cache = {}


# -----------------------------------------------------------------------------
# PubMed Entrez Fetchers
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_pubmed_by_interests(interests: List[str], max_results: int = 8) -> List[str]:
    """Queries PubMed for recent high-impact abstracts matching terms."""
    if not interests:
        interests = ["Biomedical Science"]
    clean_terms = [f'"{term}"[Title/Abstract]' for term in interests]
    query = f"({' OR '.join(clean_terms)}) AND hasabstract[text]"

    try:
        with Entrez.esearch(db="pubmed", term=query, sort="pub_date", retmax=max_results) as handle:
            record = Entrez.read(handle)
        return record.get("IdList", [])
    except Exception:
        return ["38157930", "32284366"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_pubmed_article(pmid: str) -> Dict:
    clean_pmid = str(pmid).strip()
    with Entrez.efetch(db="pubmed", id=clean_pmid, retmode="xml", rettype="abstract") as handle:
        records = Entrez.read(handle)

    articles = records.get("PubmedArticle", [])
    if not articles:
        raise LookupError(f"No publication found for PMID: {clean_pmid}")

    citation = articles[0]["MedlineCitation"]
    art = citation["Article"]
    title = art.get("ArticleTitle", "Untitled Article").rstrip(".")

    authors = [
        f"{a.get('LastName', '')} {a.get('Initials', '')}".strip()
        for a in art.get("AuthorList", [])
        if a.get("LastName")
    ]

    journal_obj = art.get("Journal", {})
    journal = journal_obj.get("ISOAbbreviation") or journal_obj.get("Title") or "Medical Journal"
    pub_date = journal_obj.get("JournalIssue", {}).get("PubDate", {}).get("Year", "2024")

    doi = None
    for eid in art.get("ELocationID", []):
        if getattr(eid, "attributes", {}).get("EIdType") == "doi":
            doi = str(eid)

    raw_abstract = art.get("Abstract", {}).get("AbstractText", [])
    abstract_text = ""
    if isinstance(raw_abstract, list):
        abstract_text = " ".join([str(p).strip() for p in raw_abstract])
    elif raw_abstract:
        abstract_text = str(raw_abstract).strip()

    if not abstract_text:
        abstract_text = "Abstract text not indexed for this record."

    return {
        "pmid": clean_pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": pub_date,
        "doi": doi,
        "abstract": abstract_text,
    }


# -----------------------------------------------------------------------------
# Google Gemini Processing (Untruncated News Generation)
# -----------------------------------------------------------------------------
def batch_summarize_feed(papers: List[Dict], gemini_client: Optional[genai.Client]) -> List[Dict]:
    """Generates complete, untruncated 3-4 sentence explanations with no trailing dots."""
    processed = []
    if not gemini_client:
        for p in papers:
            teaser = p["abstract"][:120] + "." if len(p["abstract"]) > 120 else p["abstract"]
            processed.append({
                "pmid": p["pmid"],
                "headline": p["title"],
                "teaser": teaser,
                "why_it_matters": p["abstract"][:300],
                "difficulty": "Intermediate",
                "journal": p["journal"],
                "year": p["year"],
            })
        return processed

    payload = [
        {"id": p["pmid"], "title": p["title"], "abstract": p["abstract"][:900]}
        for p in papers
    ]

    prompt = f"""You are an executive editor for 'Abstracted', a student-friendly science publication.
Convert each biomedical study into an accurate, complete news summary for college students.

Requirements:
1. "headline": Punchy, jargon-free student headline (under 14 words).
2. "teaser": Exactly one sentence capturing the main finding.
3. "why_it_matters": MUST be a complete, fully formed explanation consisting of 3 to 4 complete sentences. Explain the mechanism and why it matters in practical healthcare or biology. DO NOT truncate. Never end with an ellipsis ('...').
4. "difficulty": Choose from 'Beginner', 'Intermediate', or 'Advanced'.

Papers:
{json.dumps(payload)}

Return ONLY valid JSON matching this schema:
[
  {{
    "pmid": "string id",
    "headline": "headline string",
    "teaser": "single complete teaser sentence",
    "why_it_matters": "complete 3-4 sentence explanation without ellipses",
    "difficulty": "Beginner" | "Intermediate" | "Advanced"
  }}
]
"""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        parsed = json.loads(response.text)
        by_id = {item["pmid"]: item for item in parsed if "pmid" in item}

        for p in papers:
            meta = by_id.get(p["pmid"], {})
            wim = meta.get("why_it_matters", p["abstract"][:280]).strip()
            if wim.endswith("..."):
                wim = wim[:-3].strip() + "."
            teaser = meta.get("teaser") or (wim.split(".")[0] + "." if "." in wim else wim)

            processed.append({
                "pmid": p["pmid"],
                "headline": meta.get("headline", p["title"]),
                "teaser": teaser,
                "why_it_matters": wim,
                "difficulty": meta.get("difficulty", "Intermediate"),
                "journal": p["journal"],
                "year": p["year"],
            })
    except Exception:
        for p in papers:
            processed.append({
                "pmid": p["pmid"],
                "headline": p["title"],
                "teaser": p["abstract"][:120] + ".",
                "why_it_matters": p["abstract"][:300] + ".",
                "difficulty": "Intermediate",
                "journal": p["journal"],
                "year": p["year"],
            })
    return processed


def generate_student_digest(article: Dict, gemini_client: Optional[genai.Client]) -> Dict:
    """Produces the structured lesson breakdown for an individual paper."""
    if not gemini_client:
        return {
            "dilemma": article["abstract"][:250],
            "how_it_works": article["abstract"],
            "bullets": ["High-yield mechanism documented in original study text."],
            "nuance": "Clinical validity requires prospective cohort replication.",
        }

    prompt = f"""Break down this biomedical paper for an undergraduate student.
Title: {article['title']}
Journal: {article['journal']} ({article['year']})
Abstract: {article['abstract']}

Return valid JSON with:
{{
  "dilemma": "One clear paragraph on the specific clinical or biological mystery this paper confronts.",
  "how_it_works": "Plain-English explanation of experimental model and core cellular/biochemical mechanism found.",
  "bullets": [
    "Key takeaway 1 (specific quantified metric or conclusion)",
    "Key takeaway 2 (biological insight)",
    "Key takeaway 3 (clinical translation)"
  ],
  "nuance": "One critical experimental constraint or cohort limitation."
}}
"""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
    except Exception:
        return {
            "dilemma": article["abstract"][:250],
            "how_it_works": article["abstract"],
            "bullets": ["Key findings provided in study report."],
            "nuance": "Translation contingent on further replication.",
        }


# -----------------------------------------------------------------------------
# Supabase Database Helpers
# -----------------------------------------------------------------------------
def load_user_profile(sb: Client, user_id: str):
    try:
        res = sb.table("profiles").select("*").eq("id", user_id).execute()
        if res.data:
            data = res.data[0]
            saved_interests = data.get("interests", [])
            valid_interests = [i for i in saved_interests if i in ALL_TOPICS_FLAT]
            if valid_interests:
                st.session_state.user_interests = valid_interests
    except Exception:
        pass


def save_user_profile_data(sb: Optional[Client], user_id: Optional[str], interests: List[str]):
    if sb and user_id:
        try:
            sb.table("profiles").upsert({
                "id": user_id,
                "interests": interests,
            }).execute()
        except Exception as e:
            st.error(f"Failed to sync preferences: {e}")


def mark_article_read(sb: Optional[Client], user_id: Optional[str], article: Dict):
    if not (sb and user_id):
        return
    try:
        sb.table("user_library").upsert({
            "user_id": user_id,
            "pmid": article["pmid"],
            "title": article["title"],
            "journal": article["journal"],
            "year": str(article["year"]),
            "is_read": True,
        }, on_conflict="user_id,pmid").execute()
    except Exception:
        pass


def toggle_bookmark(sb: Optional[Client], user_id: Optional[str], article_dict: Dict, current_status: bool):
    if not user_id:
        st.toast("Please log in to save articles to your library.", icon="🔒")
        return current_status

    new_status = not current_status
    if sb:
        try:
            sb.table("user_library").upsert({
                "user_id": user_id,
                "pmid": article_dict["pmid"],
                "title": article_dict.get("headline", article_dict.get("title", "")),
                "journal": article_dict.get("journal", ""),
                "year": str(article_dict.get("year", "2024")),
                "is_bookmarked": new_status,
            }, on_conflict="user_id,pmid").execute()
            status_text = "Saved to Library" if new_status else "Removed from Library"
            st.toast(status_text, icon="🔖" if new_status else "🗑️")
        except Exception as e:
            st.warning(f"Database sync issue: {e}")
    return new_status


def get_user_library(sb: Optional[Client], user_id: Optional[str]):
    if not (sb and user_id):
        return {"bookmarks": [], "history": []}
    try:
        res = sb.table("user_library").select("*").eq("user_id", user_id).order("last_accessed", desc=True).execute()
        records = res.data or []
        return {
            "bookmarks": [r for r in records if r.get("is_bookmarked")],
            "history": [r for r in records if r.get("is_read")],
        }
    except Exception:
        return {"bookmarks": [], "history": []}


# -----------------------------------------------------------------------------
# Sidebar: Navigation, Interests & Bottom-Left Profile
# -----------------------------------------------------------------------------
supabase_client = get_supabase_client()
gemini_client = get_gemini_client()

with st.sidebar:
    # 1. Top Logo Branding with Favicon Color Gradient
    st.markdown('<div class="app-brand">Abstracted.</div>', unsafe_allow_html=True)
    st.caption("Personalized Science News for Students")
    st.write("")

    # 2. Main Navigation Buttons
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("📰 Feed", use_container_width=True, type="primary" if st.session_state.active_view == "fyp" else "secondary"):
            st.session_state.active_view = "fyp"
            st.rerun()
    with nav_col2:
        if st.button("📚 Library", use_container_width=True, type="primary" if st.session_state.active_view == "library" else "secondary"):
            st.session_state.active_view = "library"
            st.rerun()

    st.divider()

    # 3. Categorized Interests with Auth Gate
    st.markdown("#### 🧬 Research Interests")

    if st.session_state.user:
        # Categorized multi-select using topics.json hierarchy
        valid_defaults = [i for i in st.session_state.user_interests if i in ALL_TOPICS_FLAT]

        # Render categorized taxonomy preview / selection
        selected_topics = st.multiselect(
            "Curate your feed topics:",
            options=ALL_TOPICS_FLAT,
            default=valid_defaults,
            help="Select topics loaded dynamically from the research taxonomy.",
        )

        if st.button("Update Feed", use_container_width=True):
            st.session_state.user_interests = selected_topics
            user_id = st.session_state.user.id
            save_user_profile_data(supabase_client, user_id, selected_topics)
            st.session_state.gemini_fyp_cache.clear()
            st.toast("Feed preferences updated!", icon="✨")
            st.session_state.active_view = "fyp"
            st.rerun()
    else:
        st.info("🔒 **Sign in** to personalize your research interests and sync bookmarks.")

    st.divider()

    # 4. Bottom-Left Profile & Account Management
    st.markdown("#### 👤 Account")
    if supabase_client:
        if st.session_state.user:
            u_email = st.session_state.user.email or "Student"
            u_name = st.session_state.user_first_name or u_email.split("@")[0].capitalize()
            initials = u_name[0].upper()

            # Profile Badge
            st.markdown(
                f"""
                <div class="user-profile-badge">
                    <div class="user-avatar-circle">{initials}</div>
                    <div style="overflow: hidden;">
                        <div style="font-weight: 700; font-size: 0.88rem; color: #0F172A; text-overflow: ellipsis; white-space: nowrap;">{u_name}</div>
                        <div style="font-size: 0.74rem; color: #64748B; text-overflow: ellipsis; white-space: nowrap;">{u_email}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Account Settings Popover / Expander
            with st.expander("Manage Account"):
                new_display_name = st.text_input("First Name", value=st.session_state.user_first_name)
                new_password = st.text_input("New Password", type="password")

                if st.button("Save Changes", use_container_width=True):
                    try:
                        update_payload = {}
                        if new_display_name:
                            st.session_state.user_first_name = new_display_name
                            update_payload["data"] = {"first_name": new_display_name}
                        if new_password:
                            update_payload["password"] = new_password

                        if update_payload:
                            supabase_client.auth.update_user(update_payload)
                            st.success("Account updated successfully!")
                    except Exception as err:
                        st.error(f"Update failed: {err}")

                if st.button("Log Out", use_container_width=True):
                    supabase_client.auth.sign_out()
                    st.session_state.user = None
                    st.session_state.user_first_name = ""
                    st.rerun()
        else:
            # Login / Signup Interface
            auth_choice = st.radio("Access", ["Log In", "Sign Up"], horizontal=True, label_visibility="collapsed")
            if auth_choice == "Log In":
                l_email = st.text_input("Email", key="l_email")
                l_pwd = st.text_input("Password", type="password", key="l_pwd")
                if st.button("Log In", use_container_width=True, type="primary"):
                    try:
                        res = supabase_client.auth.sign_in_with_password({"email": l_email, "password": l_pwd})
                        st.session_state.user = res.user
                        metadata = getattr(res.user, "user_metadata", {}) or {}
                        st.session_state.user_first_name = metadata.get("first_name", "")
                        load_user_profile(supabase_client, res.user.id)
                        st.rerun()
                    except Exception as err:
                        st.error(f"Login failed: {err}")
            else:
                s_fname = st.text_input("First Name", key="s_fname")
                s_email = st.text_input("Email", key="s_email")
                s_pwd = st.text_input("Password", type="password", key="s_pwd")
                if st.button("Create Account", use_container_width=True):
                    try:
                        res = supabase_client.auth.sign_up({
                            "email": s_email,
                            "password": s_pwd,
                            "options": {"data": {"first_name": s_fname}},
                        })
                        if res.user:
                            st.success("Account created! Please log in above.")
                    except Exception as err:
                        st.error(f"Sign up error: {err}")
    else:
        st.caption("Connect Supabase secrets to enable cloud sync.")


# -----------------------------------------------------------------------------
# Main Application Header & Dual Search Bar
# -----------------------------------------------------------------------------
header_col, search_col = st.columns([1.5, 1.3], vertical_alignment="center")

with header_col:
    st.markdown('<h1 style="font-size: 2.1rem; font-weight: 800; margin: 0; color: #0F172A;">Today\'s Feed</h1>', unsafe_allow_html=True)
    st.caption("Curated peer-reviewed discoveries explained for students.")

with search_col:
    # Dual Search Controls in Top-Right
    s_mode = st.radio(
        "Search Mode",
        options=["Topic Discovery", "Direct PMID"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if s_mode == "Topic Discovery":
        # Grouped by category
        chosen_cat = st.selectbox("Category", list(TOPICS_TAXONOMY.keys()), label_visibility="collapsed")
        cat_topics = TOPICS_TAXONOMY[chosen_cat]
        c_sub1, c_sub2 = st.columns([3, 1])
        with c_sub1:
            chosen_term = st.selectbox("Topic", cat_topics, label_visibility="collapsed")
        with c_sub2:
            if st.button("Explore", use_container_width=True):
                st.session_state.user_interests = [chosen_term]
                st.session_state.gemini_fyp_cache.clear()
                st.session_state.active_view = "fyp"
                st.rerun()
    else:
        c_pm1, c_pm2 = st.columns([3, 1])
        with c_pm1:
            direct_pmid = st.text_input("Enter PMID", placeholder="e.g. 38157930", label_visibility="collapsed")
        with c_pm2:
            if st.button("Open", use_container_width=True) and direct_pmid.strip():
                st.session_state.reader_pmid = direct_pmid.strip()
                st.session_state.active_view = "reader"
                st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# VIEW 1: Newsfeed ("Today's Feed")
# -----------------------------------------------------------------------------
if st.session_state.active_view == "fyp":
    cache_key = "-".join(sorted(st.session_state.user_interests))

    with st.spinner("Compiling latest peer-reviewed findings..."):
        if cache_key not in st.session_state.gemini_fyp_cache:
            pmid_list = search_pubmed_by_interests(st.session_state.user_interests, max_results=8)
            raw_papers = []
            for pid in pmid_list:
                try:
                    raw_papers.append(fetch_pubmed_article(pid))
                except Exception:
                    continue

            summarized = batch_summarize_feed(raw_papers, gemini_client)
            st.session_state.gemini_fyp_cache[cache_key] = summarized

        news_feed = st.session_state.gemini_fyp_cache.get(cache_key, [])

    if not news_feed:
        st.info("No studies found matching current topics. Select different interests in the sidebar or search bar.")

    # Retrieve current user bookmarks for badge state
    user_id = st.session_state.user.id if st.session_state.user else None
    lib_records = get_user_library(supabase_client, user_id)
    bookmarked_ids = {b["pmid"] for b in lib_records["bookmarks"]}

    for item in news_feed:
        is_bookmarked = item["pmid"] in bookmarked_ids
        diff_class = f"badge-{item['difficulty'].lower()}"

        st.markdown(
            f"""
            <div class="news-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                    <span style="font-size: 0.8rem; color: #64748B; font-weight: 500;">🏛️ {item['journal']} ({item['year']}) &bull; PMID: {item['pmid']}</span>
                    <span class="badge {diff_class}">{item['difficulty']}</span>
                </div>
                <div class="news-headline">{item['headline']}</div>
                <div class="teaser-line"><strong>Summary:</strong> {item['teaser']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Untruncated summary via Expander
        with st.expander(f"💡 Why It Matters (Full 3-4 Sentence Breakdown) — PMID {item['pmid']}"):
            st.markdown(
                f"""
                <div class="why-it-matters-container">
                    {item['why_it_matters']}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Action Buttons
        btn_col1, btn_col2, _ = st.columns([1.4, 1.4, 7])
        with btn_col1:
            if st.button("Read Digest 📖", key=f"read_{item['pmid']}", use_container_width=True, type="primary"):
                st.session_state.reader_pmid = item["pmid"]
                st.session_state.active_view = "reader"
                st.rerun()

        with btn_col2:
            btn_title = "★ Saved" if is_bookmarked else "☆ Bookmark"
            if st.button(btn_title, key=f"bm_{item['pmid']}", use_container_width=True):
                toggle_bookmark(supabase_client, user_id, item, is_bookmarked)
                st.rerun()

        st.write("")


# -----------------------------------------------------------------------------
# VIEW 2: Student Library
# -----------------------------------------------------------------------------
elif st.session_state.active_view == "library":
    st.markdown("## 📚 My Library")
    st.caption("Your saved papers and study history.")

    user_id = st.session_state.user.id if st.session_state.user else None
    if not user_id:
        st.warning("🔒 Please sign in from the sidebar to sync and view your library.")

    lib_data = get_user_library(supabase_client, user_id)
    tab_bookmarks, tab_history = st.tabs(["🔖 Saved Bookmarks", "🕒 Reading History"])

    with tab_bookmarks:
        bookmarks = lib_data["bookmarks"]
        if bookmarks:
            for b in bookmarks:
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"**{b['title']}**")
                    st.caption(f"{b.get('journal', 'Journal')} ({b.get('year', '')}) &bull; PMID: {b['pmid']}")
                with c2:
                    if st.button("Open", key=f"lib_open_{b['pmid']}", use_container_width=True):
                        st.session_state.reader_pmid = b["pmid"]
                        st.session_state.active_view = "reader"
                        st.rerun()
                st.divider()
        else:
            st.caption("No bookmarked articles yet.")

    with tab_history:
        history = lib_data["history"]
        if history:
            for h in history:
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(f"**{h['title']}**")
                    st.caption(f"PMID: {h['pmid']} &bull; Studied previously")
                with c2:
                    if st.button("Review", key=f"hist_open_{h['pmid']}", use_container_width=True):
                        st.session_state.reader_pmid = h["pmid"]
                        st.session_state.active_view = "reader"
                        st.rerun()
                st.divider()
        else:
            st.caption("No read history recorded yet.")


# -----------------------------------------------------------------------------
# VIEW 3: Article Digest Reader
# -----------------------------------------------------------------------------
elif st.session_state.active_view == "reader":
    target_pmid = st.session_state.reader_pmid or "38157930"

    try:
        with st.spinner("Synthesizing pedagogical breakdown..."):
            paper = fetch_pubmed_article(target_pmid)
            user_id = st.session_state.user.id if st.session_state.user else None
            mark_article_read(supabase_client, user_id, paper)
            digest = generate_student_digest(paper, gemini_client)

        if st.button("← Back to Today's Feed"):
            st.session_state.active_view = "fyp"
            st.rerun()

        st.markdown(f"## {paper['title']}")
        authors_txt = ", ".join(paper["authors"][:4]) + (" et al." if len(paper["authors"]) > 4 else "")
        doi_suffix = f" &bull; DOI: {paper['doi']}" if paper["doi"] else ""

        st.markdown(
            f"""
            <div style="font-size: 0.9rem; color: #475569; margin-bottom: 1.25rem;">
                🏛️ <strong>{paper['journal']}</strong> ({paper['year']}) &bull; PMID: {paper['pmid']}{doi_suffix}
                <br/>✍️ {authors_txt}
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_gdoc, col_pubmed, _ = st.columns([2, 2, 6])
        with col_gdoc:
            encoded_title = urllib.parse.quote(paper["title"])
            st.link_button("↗ Export to Google Doc", f"https://docs.google.com/document/create?title={encoded_title}", use_container_width=True)
        with col_pubmed:
            st.link_button("View on PubMed ↗", f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/", use_container_width=True)

        st.write("")

        # Pedagogical Lesson Sections
        st.markdown(
            f"""
            <div class="lesson-section">
                <h4 style="color: #4338CA; margin-bottom: 0.4rem;">🎯 The Core Scientific Problem</h4>
                <p style="line-height: 1.6; color: #1E293B;">{digest['dilemma']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="lesson-section">
                <h4 style="color: #0284C7; margin-bottom: 0.4rem;">🔬 Biological Mechanism & Methods</h4>
                <p style="line-height: 1.6; color: #1E293B;">{digest['how_it_works']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### ⚡ High-Yield Student Takeaways")
        for bullet in digest["bullets"]:
            st.markdown(f'<div class="takeaway-bullet">{bullet}</div>', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="lesson-section" style="border-left: 4px solid #F59E0B; margin-top: 1rem;">
                <h4 style="color: #B45309; margin-bottom: 0.4rem;">⚠️ Critical Perspective & Nuance</h4>
                <p style="line-height: 1.6; color: #1E293B;">{digest['nuance']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # High-Contrast Unedited Abstract Expander
        with st.expander("📄 View Original Unedited Abstract"):
            st.markdown(
                f"""
                <div class="abstract-text-container">
                    {paper['abstract']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    except Exception as exc:
        st.error(f"Error loading study: {exc}")
        if st.button("Return to Feed"):
            st.session_state.active_view = "fyp"
            st.rerun()