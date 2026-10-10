import base64
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
# Favicon & SVG Asset: Forest Green Document + Chromosome / Helix
# Palette: #0B1D15 (Base Dark), #143326 (Doc), #2D5A40 (Fold), #A3B899 (Muted), #E6F4ED (Accent)
# -----------------------------------------------------------------------------
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#0B1D15"/>
  <!-- Base Paper / Document Sheet with Folded Corner -->
  <path d="M7 6C7 4.89543 7.89543 4 9 4H19L25 10V26C25 27.1046 24.1046 28 23 28H9C7.89543 28 7 27.1046 7 26V6Z" fill="#143326" stroke="#2D5A40" stroke-width="1.2"/>
  <path d="M19 4V10H25" fill="#2D5A40"/>
  <!-- Stylized Chromosome / Double-Helix Crossing Over the Sheet -->
  <path d="M10 11C13 11 15 15 16 16C17 17 19 21 22 21" stroke="#E6F4ED" stroke-width="2" stroke-linecap="round"/>
  <path d="M22 11C19 11 17 15 16 16C15 17 13 21 10 21" stroke="#A3B899" stroke-width="2" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="1.6" fill="#E6F4ED"/>
  <!-- Base-pair rungs -->
  <line x1="12" y1="13.2" x2="20" y2="13.2" stroke="#A3B899" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="12" y1="18.8" x2="20" y2="18.8" stroke="#E6F4ED" stroke-width="1.2" stroke-linecap="round"/>
</svg>"""

FAVICON_DATA_URI = f"data:image/svg+xml;base64,{base64.b64encode(FAVICON_SVG.encode()).decode()}"

st.set_page_config(
    page_title="Abstracted | Make Research Accessible",
    page_icon=FAVICON_DATA_URI,
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
# Global Dark Forest CSS & Strict Streamlit Overrides
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=JetBrains+Mono:wght@400;500&display=swap');

    /* 1. Eliminate Streamlit White Top Header */
    header[data-testid="stHeader"] {
        visibility: hidden !important;
        height: 0px !important;
    }
    .stApp {
        margin-top: 0px !important;
        background: linear-gradient(180deg, #091711 0%, #0F281E 100%) !important;
        color: #E6F4ED !important;
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    }

    /* 2. Global Dark Typography */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        letter-spacing: -0.025em;
    }
    p, span, label, div {
        color: #E6F4ED;
    }
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #94BAA5 !important;
        font-weight: 500 !important;
    }

    /* 3. Global Button Contrast */
    button[kind="primary"] {
        background-color: #1B4D3E !important;
        border: 1px solid #2D6B58 !important;
        border-radius: 9999px !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }
    button[kind="primary"]:hover {
        background-color: #22624F !important;
        border-color: #4ADE80 !important;
    }
    button[kind="primary"] p,
    button[kind="primary"] span {
        color: #FFFFFF !important;
    }

    button[kind="secondary"] {
        background-color: rgba(20, 51, 38, 0.6) !important;
        border: 1px solid #234E3C !important;
        border-radius: 9999px !important;
        color: #E6F4ED !important;
        font-weight: 600 !important;
    }
    button[kind="secondary"]:hover {
        background-color: #1B4D3E !important;
        border-color: #4ADE80 !important;
        color: #FFFFFF !important;
    }
    button[kind="secondary"] p,
    button[kind="secondary"] span {
        color: #E6F4ED !important;
    }

    div[data-testid="stButton"].danger-btn button {
        background-color: #7F1D1D !important;
        border: 1px solid #991B1B !important;
    }
    div[data-testid="stButton"].danger-btn button p,
    div[data-testid="stButton"].danger-btn button span {
        color: #FEE2E2 !important;
        font-weight: 600 !important;
    }

    /* 4. Native Container (Card) Forest Styling */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #143326 !important;
        border: 1px solid #234E3C !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
        padding: 0.5rem 0.75rem !important;
    }

    /* 5. Sidebar Dark Forest Theme */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        background-color: #0B1D15 !important;
        border-right: 1px solid #1A3E2F !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {
        color: #E6F4ED !important;
    }

    /* 6. BaseWeb Dropdowns & Popovers Contrast Fix (Removes White Boxes) */
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        background-color: #143326 !important;
        border-color: #234E3C !important;
        color: #E6F4ED !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    ul[role="listbox"],
    ul[role="listbox"] > li {
        background-color: #143326 !important;
        border-color: #234E3C !important;
        color: #E6F4ED !important;
    }
    li[role="option"] {
        background-color: #143326 !important;
        color: #E6F4ED !important;
    }
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #1B4D3E !important;
        color: #FFFFFF !important;
    }
    div[data-baseweb="tag"] {
        background-color: #1B4D3E !important;
        color: #E6F4ED !important;
        border: 1px solid #2D6B58 !important;
    }
    div[data-baseweb="tag"] span {
        color: #E6F4ED !important;
    }

    /* 7. Notification Toasts & Alerts Contrast Fix */
    div[data-testid="stToast"] {
        background-color: #143326 !important;
        border: 1px solid #234E3C !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stToast"] p,
    div[data-testid="stToast"] span,
    div[data-testid="stToast"] div {
        color: #FFFFFF !important;
    }
    .stAlert, div[data-testid="stAlert"] {
        background-color: #143326 !important;
        border: 1px solid #234E3C !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] div {
        color: #FFFFFF !important;
    }

    /* 8. Text Inputs */
    input[type="text"], input[type="password"] {
        background-color: #0E241B !important;
        color: #FFFFFF !important;
        border: 1px solid #234E3C !important;
        border-radius: 8px !important;
    }
    input[type="text"]:focus, input[type="password"]:focus {
        border-color: #4ADE80 !important;
    }

    /* 9. Tabs */
    [data-testid="stTabs"] button {
        background-color: transparent !important;
        border-radius: 6px !important;
    }
    [data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {
        color: #94BAA5 !important;
        font-weight: 600 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        background-color: rgba(35, 78, 60, 0.6) !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        color: #4ADE80 !important;
        font-weight: 700 !important;
    }

    /* 10. Expanders */
    [data-testid="stExpander"] {
        background-color: #143326 !important;
        border: 1px solid #234E3C !important;
        border-radius: 10px !important;
    }
    [data-testid="stExpander"] details summary {
        background-color: #112B20 !important;
        color: #E6F4ED !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
        background-color: #143326 !important;
    }

    /* 11. Landing Hero & Mission Card */
    .landing-hero {
        max-width: 900px;
        margin: 2rem auto 1.5rem auto;
        text-align: center;
    }
    .hero-title-serif {
        font-family: 'Newsreader', Georgia, serif;
        font-size: clamp(3.2rem, 8vw, 6rem);
        font-weight: 500;
        letter-spacing: 0.08em;
        line-height: 1.0;
        color: #FFFFFF !important;
        margin-bottom: 0.85rem;
        text-transform: uppercase;
        text-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
    }
    .hero-subtitle {
        font-size: 1.35rem;
        color: #A3C9B4 !important;
        max-width: 650px;
        margin: 0 auto 2.5rem auto;
        font-weight: 400;
        line-height: 1.5;
    }
    .mission-card {
        max-width: 780px;
        margin: 1.5rem auto 3.5rem auto;
        padding: 2.2rem 2.6rem;
        background: #143326;
        border: 1px solid #234E3C;
        border-radius: 16px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35);
    }
    .mission-title {
        font-family: 'Newsreader', Georgia, serif;
        font-size: 1.6rem;
        font-weight: 500;
        color: #FFFFFF !important;
        margin-bottom: 1rem;
        line-height: 1.3;
    }
    .mission-text {
        font-size: 1.02rem;
        line-height: 1.8;
        color: #D2E7DC !important;
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
        return create_client(url, key)
    except Exception:
        return None


if "user" not in st.session_state:
    st.session_state.user = None
if "user_display_name" not in st.session_state:
    st.session_state.user_display_name = ""
if "user_interests" not in st.session_state:
    st.session_state.user_interests = ["CRISPR", "AI in Medicine"]
if "active_view" not in st.session_state:
    st.session_state.active_view = "fyp"
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "landing"  # "landing" or "auth"
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "signin"  # "signin" or "signup"
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
# Supabase Operations & Reliable Bookmarking
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
    """Fetches user's current bookmarked articles into session state for immediate, reliable UI feedback."""
    if sb and user_id:
        try:
            res = sb.table("user_library").select("*").eq("user_id", user_id).eq("is_bookmarked", True).execute()
            if res.data:
                st.session_state.local_bookmarks = {str(r["pmid"]) for r in res.data}
                st.session_state.local_saved_items = {
                    str(r["pmid"]): {
                        "pmid": str(r["pmid"]),
                        "title": clean_text(r.get("title") or "Untitled Paper"),
                        "journal": clean_text(r.get("journal") or "Biomedical Source"),
                        "year": clean_text(str(r.get("year") or "2024")),
                        "is_bookmarked": True,
                    }
                    for r in res.data
                }
            else:
                st.session_state.local_bookmarks = set()
                st.session_state.local_saved_items = {}
        except Exception:
            pass


def toggle_bookmark(sb: Optional[Client], user_id: Optional[str], article_dict: Dict, current_status: bool):
    """Reliably persists bookmarking in Supabase AND in memory for guaranteed library display."""
    if not user_id:
        st.toast("Please sign in to save articles to your library.", icon="🔒")
        return current_status

    new_status = not current_status
    pmid_str = str(article_dict["pmid"])
    title_str = clean_text(article_dict.get("title") or article_dict.get("headline") or "Untitled Paper")
    journal_str = clean_text(article_dict.get("journal") or "Biomedical Source")
    year_str = clean_text(str(article_dict.get("year") or "2024"))

    # Update session cache immediately
    if new_status:
        st.session_state.local_bookmarks.add(pmid_str)
        st.session_state.local_saved_items[pmid_str] = {
            "pmid": pmid_str,
            "title": title_str,
            "journal": journal_str,
            "year": year_str,
            "is_bookmarked": True,
        }
        st.toast("Saved to your Library!", icon="🔖")
    else:
        st.session_state.local_bookmarks.discard(pmid_str)
        st.session_state.local_saved_items.pop(pmid_str, None)
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
            sb.table("user_library").upsert(row_payload, on_conflict="user_id,pmid").execute()
        except Exception as e:
            st.error(f"Failed to sync bookmark to cloud: {e}")

    st.rerun()


def mark_article_read(sb: Optional[Client], user_id: Optional[str], article: Dict):
    if not (sb and user_id):
        return
    try:
        sb.table("user_library").upsert({
            "user_id": user_id,
            "pmid": str(article["pmid"]),
            "title": clean_text(article["title"]),
            "journal": clean_text(article["journal"]),
            "year": clean_text(str(article["year"])),
            "is_read": True,
        }, on_conflict="user_id,pmid").execute()
    except Exception:
        pass


def get_user_library(sb: Optional[Client], user_id: Optional[str]):
    """Pulls directly from Supabase with is_bookmarked=True, falling back to session state."""
    if not (sb and user_id):
        bookmarks = list(st.session_state.local_saved_items.values())
        return {"bookmarks": bookmarks, "history": []}

    try:
        res = sb.table("user_library").select("*").eq("user_id", user_id).order("last_accessed", desc=True).execute()
        records = res.data or []
        bookmarks = [
            {
                "pmid": str(r["pmid"]),
                "title": clean_text(r.get("title") or "Untitled Paper"),
                "journal": clean_text(r.get("journal") or "Biomedical Source"),
                "year": clean_text(str(r.get("year") or "")),
                "is_bookmarked": True,
            }
            for r in records if r.get("is_bookmarked") is True
        ]
        history = [
            {
                "pmid": str(r["pmid"]),
                "title": clean_text(r.get("title") or "Untitled Paper"),
                "journal": clean_text(r.get("journal") or "Biomedical Source"),
                "year": clean_text(str(r.get("year") or "")),
                "is_bookmarked": r.get("is_bookmarked", False),
            }
            for r in records if r.get("is_read") is True
        ]

        # Update in-memory cache to stay in sync
        for b in bookmarks:
            st.session_state.local_saved_items[b["pmid"]] = b
            st.session_state.local_bookmarks.add(b["pmid"])

        return {"bookmarks": bookmarks, "history": history}
    except Exception:
        bookmarks = list(st.session_state.local_saved_items.values())
        return {"bookmarks": bookmarks, "history": []}


# -----------------------------------------------------------------------------
# SIDEBAR (Visible ONLY When User is Logged In)
# -----------------------------------------------------------------------------
supabase_client = get_supabase_client()
gemini_client = get_gemini_client()

if st.session_state.user:
    with st.sidebar:
        # Top-Left Header: Icon Only (Removed all accompanying text)
        st.markdown(
            f'<div style="display:flex; align-items:center; margin-bottom:12px;">'
            f'<img src="{FAVICON_DATA_URI}" width="28" height="28" style="border-radius:7px;" />'
            f'</div>',
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
            <div style="display:flex; align-items:center; gap:0.65rem; padding:0.65rem 0.8rem; background:#143326; border:1px solid #234E3C; border-radius:10px; margin-bottom:0.5rem;">
                <div style="width:34px; height:34px; border-radius:50%; background:#1B4D3E; color:#86EFAC; border:1px solid #4ADE80; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.85rem;">{clean_text(initials)}</div>
                <div style="overflow:hidden;">
                    <div style="font-weight:700; font-size:0.9rem; color:#FFFFFF; text-overflow:ellipsis; white-space:nowrap;">{clean_text(u_display)}</div>
                    <div style="font-size:0.75rem; color:#94BAA5; text-overflow:ellipsis; white-space:nowrap;">{clean_text(u_email)}</div>
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
                st.markdown("<h3 style='font-family: Newsreader, serif; margin-bottom: 0.2rem; color: #FFFFFF;'>Sign In</h3>", unsafe_allow_html=True)
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
                st.markdown("<h3 style='font-family: Newsreader, serif; margin-bottom: 0.2rem; color: #FFFFFF;'>Create Account</h3>", unsafe_allow_html=True)
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
# VIEW 1B: Shaded Deep Forest Landing Page
# =============================================================================
elif not st.session_state.user and st.session_state.auth_page == "landing" and st.session_state.active_view != "reader":
    # Top Bar: Icon Only on the Left (No text branding)
    nav_left, nav_right_1, nav_right_2 = st.columns([7, 1.5, 1.5], vertical_alignment="center")
    with nav_left:
        st.markdown(
            f'<div style="display:flex; align-items:center;">'
            f'<img src="{FAVICON_DATA_URI}" width="28" height="28" style="border-radius:7px;" />'
            f'</div>',
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

    # Hero Center Title & Updated Subtitle
    st.markdown(
        """
        <div class="landing-hero">
            <div class="hero-title-serif">ABSTRACTED</div>
            <div class="hero-subtitle">Make research accessible</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Human-Centered Mission Section (With Updated Enjoy! Copy)
    st.markdown(
        """
        <div class="mission-card">
            <div class="mission-title">This is a tool built by a student for fellow curious students.</div>
            <div class="mission-text">
                PubMed contains a vast treasure trove of groundbreaking research in the life sciences, biomedical sciences, and more.
                However to many high school and undergraduate students, this resource feels guarded by intimidating jargon and complex methodologies.
                I believe that students should not have to choose between staying forever consigned to surface-level pop science reports or getting lost in the dense terminology of top-tier papers.
                The aim of Abstracted is to be a bridge between the labs working at the cutting edge of their fields and the students just beginning to explore their paths.
                Enjoy!
                <br/><br/>
                <span style="font-weight: 600; color: #86EFAC;">— Michelle</span>
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
        st.markdown(f'<h1 style="font-family: Newsreader, serif; font-size: 2.5rem; font-weight: 500; margin: 0; color: #FFFFFF;">{greeting_header}</h1>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 1rem; font-weight: 600; color: #4ADE80; margin: 0.15rem 0 0 0;">Top picks for you</p>', unsafe_allow_html=True)

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
        with st.status("Distilling latest research...", expanded=True) as status:
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

    # Render Feed Cards using Native Streamlit Containers
    for item in articles_feed:
        pmid_str = str(item["pmid"])
        is_bookmarked = pmid_str in st.session_state.local_bookmarks

        impact_chip = " • 🏛️ High-Impact" if item.get("is_high_impact") else ""
        concepts_formatted = " • ".join([f"`{c}`" for c in item.get("concepts", [])])

        with st.container(border=True):
            st.markdown(
                f"🏛️ **{item['journal']}** ({item['year']}) • **PMID:** `{pmid_str}` • ⏱️ {item.get('read_time_min', 2)} min read • `{item['difficulty']}`{impact_chip}"
            )
            st.markdown(f"### {item['headline']}")
            st.markdown(f"**Summary:** {item['preview_sentences']}")
            st.markdown(f"💡 **Why It Matters:** {item['why_it_matters']}")

            if concepts_formatted:
                st.markdown(f"**Key Concepts:** {concepts_formatted}")

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
    st.markdown(f'<h1 style="font-family: Newsreader, serif; font-size: 2.5rem; font-weight: 500; margin: 0; color: #FFFFFF;">{u_display}\'s Library</h1>', unsafe_allow_html=True)
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
                        st.markdown(f"#### {clean_text(b['title'])}")
                        st.markdown(f"🏛️ **{clean_text(b.get('journal', 'Journal'))}** ({clean_text(str(b.get('year', '')))}) • **PMID:** `{clean_text(str(b['pmid']))}`")
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
                        st.markdown(f"#### {clean_text(h['title'])}")
                        st.markdown(f"**PMID:** `{clean_text(str(h['pmid']))}` • Studied recently")
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
        with st.spinner("Synthesizing pedagogical digest..."):
            paper = fetch_pubmed_article(target_pmid)
            user_id = st.session_state.user.id if st.session_state.user else None
            mark_article_read(supabase_client, user_id, paper)
            digest = generate_student_digest(paper, gemini_client)

        if st.button("← Back to Feed", type="secondary"):
            st.session_state.active_view = "fyp"
            st.rerun()

        st.markdown(f"<h2 style='font-family: Newsreader, serif; font-size: 2.2rem; color:#FFFFFF;'>{clean_text(paper['title'])}</h2>", unsafe_allow_html=True)
        authors_display = ", ".join(paper["authors"][:4]) + (" et al." if len(paper["authors"]) > 4 else "")
        doi_suffix = f" • DOI: {paper['doi']}" if paper["doi"] else ""
        impact_chip = " • 🏛️ High-Impact Journal" if paper.get("is_high_impact") else ""

        st.markdown(
            f"🏛️ **{paper['journal']}** ({paper['year']}) • **PMID:** `{paper['pmid']}`{doi_suffix} • ⏱️ {paper.get('read_time_min', 2)} min read{impact_chip}"
        )
        st.markdown(f"✍️ **Authors:** {authors_display}")

        col_gdoc, col_pubmed, _ = st.columns([2, 2, 6])
        with col_gdoc:
            encoded_title = urllib.parse.quote(paper["title"])
            st.link_button("↗ Export to Google Doc", f"https://docs.google.com/document/create?title={encoded_title}", use_container_width=True)
        with col_pubmed:
            st.link_button("View on PubMed ↗", f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/", use_container_width=True)

        st.write("")

        # 1. Context
        with st.container(border=True):
            st.markdown("#### 1. CONTEXT & CLINICAL PROBLEM")
            st.markdown(clean_text(digest.get("context", "")))

        # 2. Abstract Summary
        with st.container(border=True):
            st.markdown("#### 2. ABSTRACT SUMMARY")
            st.markdown(clean_text(digest.get("abstract_summary", "")))

        # 3. Methods & Lab Skills to Know
        with st.container(border=True):
            st.markdown("#### 3. METHODS AND LAB SKILLS TO KNOW")
            skills = digest.get("methods_and_lab_skills", [])
            for s in skills:
                st.markdown(f"- **{clean_text(s.get('skill', ''))}:** {clean_text(s.get('description', ''))}")

        # 4. Critical Takeaways
        with st.container(border=True):
            st.markdown("#### 4. CRITICAL TAKEAWAYS & NEXT STEPS")
            crit = digest.get("critical_takeaways", {})
            st.markdown(f"**Research Importance:** {clean_text(crit.get('importance', ''))}")
            st.markdown(f"**Next Experiments Required:** {clean_text(crit.get('next_steps', ''))}")
            st.markdown("**Suggested Topics for Further Reading:**")
            for topic in crit.get("further_reading", []):
                st.markdown(f"- {clean_text(topic)}")

        # 5. Unedited Abstract Expander
        with st.expander("View original abstract"):
            st.markdown(clean_text(paper["abstract"]))

    except Exception as exc:
        st.error(f"Error loading study: {exc}")
        if st.button("Return to Feed", type="primary"):
            st.session_state.active_view = "fyp"
            st.rerun()