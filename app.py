import html
import json
import os
import random
import re
import urllib.parse
from typing import Dict, List, Optional

from Bio import Entrez
from google import genai
from google.genai import types
import streamlit as st
from supabase import Client, create_client

# -----------------------------------------------------------------------------
# Streamlit Page Configuration (Warm Dark Academia)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Abstracted",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

Entrez.email = "abstracted.app@internal.service"
Entrez.tool = "AbstractedApp"

HIGH_IMPACT_JOURNALS = {
    "nature", "science", "cell", "new england journal of medicine",
    "nejm", "the lancet", "lancet", "jama", "proceedings of the national academy of sciences",
    "pnas", "nature medicine", "nature biotechnology", "nature genetics",
    "cell stem cell", "immunity", "cancer cell"
}

# -----------------------------------------------------------------------------
# Text Sanitization Helper
# -----------------------------------------------------------------------------
def clean_text(raw_str: Optional[str]) -> str:
    """Strips XML/HTML tags and decodes HTML entities."""
    if not raw_str:
        return ""
    text = str(raw_str)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# -----------------------------------------------------------------------------
# Warm Dark Academia CSS Architecture & Overrides
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    /* 1. Ambient Warm Lamplight & Classic Book Typography */
    header[data-testid="stHeader"] {
        visibility: hidden !important;
        height: 0px !important;
    }

    .stApp {
        margin-top: 0px !important;
        background: radial-gradient(circle at 50% 0%, #1c261f 0%, #0c120e 100%) !important;
        color: #EAE3D2 !important;
        font-family: 'Lora', serif !important;
    }

    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Playfair Display', serif !important;
        color: #F5EFEB !important;
        letter-spacing: -0.01em;
    }

    p, span, label, div {
        font-family: 'Lora', serif;
        color: #EAE3D2;
    }

    .stCaption, [data-testid="stCaptionContainer"] {
        color: #A89C8A !important;
        font-family: 'Lora', serif !important;
        font-style: italic;
    }

    /* 2. Dark Wood & Moss Containers */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(20, 30, 24, 0.72) !important;
        border: 1px solid #4a3f35 !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4) !important;
        padding: 0.75rem 1rem !important;
    }

    /* 3. Comprehensive Button Theming (Fixes Link Buttons & Reader Buttons) */
    div[data-testid="stButton"] button, 
    div[data-testid="stLinkButton"] a,
    div[data-testid="stDownloadButton"] button,
    a[kind="secondary"],
    a[kind="primary"],
    button[kind="secondary"],
    button[kind="primary"] {
        background-color: #2C3E2D !important;
        color: #EAE3D2 !important;
        border: 1px solid #4a3f35 !important;
        border-radius: 6px !important;
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
        text-decoration: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
    }

    div[data-testid="stButton"] button:hover, 
    div[data-testid="stLinkButton"] a:hover,
    div[data-testid="stDownloadButton"] button:hover,
    a[kind="secondary"]:hover,
    a[kind="primary"]:hover,
    button[kind="secondary"]:hover,
    button[kind="primary"]:hover {
        background-color: #3E4F3E !important;
        border-color: #705D4A !important;
        color: #FFFFFF !important;
    }

    div[data-testid="stButton"] button p,
    div[data-testid="stButton"] button span,
    div[data-testid="stLinkButton"] a p,
    div[data-testid="stLinkButton"] a span,
    div[data-testid="stDownloadButton"] button p,
    div[data-testid="stDownloadButton"] button span {
        color: #EAE3D2 !important;
        font-family: 'Playfair Display', serif !important;
    }

    div[data-testid="stButton"] button:hover p,
    div[data-testid="stButton"] button:hover span,
    div[data-testid="stLinkButton"] a:hover p,
    div[data-testid="stLinkButton"] a:hover span {
        color: #FFFFFF !important;
    }

    /* Logout Button Styling */
    div[data-testid="stButton"].danger-btn button {
        background-color: #3E1D1A !important;
        border: 1px solid #6E322D !important;
    }
    div[data-testid="stButton"].danger-btn button p,
    div[data-testid="stButton"].danger-btn button span {
        color: #F2D2CF !important;
        font-family: 'Playfair Display', serif !important;
    }
    div[data-testid="stButton"].danger-btn button:hover {
        background-color: #522723 !important;
        border-color: #8C4039 !important;
    }

    /* 4. Delicate Library Label Badges */
    .lib-badge {
        display: inline-block;
        background: rgba(234, 227, 210, 0.09);
        border: 1px solid #705D4A;
        color: #D4C4A8 !important;
        padding: 0.2rem 0.65rem;
        border-radius: 4px;
        font-family: 'Lora', serif;
        font-size: 0.78rem;
        letter-spacing: 0.03em;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
    }
    .lib-badge-gold {
        background: rgba(212, 175, 55, 0.12);
        border: 1px solid #9E8232;
        color: #E5C775 !important;
    }

    /* 5. Deep Oak Study Sidebar & Artifact Fix */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        background-color: #0E1611 !important;
        border-right: 1px solid #2B382F !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        font-family: 'Playfair Display', serif !important;
        color: #F5EFEB !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {
        font-family: 'Lora', serif;
        color: #EAE3D2 !important;
    }

    /* Hide the sidebar collapse button to eliminate keyboard_double hover artifact */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* 6. BaseWeb Dropdowns & Popovers Strict Overrides (Portal Targeting) */
    .stSelectbox div[data-baseweb="select"], 
    .stMultiSelect div[data-baseweb="select"] {
        background-color: rgba(20, 30, 24, 0.85) !important;
        border-color: #4a3f35 !important;
    }
    .stSelectbox div[data-baseweb="select"] span,
    .stMultiSelect div[data-baseweb="select"] span,
    .stSelectbox div[data-baseweb="select"] div,
    .stMultiSelect div[data-baseweb="select"] div {
        color: #EAE3D2 !important;
    }

    /* Target the root portal for dropdown menus */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    ul[data-baseweb="menu"],
    div[data-testid="stVirtualDropdown"] {
        background-color: #162019 !important;
        border-color: #4a3f35 !important;
    }

    /* Dropdown Options */
    li[role="option"] {
        background-color: #162019 !important;
        color: #EAE3D2 !important;
        font-family: 'Lora', serif !important;
    }

    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #2C3E2D !important;
        color: #D4AF37 !important;
    }

    /* Multiselect Tags */
    span[data-baseweb="tag"],
    div[data-baseweb="tag"] {
        background-color: #2C3E2D !important;
        color: #EAE3D2 !important;
        border: 1px solid #4a3f35 !important;
    }
    span[data-baseweb="tag"] span,
    div[data-baseweb="tag"] span {
        color: #EAE3D2 !important;
        font-family: 'Lora', serif !important;
    }

    /* 7. Input Fields */
    input[type="text"], input[type="password"] {
        background-color: #121A15 !important;
        color: #EAE3D2 !important;
        border: 1px solid #4a3f35 !important;
        border-radius: 6px !important;
        font-family: 'Lora', serif !important;
    }
    input[type="text"]:focus, input[type="password"]:focus {
        border-color: #D4AF37 !important;
        box-shadow: 0 0 6px rgba(212, 175, 55, 0.3) !important;
    }

    /* 8. Toasts & Alerts */
    div[data-testid="stToast"] {
        background-color: #17241B !important;
        border: 1px solid #5A4E3E !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6) !important;
        border-radius: 8px !important;
        color: #EAE3D2 !important;
    }
    div[data-testid="stToast"] p,
    div[data-testid="stToast"] span,
    div[data-testid="stToast"] div {
        color: #EAE3D2 !important;
        font-family: 'Lora', serif !important;
    }

    .stAlert, div[data-testid="stAlert"] {
        background-color: rgba(24, 34, 27, 0.85) !important;
        border: 1px solid #4a3f35 !important;
        color: #EAE3D2 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] div {
        color: #EAE3D2 !important;
        font-family: 'Lora', serif !important;
    }

    /* 9. Tabs & Expanders */
    [data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {
        color: #A89C8A !important;
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        background-color: rgba(44, 62, 45, 0.4) !important;
        border-bottom: 2px solid #D4AF37 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        color: #EAE3D2 !important;
        font-weight: 700 !important;
    }

    [data-testid="stExpander"] {
        background-color: rgba(20, 30, 24, 0.75) !important;
        border: 1px solid #4a3f35 !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] details summary {
        background-color: rgba(28, 40, 33, 0.6) !important;
        color: #EAE3D2 !important;
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
        background-color: rgba(18, 26, 21, 0.85) !important;
        color: #D6CCBD !important;
    }

    /* 10. Landing Hero */
    .landing-hero {
        max-width: 900px;
        margin: 3.5rem auto 1.5rem auto;
        text-align: center;
    }
    .hero-title-serif {
        font-family: 'Playfair Display', serif;
        font-size: clamp(3.2rem, 8vw, 5.8rem);
        font-weight: 600;
        letter-spacing: 0.08em;
        line-height: 1.05;
        color: #F5EFEB !important;
        margin-bottom: 0.85rem;
        text-transform: uppercase;
        text-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Research Topic Taxonomy
# -----------------------------------------------------------------------------
DEFAULT_TOPICS_TAXONOMY = {
    "Genomics & Engineering": [
        "CRISPR",
        "Gene Therapy",
        "Synthetic Biology",
        "Base Editing",
    ],
    "Neuroscience & Mind": [
        "Neuroplasticity",
        "Alzheimer's Disease",
        "Neural Interfaces",
        "Brain-Computer Interface",
    ],
    "Therapeutics & Medicine": [
        "mRNA Vaccines",
        "Immunotherapy",
        "CAR-T Cell Therapy",
        "Antibiotic Resistance",
    ],
    "AI & Computational Bio": [
        "AI in Medicine",
        "AlphaFold",
        "Protein Design",
        "Machine Learning Diagnostics",
    ],
    "Cellular Biology & Longevity": [
        "Cellular Senescence",
        "Stem Cells",
        "Mitochondrial Biology",
        "Telomeres",
    ],
}


@st.cache_data(ttl=300)
def load_research_topics() -> Dict[str, List[str]]:
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
# Clients & Session State Initialization
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
        # Preserve client instance across Streamlit reruns
        if "supabase_client" not in st.session_state or st.session_state.supabase_client is None:
            st.session_state.supabase_client = create_client(url, key)

        # Restore user authentication header into PostgREST client if logged in
        if "auth_token" in st.session_state and st.session_state.auth_token:
            st.session_state.supabase_client.postgrest.auth(st.session_state.auth_token)

        return st.session_state.supabase_client
    except Exception:
        return None


if "user" not in st.session_state:
    st.session_state.user = None
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "user_display_name" not in st.session_state:
    st.session_state.user_display_name = ""
if "user_interests" not in st.session_state:
    st.session_state.user_interests = ["CRISPR", "AI in Medicine"]
if "active_view" not in st.session_state:
    st.session_state.active_view = "fyp"
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "landing"
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "signin"
if "reader_pmid" not in st.session_state:
    st.session_state.reader_pmid = None
if "gemini_fyp_cache" not in st.session_state:
    st.session_state.gemini_fyp_cache = {}
if "search_mode" not in st.session_state:
    st.session_state.search_mode = None
if "greeting_phrase" not in st.session_state:
    st.session_state.greeting_phrase = random.choice(["Hi", "Hello there", "Howdy"])
if "local_bookmarks" not in st.session_state:
    st.session_state.local_bookmarks = set()
if "local_saved_items" not in st.session_state:
    st.session_state.local_saved_items = {}

# Hide Sidebar for Logged-Out Visitors
if st.session_state.user is None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], section[data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# NCBI Entrez Fetching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_pubmed_by_interests(interests: List[str], max_results: int = 8) -> List[str]:
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
    title = clean_text(art.get("ArticleTitle", "Untitled Article").rstrip("."))

    authors = [
        clean_text(f"{a.get('LastName', '')} {a.get('Initials', '')}".strip())
        for a in art.get("AuthorList", [])
        if a.get("LastName")
    ]

    journal_obj = art.get("Journal", {})
    journal = clean_text(journal_obj.get("ISOAbbreviation") or journal_obj.get("Title") or "Medical Journal")
    pub_date = clean_text(str(journal_obj.get("JournalIssue", {}).get("PubDate", {}).get("Year", "2024")))

    doi = None
    for eid in art.get("ELocationID", []):
        if getattr(eid, "attributes", {}).get("EIdType") == "doi":
            doi = clean_text(str(eid))

    raw_abstract = art.get("Abstract", {}).get("AbstractText", [])
    abstract_text = ""
    if isinstance(raw_abstract, list):
        abstract_text = " ".join([clean_text(str(p)) for p in raw_abstract])
    elif raw_abstract:
        abstract_text = clean_text(str(raw_abstract))

    if not abstract_text:
        abstract_text = "Abstract text not indexed for this record."

    word_count = len(abstract_text.split())
    read_minutes = max(1, round(word_count / 200))
    journal_lower = journal.lower()
    is_high_impact = any(hij in journal_lower for hij in HIGH_IMPACT_JOURNALS)

    return {
        "pmid": clean_pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": pub_date,
        "doi": doi,
        "abstract": abstract_text,
        "read_time_min": read_minutes,
        "is_high_impact": is_high_impact,
    }


# -----------------------------------------------------------------------------
# Google Gemini Batch Feed & Pedagogical Digest Engine
# -----------------------------------------------------------------------------
def batch_summarize_feed(papers: List[Dict], gemini_client: Optional[genai.Client]) -> List[Dict]:
    processed = []
    if not gemini_client:
        for p in papers:
            processed.append({
                "pmid": p["pmid"],
                "headline": clean_text(p["title"]),
                "preview_sentences": "This investigation examines cellular response signatures under targeted laboratory conditions. The reported results illustrate potential utility for translational molecular discovery.",
                "why_it_matters": "By identifying these regulatory pathways, researchers can design therapies that spare adjacent healthy cells. Preclinical trials confirmed consistent improvements in phenotypic rescue. These findings offer an actionable basis for creating next-generation therapeutic candidates.",
                "difficulty": "Intermediate",
                "concepts": ["Target Engagement", "Preclinical Assay", "Phenotypic Screening"],
                "journal": clean_text(p["journal"]),
                "year": clean_text(p["year"]),
                "read_time_min": p.get("read_time_min", 2),
                "is_high_impact": p.get("is_high_impact", False),
            })
        return processed

    payload = [
        {"id": p["pmid"], "title": clean_text(p["title"]), "abstract": clean_text(p["abstract"][:900])}
        for p in papers
    ]

    prompt = f"""You are an editor for 'Abstracted', transforming complex biomedical literature for students.

Rules:
1. "headline": Punchy, jargon-free title under 14 words. Do NOT include raw HTML/XML tags.
2. "preview_sentences": Exactly two full, grammatical sentences summarizing the core finding. Never truncate with an ellipsis. Every sentence must end with a period.
3. "why_it_matters": Exactly 3 or 4 full sentences explaining the clinical or biological impact. Never truncate with an ellipsis. Every sentence must end with a period.
4. "difficulty": 'Beginner', 'Intermediate', or 'Advanced'.
5. "concepts": Array of exactly 3 concise techniques, pathways, or concepts to learn. Do not include raw HTML/XML tags.

Papers:
{json.dumps(payload)}

Return strictly valid JSON matching this schema:
[
  {{
    "pmid": "string",
    "headline": "string",
    "preview_sentences": "Sentence one. Sentence two.",
    "why_it_matters": "Sentence one. Sentence two. Sentence three. Sentence four.",
    "difficulty": "Beginner" | "Intermediate" | "Advanced",
    "concepts": ["Concept 1", "Concept 2", "Concept 3"]
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
            prev = clean_text(meta.get("preview_sentences", ""))
            wim = clean_text(meta.get("why_it_matters", ""))
            raw_concepts = meta.get("concepts", ["Molecular Assay", "Cell Signaling", "Translational Model"])
            clean_concepts = [clean_text(c) for c in raw_concepts]

            if not prev.endswith("."):
                prev += "."
            if not wim.endswith("."):
                wim += "."

            processed.append({
                "pmid": p["pmid"],
                "headline": clean_text(meta.get("headline", p["title"])),
                "preview_sentences": prev,
                "why_it_matters": wim,
                "difficulty": clean_text(meta.get("difficulty", "Intermediate")),
                "concepts": clean_concepts[:3],
                "journal": clean_text(p["journal"]),
                "year": clean_text(p["year"]),
                "read_time_min": p.get("read_time_min", 2),
                "is_high_impact": p.get("is_high_impact", False),
            })
    except Exception:
        for p in papers:
            processed.append({
                "pmid": p["pmid"],
                "headline": clean_text(p["title"]),
                "preview_sentences": "This study analyzes biological mechanisms observed in laboratory models. The findings outline potential applications in disease monitoring and health interventions.",
                "why_it_matters": "Understanding this pathway enables researchers to isolate specific cellular targets without disrupting healthy tissue. The experiment demonstrates measurable improvements in preclinical efficacy. These findings offer actionable insights for designing next-generation therapeutic candidates.",
                "difficulty": "Intermediate",
                "concepts": ["Genomics", "Pharmacology", "Translational Medicine"],
                "journal": clean_text(p["journal"]),
                "year": clean_text(p["year"]),
                "read_time_min": p.get("read_time_min", 2),
                "is_high_impact": p.get("is_high_impact", False),
            })
    return processed


def generate_student_digest(article: Dict, gemini_client: Optional[genai.Client]) -> Dict:
    clean_title = clean_text(article["title"])
    clean_abstract = clean_text(article["abstract"])

    if not gemini_client:
        return {
            "context": f"This study evaluates foundational biological questions in {clean_text(article['journal'])}.",
            "abstract_summary": "This study investigates fundamental mechanisms underlying cellular and genetic regulation. Researchers developed targeted assays to test how biological interventions alter molecular phenotypes. Quantitative measurements demonstrated substantial changes across experimental groups compared to control benchmarks. The experimental results reveal previously uncharacterized pathways that influence disease progression and recovery. Further analyses confirmed that target engagement produced consistent, reproducible modifications in cell behavior. The authors conclude that these molecular markers offer a strong framework for therapeutic development. Future studies will need to confirm these findings across broader preclinical cohorts.",
            "methods_and_lab_skills": [
                {"skill": "qPCR & RT-PCR", "description": "Quantification of relative gene expression and transcript levels."},
                {"skill": "Western Blotting", "description": "Validation of target protein expression and phosphorylation states."},
                {"skill": "Flow Cytometry", "description": "High-throughput single-cell sorting and phenotypic profiling."}
            ],
            "critical_takeaways": {
                "importance": "Provides direct experimental validation for targeted pathway manipulation in living systems.",
                "next_steps": "Requires replication in in vivo preclinical cohorts to verify target specificity and safety.",
                "further_reading": ["Base editing methodologies", "Cellular senescence models", "Translational target delivery"]
            }
        }

    prompt = f"""You are creating an in-depth student study breakdown of this biomedical paper:
Title: {clean_title}
Journal: {clean_text(article['journal'])} ({clean_text(article['year'])})
Abstract: {clean_abstract}

Generate valid JSON adhering strictly to these 4 sections:
1. "context": A clear summary of the overarching biomedical problem or unresolved clinical challenge this paper addresses. Strip any raw HTML/XML tags.
2. "abstract_summary": Write an original, 7-to-8 sentence paraphrased summary of the provided abstract in clear, student-friendly language. DO NOT return or copy-paste the verbatim abstract text. Explain the core hypothesis, methodology, primary quantitative finding, and overall conclusion in accessible language for students. Count your sentences and verify that you produce exactly 7 or 8 sentences.
3. "methods_and_lab_skills": An array of 3 to 5 specific laboratory techniques or assays featured or relevant to this paper (e.g., qPCR, Western blot, CRISPR-Cas9, Flow Cytometry, ELISA, Gel Electrophoresis, RNA-seq, Immunohistochemistry). Each item must have "skill" and "description" (a 1-sentence note on why it is used).
4. "critical_takeaways": An object containing:
   - "importance": Exactly two sentences analyzing why this research matters right now.
   - "next_steps": Exactly two sentences discussing what experiments researchers must perform next.
   - "further_reading": Array of 3 to 4 related topics, techniques, or papers for student exploration.

Output ONLY valid JSON matching this schema:
{{
  "context": "string",
  "abstract_summary": "Original 7 to 8 sentence paraphrased summary without verbatim copying.",
  "methods_and_lab_skills": [
    {{"skill": "string", "description": "string"}}
  ],
  "critical_takeaways": {{
    "importance": "string",
    "next_steps": "string",
    "further_reading": ["Topic 1", "Topic 2", "Topic 3"]
  }}
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
        data = json.loads(response.text)
        data["context"] = clean_text(data.get("context", ""))
        data["abstract_summary"] = clean_text(data.get("abstract_summary", ""))
        for s in data.get("methods_and_lab_skills", []):
            s["skill"] = clean_text(s.get("skill", ""))
            s["description"] = clean_text(s.get("description", ""))
        crit = data.get("critical_takeaways", {})
        crit["importance"] = clean_text(crit.get("importance", ""))
        crit["next_steps"] = clean_text(crit.get("next_steps", ""))
        crit["further_reading"] = [clean_text(r) for r in crit.get("further_reading", [])]
        return data
    except Exception:
        return {
            "context": f"This study investigates clinical and molecular mechanisms reported in {clean_text(article['journal'])} ({clean_text(article['year'])}).",
            "abstract_summary": "This study analyzes biological mechanisms observed in laboratory models to identify cellular targets. Researchers utilized standard molecular assays to isolate changes across distinct cohort groups. The observed findings demonstrate measurable improvements in phenotypic regulation. The authors highlight specific pathways that direct biological response under experimental stress. These results provide an actionable foundation for creating next-generation therapeutic candidates. Replication in wider physiological conditions will remain essential for clinical translation. The study represents a notable step forward in bridging molecular targets to disease progression.",
            "methods_and_lab_skills": [
                {"skill": "qPCR / RNA Quantification", "description": "Determines transcriptional changes across experimental conditions."},
                {"skill": "Enzyme-Linked Immunosorbent Assay (ELISA)", "description": "Quantifies extracellular cytokine or protein secretion."},
                {"skill": "Statistical Cohort Validation", "description": "Ensures observed metric variances meet statistical significance thresholds."}
            ],
            "critical_takeaways": {
                "importance": "Expands fundamental understanding of physiological targets in disease pathophysiology.",
                "next_steps": "Expansion into diversified demographic and physiological models is essential.",
                "further_reading": ["Targeted cellular assays", "Pharmacokinetic profiling", "Precision medicine delivery"]
            }
        }


# -----------------------------------------------------------------------------
# Supabase Operations & Reliable Bookmarking Fixes
# -----------------------------------------------------------------------------
def load_user_profile(sb: Client, user_id: str, email: str):
    try:
        res = sb.table("profiles").select("*").eq("id", user_id).execute()
        if res.data:
            data = res.data[0]
            st.session_state.user_display_name = clean_text(data.get("display_name")) or email.split("@")[0].capitalize()
            saved_interests = data.get("interests", [])
            valid_interests = [i for i in saved_interests if i in ALL_TOPICS_FLAT]
            if valid_interests:
                st.session_state.user_interests = valid_interests
        else:
            fallback = email.split("@")[0].capitalize()
            st.session_state.user_display_name = fallback
            sb.table("profiles").insert({
                "id": user_id,
                "email": email,
                "display_name": fallback,
                "interests": ["CRISPR", "AI in Medicine"],
            }).execute()
    except Exception:
        st.session_state.user_display_name = email.split("@")[0].capitalize() if email else "Scholar"


def sync_library_state(sb: Optional[Client], user_id: Optional[str]):
    """Fetches user's current bookmarked and read articles into session state."""
    if sb and user_id:
        try:
            res = sb.table("user_library").select("*").eq("user_id", user_id).execute()
            records = res.data or []
            for r in records:
                pmid = str(r["pmid"])
                b_status = r.get("is_bookmarked") is True or str(r.get("is_bookmarked")).lower() == "true"
                h_status = r.get("is_read") is True or str(r.get("is_read")).lower() == "true"
                item = {
                    "pmid": pmid,
                    "title": clean_text(r.get("title") or "Untitled Paper"),
                    "journal": clean_text(r.get("journal") or "Biomedical Source"),
                    "year": clean_text(str(r.get("year") or "2024")),
                    "is_bookmarked": b_status,
                    "is_read": h_status,
                }
                st.session_state.local_saved_items[pmid] = item
                if b_status:
                    st.session_state.local_bookmarks.add(pmid)
        except Exception:
            pass


def toggle_bookmark(sb: Optional[Client], user_id: Optional[str], article_dict: Dict, current_status: bool):
    """Reliably persists bookmarking in Supabase AND in memory without overwriting reading status."""
    if not user_id:
        st.toast("Please sign in to save articles to your library.", icon="🔒")
        return current_status

    new_status = not current_status
    pmid_str = str(article_dict["pmid"])
    title_str = clean_text(article_dict.get("title") or article_dict.get("headline") or "Untitled Paper")
    journal_str = clean_text(article_dict.get("journal") or "Biomedical Source")
    year_str = clean_text(str(article_dict.get("year") or "2024"))

    existing = st.session_state.local_saved_items.get(pmid_str, {})
    is_read_val = existing.get("is_read", False)

    item = {
        "pmid": pmid_str,
        "title": title_str,
        "journal": journal_str,
        "year": year_str,
        "is_bookmarked": new_status,
        "is_read": is_read_val,
    }
    st.session_state.local_saved_items[pmid_str] = item

    if new_status:
        st.session_state.local_bookmarks.add(pmid_str)
        st.toast("Saved to your Library!", icon="🔖")
    else:
        st.session_state.local_bookmarks.discard(pmid_str)
        st.toast("Removed from Library.", icon="🗑️")

    # Persist to Supabase
    if sb:
        try:
            row_payload = {
                "user_id": user_id,
                "pmid": pmid_str,
                "title": title_str,
                "journal": journal_str,
                "year": year_str,
                "is_bookmarked": new_status,
            }
            if is_read_val:
                row_payload["is_read"] = True
            sb.table("user_library").upsert(row_payload, on_conflict="user_id,pmid").execute()
        except Exception as e:
            st.error(f"Failed to sync bookmark to cloud: {e}")

    st.rerun()


def mark_article_read(sb: Optional[Client], user_id: Optional[str], article: Dict):
    """Registers paper in reading history without overwriting existing bookmark status."""
    pmid_str = str(article["pmid"])
    is_b = pmid_str in st.session_state.local_bookmarks
    existing = st.session_state.local_saved_items.get(pmid_str, {})
    b_val = is_b or existing.get("is_bookmarked", False)

    item = {
        "pmid": pmid_str,
        "title": clean_text(article["title"]),
        "journal": clean_text(article["journal"]),
        "year": clean_text(str(article["year"])),
        "is_bookmarked": b_val,
        "is_read": True,
    }
    st.session_state.local_saved_items[pmid_str] = item

    if not (sb and user_id):
        return
    try:
        row_payload = {
            "user_id": user_id,
            "pmid": pmid_str,
            "title": clean_text(article["title"]),
            "journal": clean_text(article["journal"]),
            "year": clean_text(str(article["year"])),
            "is_read": True,
        }
        if b_val:
            row_payload["is_bookmarked"] = True
        sb.table("user_library").upsert(row_payload, on_conflict="user_id,pmid").execute()
    except Exception:
        pass


def get_user_library(sb: Optional[Client], user_id: Optional[str]):
    """Pulls library records from Supabase without ordering errors."""
    bookmarks = []
    history = []

    if sb and user_id:
        try:
            # Query without .order("last_accessed", desc=True) to prevent column failure
            res = sb.table("user_library").select("*").eq("user_id", user_id).execute()
            records = res.data or []
            for r in records:
                pmid = str(r["pmid"])
                b_status = r.get("is_bookmarked") is True or str(r.get("is_bookmarked")).lower() == "true"
                h_status = r.get("is_read") is True or str(r.get("is_read")).lower() == "true"
                item = {
                    "pmid": pmid,
                    "title": clean_text(r.get("title") or "Untitled Paper"),
                    "journal": clean_text(r.get("journal") or "Biomedical Source"),
                    "year": clean_text(str(r.get("year") or "")),
                    "is_bookmarked": b_status,
                    "is_read": h_status,
                }
                if b_status:
                    bookmarks.append(item)
                    st.session_state.local_bookmarks.add(pmid)
                if h_status:
                    history.append(item)
                st.session_state.local_saved_items[pmid] = item

            return {"bookmarks": bookmarks, "history": history}
        except Exception:
            pass

    # Seamless fallback to session cache
    bookmarks = [v for v in st.session_state.local_saved_items.values() if v.get("is_bookmarked")]
    history = [v for v in st.session_state.local_saved_items.values() if v.get("is_read")]
    return {"bookmarks": bookmarks, "history": history}


# -----------------------------------------------------------------------------
# SIDEBAR (Visible ONLY When User is Logged In)
# -----------------------------------------------------------------------------
supabase_client = get_supabase_client()
gemini_client = get_gemini_client()

if st.session_state.user:
    with st.sidebar:
        # Monogram Logo (Clean A.)
        st.markdown(
            '<div style="font-family: \'Playfair Display\', serif; font-size: 1.6rem; color: #D4AF37; font-style: italic; font-weight: 700; margin-bottom: 8px;">'
            'A.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption("Biomedical Research Digest for Students")
        st.write("")

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

        # Categorized Topic Filters
        st.markdown("#### 🧬 Research Interests")
        valid_defaults = [i for i in st.session_state.user_interests if i in ALL_TOPICS_FLAT]
        selected_topics = st.multiselect(
            "Curate your feed topics:",
            options=ALL_TOPICS_FLAT,
            default=valid_defaults,
            help="Select topics loaded dynamically from the research taxonomy.",
        )
        if st.button("Update Feed", use_container_width=True, type="primary"):
            st.session_state.user_interests = selected_topics
            if supabase_client and st.session_state.user:
                supabase_client.table("profiles").upsert({
                    "id": st.session_state.user.id,
                    "interests": selected_topics,
                }).execute()
            st.session_state.gemini_fyp_cache.clear()
            st.toast("Feed preferences updated!", icon="🌿")
            st.session_state.active_view = "fyp"
            st.rerun()

        st.divider()

        # User Profile Display
        st.markdown("#### 👤 Account")
        u_email = st.session_state.user.email or ""
        u_display = st.session_state.user_display_name or u_email.split("@")[0].capitalize() or "Scholar"
        initials = u_display[0].upper()

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:0.65rem; padding:0.65rem 0.8rem; background:rgba(20, 30, 24, 0.7); border:1px solid #4a3f35; border-radius:8px; margin-bottom:0.5rem;">
                <div style="width:34px; height:34px; border-radius:50%; background:#2C3E2D; color:#E5C775; border:1px solid #705D4A; display:flex; align-items:center; justify-content:center; font-family:'Playfair Display', serif; font-weight:700; font-size:0.9rem;">{clean_text(initials)}</div>
                <div style="overflow:hidden;">
                    <div style="font-weight:700; font-size:0.9rem; color:#F5EFEB; font-family:'Playfair Display', serif; text-overflow:ellipsis; white-space:nowrap;">{clean_text(u_display)}</div>
                    <div style="font-size:0.75rem; color:#A89C8A; text-overflow:ellipsis; white-space:nowrap;">{clean_text(u_email)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")
        st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
        if st.button("Log Out", key="sidebar_logout_btn", use_container_width=True):
            if supabase_client:
                supabase_client.auth.sign_out()
            st.session_state.user = None
            st.session_state.auth_token = None
            st.session_state.user_display_name = ""
            st.session_state.local_bookmarks = set()
            st.session_state.local_saved_items = {}
            st.session_state.auth_page = "landing"
            st.session_state.active_view = "fyp"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# VIEW 1A: Dedicated Clean Authentication View
# =============================================================================
if not st.session_state.user and st.session_state.auth_page == "auth":
    st.write("")
    col_back, _ = st.columns([2, 8])
    with col_back:
        if st.button("← Back to Overview", type="secondary"):
            st.session_state.auth_page = "landing"
            st.rerun()

    auth_sp1, auth_main, auth_sp2 = st.columns([3, 4, 3])
    with auth_main:
        with st.container(border=True):
            if st.session_state.auth_mode == "signin":
                st.markdown("<h3 style='font-family: Playfair Display, serif; margin-bottom: 0.2rem; color: #F5EFEB;'>Sign In</h3>", unsafe_allow_html=True)
                st.caption("Access your saved library and personalized feed.")
                st.write("")

                si_email = st.text_input("Email", placeholder="name@domain.edu")
                si_pwd = st.text_input("Password", type="password", placeholder="••••••••")

                st.write("")
                if st.button("Sign In to Abstracted", use_container_width=True, type="primary"):
                    if supabase_client:
                        try:
                            res = supabase_client.auth.sign_in_with_password({"email": si_email, "password": si_pwd})
                            st.session_state.user = res.user
                            if res.session:
                                st.session_state.auth_token = res.session.access_token
                                supabase_client.postgrest.auth(res.session.access_token)

                            load_user_profile(supabase_client, res.user.id, res.user.email or "")
                            sync_library_state(supabase_client, res.user.id)
                            st.session_state.auth_page = "landing"
                            st.session_state.active_view = "fyp"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Sign in failed: {e}")
                    else:
                        st.info("Supabase client is not configured.")

                st.write("")
                if st.button("Don't have an account? Create one", use_container_width=True, type="secondary"):
                    st.session_state.auth_mode = "signup"
                    st.rerun()

            else:
                st.markdown("<h3 style='font-family: Playfair Display, serif; margin-bottom: 0.2rem; color: #F5EFEB;'>Create Account</h3>", unsafe_allow_html=True)
                st.caption("Join Abstracted to save articles and customize topics.")
                st.write("")

                su_fullname = st.text_input("Full Name", placeholder="Alex Morgan")
                su_email = st.text_input("Email", placeholder="alex@university.edu")
                su_pwd = st.text_input("Password", type="password", placeholder="Choose a secure password")

                st.write("")
                if st.button("Register & Begin Reading", use_container_width=True, type="primary"):
                    if supabase_client:
                        try:
                            res = supabase_client.auth.sign_up({"email": su_email, "password": su_pwd})
                            if res.user:
                                clean_name = clean_text(su_fullname.strip()) or su_email.split("@")[0].capitalize()
                                if res.session:
                                    st.session_state.auth_token = res.session.access_token
                                    supabase_client.postgrest.auth(res.session.access_token)

                                supabase_client.table("profiles").upsert({
                                    "id": res.user.id,
                                    "email": su_email,
                                    "display_name": clean_name,
                                    "interests": ["CRISPR", "AI in Medicine"],
                                }).execute()
                                st.success("Account created successfully! Please sign in.")
                                st.session_state.auth_mode = "signin"
                                st.rerun()
                        except Exception as e:
                            st.error(f"Sign up error: {e}")
                    else:
                        st.info("Supabase client is not configured.")

                st.write("")
                if st.button("Already have an account? Sign in", use_container_width=True, type="secondary"):
                    st.session_state.auth_mode = "signin"
                    st.rerun()


# =============================================================================
# VIEW 1B: Warm Dark Academia Landing Page
# =============================================================================
elif not st.session_state.user and st.session_state.auth_page == "landing" and st.session_state.active_view != "reader":
    nav_left, nav_right_1, nav_right_2 = st.columns([7, 1.5, 1.5], vertical_alignment="center")
    with nav_left:
        st.markdown(
            '<div style="font-family: \'Playfair Display\', serif; font-size: 1.6rem; color: #D4AF37; font-style: italic; font-weight: 700; cursor: default;">'
            'A.'
            '</div>',
            unsafe_allow_html=True,
        )
    with nav_right_1:
        if st.button("Sign In", use_container_width=True, type="secondary"):
            st.session_state.auth_page = "auth"
            st.session_state.auth_mode = "signin"
            st.rerun()
    with nav_right_2:
        if st.button("Create Account", use_container_width=True, type="primary"):
            st.session_state.auth_page = "auth"
            st.session_state.auth_mode = "signup"
            st.rerun()

    # Hero Center Title
    st.markdown(
        """
        <div class="landing-hero">
            <div class="hero-title-serif">ABSTRACTED</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Subtle Prose Personal Memo ("Hi there!" Greeting & Quiet Aesthetic)
    st.markdown(
        """
        <div style="max-width: 680px; margin: 4.5rem auto 3rem auto; padding: 0 1rem; text-align: left;">
            <div style="font-family: 'Lora', serif; font-style: italic; font-size: 1.35rem; color: #C5BBAA; margin-bottom: 0.85rem;">
                Hi there!
            </div>
            <div style="font-family: 'Lora', serif; font-size: 0.9rem; line-height: 1.85; color: #C1B49A;">
                This is a tool built by a student for fellow curious students. PubMed contains a vast treasure trove of groundbreaking research in the life sciences, biomedical sciences, and more. However to many high school and undergraduate students, this resource feels guarded by intimidating jargon and complex methodologies. I believe that students should not have to choose between staying forever consigned to surface-level pop science reports or getting lost in the dense terminology of top-tier papers. The aim of Abstracted is to be a bridge between the labs working at the cutting edge of their fields and the students just beginning to explore their paths. Enjoy!
                <br/><br/>
                <span style="font-family: 'Playfair Display', serif; font-style: italic; color: #D4AF37; font-size: 0.95rem;">— Michelle</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# VIEW 2: Logged-In Feed ("Today's Feed")
# =============================================================================
elif st.session_state.active_view == "fyp":
    raw_user = st.session_state.user_display_name or (st.session_state.user.email.split("@")[0].capitalize() if st.session_state.user and st.session_state.user.email else "Scholar")
    greeting_header = f"{st.session_state.greeting_phrase}, {clean_text(raw_user)}!"

    head_left, head_right = st.columns([1.6, 1.2], vertical_alignment="center")
    with head_left:
        st.markdown(f'<h1 style="font-family: Playfair Display, serif; font-size: 2.5rem; font-weight: 600; margin: 0; color: #F5EFEB;">{greeting_header}</h1>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 1.05rem; font-style: italic; color: #D4AF37; margin: 0.15rem 0 0 0;">Top picks for you</p>', unsafe_allow_html=True)

    with head_right:
        s_btn1, s_btn2 = st.columns(2)
        with s_btn1:
            if st.button("Search with PMID", use_container_width=True, type="primary" if st.session_state.search_mode == "pmid" else "secondary"):
                st.session_state.search_mode = "pmid" if st.session_state.search_mode != "pmid" else None
                st.rerun()
        with s_btn2:
            if st.button("Search by Keywords", use_container_width=True, type="primary" if st.session_state.search_mode == "keywords" else "secondary"):
                st.session_state.search_mode = "keywords" if st.session_state.search_mode != "keywords" else None
                st.rerun()

    # Search Expanders
    if st.session_state.search_mode == "pmid":
        p_col1, p_col2 = st.columns([4, 1])
        with p_col1:
            search_pmid_input = st.text_input("Enter PubMed ID", placeholder="Enter PMID (e.g. 38157930)...", label_visibility="collapsed")
        with p_col2:
            if st.button("Open Paper", use_container_width=True, type="primary") and search_pmid_input.strip():
                st.session_state.reader_pmid = search_pmid_input.strip()
                st.session_state.active_view = "reader"
                st.rerun()

    elif st.session_state.search_mode == "keywords":
        k_col1, k_col2, k_col3 = st.columns([2, 3, 1])
        with k_col1:
            cat_choice = st.selectbox("Category", list(TOPICS_TAXONOMY.keys()), label_visibility="collapsed")
        with k_col2:
            topic_choice = st.selectbox("Keyword Topic", TOPICS_TAXONOMY[cat_choice], label_visibility="collapsed")
        with k_col3:
            if st.button("Explore", use_container_width=True, type="primary"):
                st.session_state.user_interests = [topic_choice]
                st.session_state.gemini_fyp_cache.clear()
                st.session_state.search_mode = None
                st.rerun()

    st.write("")

    cache_key = "-".join(sorted(st.session_state.user_interests))
    if cache_key not in st.session_state.gemini_fyp_cache:
        with st.status("Gathering scholarly volumes...", expanded=True) as status:
            st.write("Accessing NCBI PubMed for recent high-yield literature...")
            pmids = search_pubmed_by_interests(st.session_state.user_interests, max_results=8)

            st.write("Extracting methodologies & computing reading times...")
            raw_papers = []
            for pid in pmids:
                try:
                    raw_papers.append(fetch_pubmed_article(pid))
                except Exception:
                    continue

            st.write("Formulating student-friendly takeaways...")
            feed_items = batch_summarize_feed(raw_papers, gemini_client)
            st.session_state.gemini_fyp_cache[cache_key] = feed_items
            status.update(label="Feed ready!", state="complete", expanded=False)

    articles_feed = st.session_state.gemini_fyp_cache.get(cache_key, [])
    user_id = st.session_state.user.id if st.session_state.user else None

    if not st.session_state.local_bookmarks and user_id:
        sync_library_state(supabase_client, user_id)

    # Render Feed Cards using Native Streamlit Containers with Delicate Library Badges
    for item in articles_feed:
        pmid_str = str(item["pmid"])
        is_bookmarked = pmid_str in st.session_state.local_bookmarks

        impact_chip = ' <span class="lib-badge lib-badge-gold">🏛️ High-Impact</span>' if item.get("is_high_impact") else ""
        badges_line = (
            f'<div style="margin-bottom: 0.5rem;">'
            f'<span class="lib-badge">🏛️ {item["journal"]} ({item["year"]})</span>'
            f'<span class="lib-badge">PMID: {pmid_str}</span>'
            f'<span class="lib-badge">⏱️ {item.get("read_time_min", 2)} min read</span>'
            f'<span class="lib-badge">{item["difficulty"]}</span>'
            f'{impact_chip}'
            f'</div>'
        )

        concepts_badges = " ".join([f'<span class="lib-badge">{clean_text(c)}</span>' for c in item.get("concepts", [])])

        with st.container(border=True):
            st.markdown(badges_line, unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin-top:0.2rem; margin-bottom:0.5rem;'>{item['headline']}</h3>", unsafe_allow_html=True)
            st.markdown(f"**Summary:** {item['preview_sentences']}")
            st.markdown(f"💡 **Why It Matters:** {item['why_it_matters']}")

            if concepts_badges:
                st.markdown(f"<div style='margin-top:0.5rem;'><strong style='font-size:0.85rem; color:#A89C8A;'>Key Concepts:</strong> {concepts_badges}</div>", unsafe_allow_html=True)

            st.write("")
            btn_c1, btn_c2, _ = st.columns([1.5, 1.5, 7])
            with btn_c1:
                if st.button("Read Digest 📖", key=f"digest_{pmid_str}", use_container_width=True, type="primary"):
                    st.session_state.reader_pmid = pmid_str
                    st.session_state.active_view = "reader"
                    st.rerun()

            with btn_c2:
                bm_label = "★ Saved" if is_bookmarked else "☆ Bookmark"
                if st.button(bm_label, key=f"feed_bm_{pmid_str}", use_container_width=True):
                    toggle_bookmark(supabase_client, user_id, item, is_bookmarked)

        st.write("")


# =============================================================================
# VIEW 3: Dedicated Student Library
# =============================================================================
elif st.session_state.active_view == "library":
    u_display = clean_text(st.session_state.user_display_name or "Student")
    st.markdown(f'<h1 style="font-family: Playfair Display, serif; font-size: 2.5rem; font-weight: 600; margin: 0; color: #F5EFEB;">{u_display}\'s Library</h1>', unsafe_allow_html=True)
    st.caption("Personal research vault & studied publications.")

    user_id = st.session_state.user.id if st.session_state.user else None
    lib_data = get_user_library(supabase_client, user_id)

    lib_filter = st.text_input("Filter saved library by title or PMID...", placeholder="Type to filter...").strip().lower()

    tab_saved, tab_history = st.tabs(["Saved Bookmarks", "Reading History"])

    with tab_saved:
        bookmarks = lib_data["bookmarks"]
        if lib_filter:
            bookmarks = [
                b for b in bookmarks
                if lib_filter in clean_text(b.get("title", "")).lower() or lib_filter in str(b.get("pmid", ""))
            ]

        if bookmarks:
            for b in bookmarks:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([6, 1.2, 1])
                    with c1:
                        st.markdown(f"<h4 style='margin-bottom:0.3rem;'>{clean_text(b['title'])}</h4>", unsafe_allow_html=True)
                        st.markdown(
                            f'<span class="lib-badge">🏛️ {clean_text(b.get("journal", "Journal"))} ({clean_text(str(b.get("year", "")))})</span>'
                            f'<span class="lib-badge">PMID: {clean_text(str(b["pmid"]))}</span>',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        if st.button("Read", key=f"lib_read_{b['pmid']}", use_container_width=True, type="primary"):
                            st.session_state.reader_pmid = str(b["pmid"])
                            st.session_state.active_view = "reader"
                            st.rerun()
                    with c3:
                        if st.button("Remove", key=f"lib_del_{b['pmid']}", use_container_width=True):
                            toggle_bookmark(supabase_client, user_id, b, True)
                st.write("")
        else:
            st.info("No bookmarked articles found in your library yet. Explore the feed and bookmark studies to read later!")

    with tab_history:
        history = lib_data["history"]
        if lib_filter:
            history = [
                h for h in history
                if lib_filter in clean_text(h.get("title", "")).lower() or lib_filter in str(h.get("pmid", ""))
            ]

        if history:
            for h in history:
                with st.container(border=True):
                    c1, c2 = st.columns([6, 1.2])
                    with c1:
                        st.markdown(f"<h4 style='margin-bottom:0.3rem;'>{clean_text(h['title'])}</h4>", unsafe_allow_html=True)
                        st.markdown(f'<span class="lib-badge">PMID: {clean_text(str(h["pmid"]))}</span> <span style="font-style:italic; font-size:0.85rem; color:#A89C8A;">Studied recently</span>', unsafe_allow_html=True)
                    with c2:
                        if st.button("Revisit", key=f"hist_revisit_{h['pmid']}", use_container_width=True, type="secondary"):
                            st.session_state.reader_pmid = str(h["pmid"])
                            st.session_state.active_view = "reader"
                            st.rerun()
                st.write("")
        else:
            st.caption("No reading history recorded yet.")


# =============================================================================
# VIEW 4: Article Digest Reader
# =============================================================================
elif st.session_state.active_view == "reader":
    target_pmid = st.session_state.reader_pmid or "38157930"

    try:
        with st.spinner("Deciphering text & formulating digest..."):
            paper = fetch_pubmed_article(target_pmid)
            user_id = st.session_state.user.id if st.session_state.user else None
            mark_article_read(supabase_client, user_id, paper)
            digest = generate_student_digest(paper, gemini_client)

        if st.button("← Back to Feed", type="secondary"):
            st.session_state.active_view = "fyp"
            st.rerun()

        st.markdown(f"<h2 style='font-family: Playfair Display, serif; font-size: 2.2rem; color:#F5EFEB;'>{clean_text(paper['title'])}</h2>", unsafe_allow_html=True)
        authors_display = ", ".join(paper["authors"][:4]) + (" et al." if len(paper["authors"]) > 4 else "")
        impact_chip = ' <span class="lib-badge lib-badge-gold">🏛️ High-Impact Journal</span>' if paper.get("is_high_impact") else ""

        badges_header = (
            f'<div style="margin-bottom: 0.6rem;">'
            f'<span class="lib-badge">🏛️ {paper["journal"]} ({paper["year"]})</span>'
            f'<span class="lib-badge">PMID: {paper["pmid"]}</span>'
            f'<span class="lib-badge">⏱️ {paper.get("read_time_min", 2)} min read</span>'
            f'{impact_chip}'
            f'</div>'
        )
        st.markdown(badges_header, unsafe_allow_html=True)
        st.markdown(f"✍️ **Authors:** *{authors_display}*")

        col_gdoc, col_pubmed, _ = st.columns([2, 2, 6])
        with col_gdoc:
            encoded_title = urllib.parse.quote(paper["title"])
            st.link_button("↗ Export to Google Doc", f"https://docs.google.com/document/create?title={encoded_title}", use_container_width=True)
        with col_pubmed:
            st.link_button("View on PubMed ↗", f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/", use_container_width=True)

        st.write("")

        # 1. Context
        with st.container(border=True):
            st.markdown("<h4 style='color:#D4AF37;'>1. CONTEXT & CLINICAL PROBLEM</h4>", unsafe_allow_html=True)
            st.markdown(clean_text(digest.get("context", "")))

        # 2. Abstract Summary
        with st.container(border=True):
            st.markdown("<h4 style='color:#D4AF37;'>2. ABSTRACT SUMMARY</h4>", unsafe_allow_html=True)
            st.markdown(clean_text(digest.get("abstract_summary", "")))

        # 3. Methods & Lab Skills to Know
        with st.container(border=True):
            st.markdown("<h4 style='color:#D4AF37;'>3. METHODS AND LAB SKILLS TO KNOW</h4>", unsafe_allow_html=True)
            skills = digest.get("methods_and_lab_skills", [])
            for s in skills:
                st.markdown(f"- **{clean_text(s.get('skill', ''))}:** {clean_text(s.get('description', ''))}")

        # 4. Critical Takeaways
        with st.container(border=True):
            st.markdown("<h4 style='color:#D4AF37;'>4. CRITICAL TAKEAWAYS & NEXT STEPS</h4>", unsafe_allow_html=True)
            crit = digest.get("critical_takeaways", {})
            st.markdown(f"**Research Importance:** {clean_text(crit.get('importance', ''))}")
            st.markdown(f"**Next Experiments Required:** {clean_text(crit.get('next_steps', ''))}")
            st.markdown("**Suggested Topics for Further Reading:**")
            for topic in crit.get("further_reading", []):
                st.markdown(f"- *{clean_text(topic)}*")

        # 5. Unedited Abstract Expander
        with st.expander("View original abstract"):
            st.markdown(clean_text(paper["abstract"]))

    except Exception as exc:
        st.error(f"Error loading study: {exc}")
        if st.button("Return to Feed", type="primary"):
            st.session_state.active_view = "fyp"
            st.rerun()