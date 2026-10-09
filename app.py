import base64
import html
import json
import os
import re
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
# Styling
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        color: #0F172A;
    }

    .stApp {
        background-color: #F8FAFC;
    }

    .app-brand {
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #4338CA 0%, #0284C7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }

    /* News card container */
    .news-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }

    .news-card:hover {
        border-color: #CBD5E1;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }

    .news-headline {
        font-family: 'Newsreader', serif;
        font-size: 1.35rem;
        font-weight: 500;
        color: #0F172A;
        line-height: 1.35;
        margin-bottom: 0.5rem;
    }

    .why-it-matters {
        background: #F0FDF4;
        border-left: 3px solid #22C55E;
        padding: 0.6rem 0.8rem;
        border-radius: 0 6px 6px 0;
        color: #166534;
        font-size: 0.9rem;
        line-height: 1.5;
        margin: 0.6rem 0;
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

    .lesson-section {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    .takeaway-bullet {
        padding: 0.6rem 0.75rem;
        background: #F1F5F9;
        border-left: 3px solid #6366F1;
        border-radius: 0 6px 6px 0;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Clients & Initialization
# -----------------------------------------------------------------------------
AVAILABLE_INTERESTS = [
    "CRISPR & Gene Editing",
    "AI in Healthcare",
    "Neuroscience",
    "Immunology & Vaccines",
    "Synthetic Biology",
    "Longevity & Aging",
    "Cancer Oncology",
    "Stem Cells",
]


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


# Initialize Session State
if "user" not in st.session_state:
    st.session_state.user = None
if "user_interests" not in st.session_state:
    st.session_state.user_interests = ["CRISPR & Gene Editing", "AI in Healthcare"]
if "active_view" not in st.session_state:
    st.session_state.active_view = "fyp"  # "fyp", "reader", "library"
if "reader_pmid" not in st.session_state:
    st.session_state.reader_pmid = None
if "gemini_fyp_cache" not in st.session_state:
    st.session_state.gemini_fyp_cache = {}


# -----------------------------------------------------------------------------
# NCBI Entrez Fetch Helpers
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_pubmed_by_interests(interests: List[str], max_results: int = 8) -> List[str]:
    """Queries PubMed for recent impactful papers matching the given interest topics."""
    if not interests:
        interests = ["Biomedical Research"]
    clean_terms = [f'"{term}"[Title/Abstract]' for term in interests]
    query = f"({' OR '.join(clean_terms)}) AND hasabstract[text]"

    try:
        with Entrez.esearch(db="pubmed", term=query, sort="pub_date", retmax=max_results) as handle:
            record = Entrez.read(handle)
        return record.get("IdList", [])
    except Exception as e:
        st.warning(f"PubMed search encountered a transient issue: {e}")
        return ["38157930", "32284366"]  # Fallbacks


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
# Google Gemini News & Pedagogical Digest Engine
# -----------------------------------------------------------------------------
def batch_summarize_feed(papers: List[Dict], gemini_client: Optional[genai.Client]) -> List[Dict]:
    """Transforms raw papers into accessible student news items with headlines and difficulty ratings."""
    processed = []
    
    # If no Gemini client, provide deterministic fallback representations
    if not gemini_client:
        for p in papers:
            processed.append({
                "pmid": p["pmid"],
                "headline": p["title"],
                "why_it_matters": p["abstract"][:180] + "...",
                "difficulty": "Intermediate",
                "journal": p["journal"],
                "year": p["year"],
            })
        return processed

    # Build batch generation prompt for Gemini 1.5 Flash
    papers_payload = [
        {"id": p["pmid"], "title": p["title"], "abstract": p["abstract"][:600]}
        for p in papers
    ]

    prompt = f"""You are an editor for 'Abstracted', a student-friendly science news site.
Transform the following biomedical papers into accessible science news items.

Papers to process:
{json.dumps(papers_payload)}

Return ONLY a JSON list of objects matching this exact schema:
[
  {{
    "pmid": "paper pmid string",
    "headline": "Punchy, exciting, jargon-free student newspaper headline (under 14 words)",
    "why_it_matters": "Exactly two student-friendly sentences explaining why this discovery matters to everyday biology or medicine.",
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
                temperature=0.3,
            ),
        )
        data = json.loads(response.text)
        data_by_id = {item["pmid"]: item for item in data if "pmid" in item}

        for p in papers:
            meta = data_by_id.get(p["pmid"], {})
            processed.append({
                "pmid": p["pmid"],
                "headline": meta.get("headline", p["title"]),
                "why_it_matters": meta.get("why_it_matters", p["abstract"][:150] + "..."),
                "difficulty": meta.get("difficulty", "Intermediate"),
                "journal": p["journal"],
                "year": p["year"],
            })
    except Exception as e:
        # Graceful fallback on LLM error
        for p in papers:
            processed.append({
                "pmid": p["pmid"],
                "headline": p["title"],
                "why_it_matters": p["abstract"][:160] + "...",
                "difficulty": "Intermediate",
                "journal": p["journal"],
                "year": p["year"],
            })
    return processed


def generate_student_digest(article: Dict, gemini_client: Optional[genai.Client]) -> Dict:
    """Generates an organized, student-accessible lesson breakdown."""
    if not gemini_client:
        return {
            "dilemma": f"Study evaluates foundational questions addressed in: {article['title']}",
            "how_it_works": article["abstract"],
            "bullets": ["High-yield clinical and experimental observations detailed in original abstract."],
            "nuance": "Findings must be validated through further reproducible clinical cohorts.",
        }

    prompt = f"""Create an engaging study digest for a life-sciences undergraduate.
Paper Title: {article['title']}
Journal: {article['journal']} ({article['year']})
Abstract: {article['abstract']}

Return ONLY valid JSON with this schema:
{{
  "dilemma": "Clear, exciting paragraph outlining what problem the researchers were trying to solve and why previous solutions fell short.",
  "how_it_works": "Plain-English walkthrough of the experiment, model organism/data used, and biological mechanism found.",
  "bullets": [
    "Key takeaway 1 (direct finding with numbers/metrics if present)",
    "Key takeaway 2 (biological implication)",
    "Key takeaway 3 (practical future application)"
  ],
  "nuance": "One critical constraint, limitation, or caveat to remember before over-hyping this paper."
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
            "dilemma": article["abstract"][:300] + "...",
            "how_it_works": article["abstract"][300:700] if len(article["abstract"]) > 300 else article["abstract"],
            "bullets": ["Primary experimental endpoints recorded in PubMed abstract."],
            "nuance": "Clinical translation requires broader cohort studies.",
        }


# -----------------------------------------------------------------------------
# Supabase Persistence Helpers
# -----------------------------------------------------------------------------
def load_user_profile(sb: Client, user_id: str):
    try:
        res = sb.table("profiles").select("*").eq("id", user_id).execute()
        if res.data:
            interests = res.data[0].get("interests", [])
            if interests:
                st.session_state.user_interests = interests
    except Exception:
        pass


def save_user_interests(sb: Optional[Client], user_id: Optional[str], interests: List[str]):
    st.session_state.user_interests = interests
    if sb and user_id:
        try:
            sb.table("profiles").upsert({"id": user_id, "interests": interests}).execute()
        except Exception as e:
            st.error(f"Failed to sync interests: {e}")


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
    new_status = not current_status
    if sb and user_id:
        try:
            sb.table("user_library").upsert({
                "user_id": user_id,
                "pmid": article_dict["pmid"],
                "title": article_dict.get("headline", article_dict.get("title", "")),
                "journal": article_dict.get("journal", ""),
                "year": str(article_dict.get("year", "2024")),
                "is_bookmarked": new_status,
            }, on_conflict="user_id,pmid").execute()
        except Exception as e:
            st.warning(f"Database sync failed: {e}")
    return new_status


def get_user_library(sb: Optional[Client], user_id: Optional[str]):
    if not (sb and user_id):
        return {"bookmarks": [], "history": []}
    try:
        res = sb.table("user_library").select("*").eq("user_id", user_id).order("last_accessed", desc=True).execute()
        records = res.data or []
        bookmarks = [r for r in records if r.get("is_bookmarked")]
        history = [r for r in records if r.get("is_read")]
        return {"bookmarks": bookmarks, "history": history}
    except Exception:
        return {"bookmarks": [], "history": []}


# -----------------------------------------------------------------------------
# Sidebar: Auth, Interests & Navigation
# -----------------------------------------------------------------------------
supabase_client = get_supabase_client()
gemini_client = get_gemini_client()

with st.sidebar:
    st.markdown('<div class="app-brand">Abstracted.</div>', unsafe_allow_html=True)
    st.caption("Personalized Science News & Digests")
    st.write("")

    # --- Supabase Authentication ---
    st.markdown("#### 👤 Student Account")
    if supabase_client:
        if not st.session_state.user:
            auth_tab1, auth_tab2 = st.tabs(["Log In", "Sign Up"])
            with auth_tab1:
                login_email = st.text_input("Email", key="login_email")
                login_pwd = st.text_input("Password", type="password", key="login_pwd")
                if st.button("Log In", use_container_width=True, type="primary"):
                    try:
                        res = supabase_client.auth.sign_in_with_password({"email": login_email, "password": login_pwd})
                        st.session_state.user = res.user
                        load_user_profile(supabase_client, res.user.id)
                        st.rerun()
                    except Exception as err:
                        st.error(f"Login failed: {err}")

            with auth_tab2:
                signup_email = st.text_input("Email", key="signup_email")
                signup_pwd = st.text_input("Password", type="password", key="signup_pwd")
                if st.button("Create Account", use_container_width=True):
                    try:
                        res = supabase_client.auth.sign_up({"email": signup_email, "password": signup_pwd})
                        if res.user:
                            st.success("Account created! Please log in.")
                    except Exception as err:
                        st.error(f"Signup failed: {err}")
        else:
            st.success(f"Logged in as **{st.session_state.user.email}**")
            if st.button("Log Out", use_container_width=True):
                supabase_client.auth.sign_out()
                st.session_state.user = None
                st.rerun()
    else:
        st.info("💡 Add `SUPABASE_URL` and `SUPABASE_KEY` to `.streamlit/secrets.toml` to enable persistent cloud sync.")

    st.divider()

    # --- Navigation Section ---
    st.markdown("#### 🧭 Feed Channels")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("📰 For You", use_container_width=True, type="primary" if st.session_state.active_view == "fyp" else "secondary"):
            st.session_state.active_view = "fyp"
            st.rerun()
    with col_nav2:
        if st.button("📚 Library", use_container_width=True, type="primary" if st.session_state.active_view == "library" else "secondary"):
            st.session_state.active_view = "library"
            st.rerun()

    st.divider()

    # --- Topic Preferences ---
    st.markdown("#### 🧬 My Research Interests")
    selected_interests = st.multiselect(
        "Topics for Your Daily Feed:",
        options=AVAILABLE_INTERESTS,
        default=st.session_state.user_interests,
    )
    if st.button("Save Preferences", use_container_width=True):
        user_id = st.session_state.user.id if st.session_state.user else None
        save_user_interests(supabase_client, user_id, selected_interests)
        st.session_state.gemini_fyp_cache.clear()  # Invalidate feed cache
        st.session_state.active_view = "fyp"
        st.rerun()

    st.divider()
    # Search by Specific PMID
    st.markdown("#### 🔎 Lookup Paper")
    lookup_pmid = st.text_input("PubMed ID (PMID)", placeholder="e.g. 38157930")
    if st.button("Open Paper", use_container_width=True) and lookup_pmid.strip():
        st.session_state.reader_pmid = lookup_pmid.strip()
        st.session_state.active_view = "reader"
        st.rerun()


# -----------------------------------------------------------------------------
# Main View 1: Personalized "For You" Feed (FYP)
# -----------------------------------------------------------------------------
if st.session_state.active_view == "fyp":
    st.markdown("## 📰 For You")
    st.caption("Personalized science discoveries synthesized for students from PubMed.")

    interests_key = "-".join(sorted(st.session_state.user_interests))
    with st.spinner("Fetching today's top papers and generating student news cards..."):
        if interests_key not in st.session_state.gemini_fyp_cache:
            pmid_list = search_pubmed_by_interests(st.session_state.user_interests, max_results=8)
            raw_papers = []
            for pid in pmid_list:
                try:
                    raw_papers.append(fetch_pubmed_article(pid))
                except Exception:
                    continue

            feed_news = batch_summarize_feed(raw_papers, gemini_client)
            st.session_state.gemini_fyp_cache[interests_key] = feed_news

        news_items = st.session_state.gemini_fyp_cache.get(interests_key, [])

    if not news_items:
        st.info("No papers found matching your current interest filters. Try adding more topics from the sidebar.")

    # Render Newsfeed Cards
    user_id = st.session_state.user.id if st.session_state.user else None
    user_lib = get_user_library(supabase_client, user_id)
    bookmarked_pmids = {b["pmid"] for b in user_lib["bookmarks"]}

    for item in news_items:
        diff_class = f"badge-{item['difficulty'].lower()}"
        is_bookmarked = item["pmid"] in bookmarked_pmids

        st.markdown(
            f"""
            <div class="news-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                    <span style="font-size: 0.82rem; color: #64748B; font-weight: 500;">🏛️ {item['journal']} ({item['year']}) &bull; PMID: {item['pmid']}</span>
                    <span class="badge {diff_class}">{item['difficulty']}</span>
                </div>
                <div class="news-headline">{item['headline']}</div>
                <div class="why-it-matters"><strong>💡 Why It Matters:</strong> {item['why_it_matters']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_act1, col_act2, _ = st.columns([1.5, 1.5, 7])
        with col_act1:
            if st.button("📖 Read Now", key=f"read_{item['pmid']}", use_container_width=True, type="primary"):
                st.session_state.reader_pmid = item["pmid"]
                st.session_state.active_view = "reader"
                st.rerun()

        with col_act2:
            bm_label = "★ Saved" if is_bookmarked else "☆ Bookmark"
            if st.button(bm_label, key=f"bm_{item['pmid']}", use_container_width=True):
                toggle_bookmark(supabase_client, user_id, item, is_bookmarked)
                st.rerun()


# -----------------------------------------------------------------------------
# Main View 2: Student Library (Saved & History)
# -----------------------------------------------------------------------------
elif st.session_state.active_view == "library":
    st.markdown("## 📚 My Library")
    st.caption("Your saved reading bookmarks and studied articles.")

    user_id = st.session_state.user.id if st.session_state.user else None
    if not user_id:
        st.info("Log in using the sidebar to sync your saved papers across devices.")

    lib_data = get_user_library(supabase_client, user_id)
    tab_bookmarks, tab_history = st.tabs(["🔖 Saved Bookmarks", "🕒 Reading History"])

    with tab_bookmarks:
        bookmarks = lib_data["bookmarks"]
        if bookmarks:
            for b in bookmarks:
                col_item, col_btn = st.columns([6, 1])
                with col_item:
                    st.markdown(f"**{b['title']}**")
                    st.caption(f"{b.get('journal', 'Journal')} ({b.get('year', '')}) &bull; PMID: {b['pmid']}")
                with col_btn:
                    if st.button("Open", key=f"lib_open_{b['pmid']}", use_container_width=True):
                        st.session_state.reader_pmid = b["pmid"]
                        st.session_state.active_view = "reader"
                        st.rerun()
                st.divider()
        else:
            st.caption("No bookmarked articles yet. Click '☆ Bookmark' on any article in your feed.")

    with tab_history:
        history = lib_data["history"]
        if history:
            for h in history:
                col_item, col_btn = st.columns([6, 1])
                with col_item:
                    st.markdown(f"**{h['title']}**")
                    st.caption(f"PMID: {h['pmid']} &bull; Studied recently")
                with col_btn:
                    if st.button("Revisit", key=f"hist_open_{h['pmid']}", use_container_width=True):
                        st.session_state.reader_pmid = h["pmid"]
                        st.session_state.active_view = "reader"
                        st.rerun()
                st.divider()
        else:
            st.caption("No read history recorded yet. Open an article to start reading.")


# -----------------------------------------------------------------------------
# Main View 3: Single Article Reader & Lesson Digest
# -----------------------------------------------------------------------------
elif st.session_state.active_view == "reader":
    target_pmid = st.session_state.reader_pmid or "38157930"

    try:
        with st.spinner("Retrieving paper from NCBI & structuring digest..."):
            paper_details = fetch_pubmed_article(target_pmid)
            user_id = st.session_state.user.id if st.session_state.user else None
            mark_article_read(supabase_client, user_id, paper_details)
            digest = generate_student_digest(paper_details, gemini_client)

        if st.button("← Back to Newsfeed"):
            st.session_state.active_view = "fyp"
            st.rerun()

        st.markdown(f"## {paper_details['title']}")
        authors_display = ", ".join(paper_details["authors"][:4]) + (" et al." if len(paper_details["authors"]) > 4 else "")
        doi_badge = f" &bull; DOI: {paper_details['doi']}" if paper_details["doi"] else ""

        st.markdown(
            f"""
            <div style="font-size: 0.9rem; color: #64748B; margin-bottom: 1.25rem;">
                🏛️ <strong>{paper_details['journal']}</strong> ({paper_details['year']}) &bull; PMID: {paper_details['pmid']}{doi_badge}
                <br/>✍️ {authors_display}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Export & Bookmark Options
        col_act1, col_act2, col_act3 = st.columns([2, 2, 6])
        with col_act1:
            encoded_title = urllib.parse.quote(paper_details["title"])
            st.link_button("↗ Open Google Doc", f"https://docs.google.com/document/create?title={encoded_title}", use_container_width=True)
        with col_act2:
            st.link_button("PubMed Source ↗", f"https://pubmed.ncbi.nlm.nih.gov/{paper_details['pmid']}/", use_container_width=True)

        st.write("")

        # Lesson Digest Sections
        st.markdown(
            f"""
            <div class="lesson-section">
                <h4 style="color: #4338CA; margin-bottom: 0.4rem;">🎯 The Research Dilemma</h4>
                <p style="line-height: 1.6; color: #334155;">{digest['dilemma']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="lesson-section">
                <h4 style="color: #0284C7; margin-bottom: 0.4rem;">🔬 How the Experiment Works</h4>
                <p style="line-height: 1.6; color: #334155;">{digest['how_it_works']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### ⚡ High-Yield Student Takeaways")
        for bullet in digest["bullets"]:
            st.markdown(f'<div class="takeaway-bullet">{bullet}</div>', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="lesson-section" style="border-left: 4px solid #EAB308; margin-top: 1.2rem;">
                <h4 style="color: #A16207; margin-bottom: 0.4rem;">⚠️ Critical Perspective & Nuance</h4>
                <p style="line-height: 1.6; color: #475569;">{digest['nuance']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("📄 View Original Unedited Abstract"):
            st.write(paper_details["abstract"])

    except Exception as exc:
        st.error(f"Failed to load paper details: {exc}")
        if st.button("Return to Feed"):
            st.session_state.active_view = "fyp"
            st.rerun()