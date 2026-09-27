import base64
import html
import re
import urllib.error
import urllib.parse
from Bio import Entrez
import streamlit as st

# -----------------------------------------------------------------------------
# App Configuration & SVG Tech Favicon
# -----------------------------------------------------------------------------
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="7" fill="#0F172A"/>
<path d="M9 7C14 7 18 12 18 16C18 20 22 25 25 25" stroke="#38BDF8" stroke-width="2.5" stroke-linecap="round"/>
<path d="M23 7C18 7 14 12 14 16C14 20 10 25 7 25" stroke="#818CF8" stroke-width="2.5" stroke-linecap="round"/>
<circle cx="16" cy="16" r="2.5" fill="#38BDF8"/>
<circle cx="9" cy="7" r="2" fill="#818CF8"/>
<circle cx="25" cy="25" r="2" fill="#38BDF8"/>
</svg>"""

FAVICON_DATA_URI = f"data:image/svg+xml;base64,{base64.b64encode(FAVICON_SVG.encode()).decode()}"

st.set_page_config(
    page_title="ScholarPulse | Biomedical Digest",
    page_icon=FAVICON_DATA_URI,
    layout="wide",
    initial_sidebar_state="expanded",
)

Entrez.email = "scholarpulse.reader@internal.service"
Entrez.tool = "ScholarPulseApp"

# -----------------------------------------------------------------------------
# Clean Light Theme CSS
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        color: #1E293B;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    /* Paper Title typography */
    .paper-title {
        font-family: 'Newsreader', Georgia, serif;
        font-size: 1.85rem;
        font-weight: 500;
        line-height: 1.35;
        color: #0F172A;
        letter-spacing: -0.015em;
        margin-top: 0.5rem;
        margin-bottom: 0.75rem;
    }

    .meta-chip-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        align-items: center;
        margin-bottom: 1.25rem;
        font-size: 0.825rem;
        color: #64748B;
    }

    .meta-chip {
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-weight: 500;
        color: #334155;
    }

    .lesson-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.4rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }

    .lesson-header {
        font-size: 0.75rem;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #4F46E5;
        margin-bottom: 0.4rem;
    }

    .lesson-body {
        font-size: 0.95rem;
        line-height: 1.65;
        color: #334155;
    }

    .insight-bullet {
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #6366F1;
        background: #F8FAFC;
        border-radius: 0 6px 6px 0;
        font-size: 0.92rem;
        line-height: 1.55;
    }

    /* Print View Styles */
    @media print {
        body { background: white; color: black; }
        .stSidebar, button, header, footer { display: none !important; }
        .lesson-card { border: none; box-shadow: none; padding: 0; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "library" not in st.session_state:
    st.session_state.library = {}
if "active_pmid" not in st.session_state:
    st.session_state.active_pmid = "38157930"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}

# -----------------------------------------------------------------------------
# Entrez Data Fetching & Intelligence Helpers
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_pubmed_record(pmid: str):
    clean_pmid = str(pmid).strip()
    if not clean_pmid.isdigit():
        raise ValueError("PMID must contain digits only.")

    try:
        with Entrez.efetch(db="pubmed", id=clean_pmid, retmode="xml", rettype="abstract") as handle:
            records = Entrez.read(handle)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise LookupError(f"PMID {clean_pmid} was not found on PubMed.")
        raise RuntimeError(f"NCBI returned error: {e}")
    except Exception as err:
        raise RuntimeError(f"Failed to connect to NCBI: {err}")

    articles = records.get("PubmedArticle", [])
    if not articles:
        raise LookupError(f"No publication record exists for PMID {clean_pmid}.")

    citation = articles[0]["MedlineCitation"]
    article = citation["Article"]

    title = article.get("ArticleTitle", "Untitled Article").rstrip(".")
    authors = [
        f"{a.get('LastName', '')} {a.get('Initials', '')}".strip()
        for a in article.get("AuthorList", [])
        if a.get("LastName")
    ]

    journal_obj = article.get("Journal", {})
    journal = journal_obj.get("ISOAbbreviation") or journal_obj.get("Title") or "Unknown Source"
    pub_date = journal_obj.get("JournalIssue", {}).get("PubDate", {}).get("Year", "Recent")

    doi = None
    for eid in article.get("ELocationID", []):
        if getattr(eid, "attributes", {}).get("EIdType") == "doi":
            doi = str(eid)

    # Parse Abstract
    raw_abstract = article.get("Abstract", {}).get("AbstractText", [])
    sections = []
    plain_paragraphs = []

    if isinstance(raw_abstract, list):
        for part in raw_abstract:
            txt = str(part).strip()
            lbl = getattr(part, "attributes", {}).get("Label", "") if hasattr(part, "attributes") else ""
            if lbl:
                sections.append((lbl.title(), txt))
                plain_paragraphs.append(f"{lbl.upper()}: {txt}")
            else:
                plain_paragraphs.append(txt)
    elif raw_abstract:
        plain_paragraphs.append(str(raw_abstract).strip())

    full_text = " ".join(plain_paragraphs) if plain_paragraphs else "Abstract not provided."

    return {
        "pmid": clean_pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": pub_date,
        "doi": doi,
        "full_text": full_text,
        "sections": sections,
    }


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_related_papers(pmid: str, max_results: int = 4):
    """Queries NCBI elink tool to find real citations related to the given paper."""
    try:
        with Entrez.elink(dbfrom="pubmed", id=pmid, cmd="neighbor") as handle:
            link_record = Entrez.read(handle)
        links = link_record[0]["LinkSetDb"][0]["Link"]
        neighbor_ids = [l["Id"] for l in links[1 : max_results + 1]]

        summaries = []
        if neighbor_ids:
            with Entrez.esummary(db="pubmed", id=",".join(neighbor_ids)) as h_sum:
                docsums = Entrez.read(h_sum)
                for doc in docsums:
                    summaries.append({
                        "pmid": doc["Id"],
                        "title": doc.get("Title", "Untitled"),
                        "source": doc.get("Source", ""),
                        "pubdate": doc.get("PubDate", "").split()[0],
                    })
        return summaries
    except Exception:
        return []


def synthesize_lesson(article: dict) -> dict:
    """Transforms raw text into a multi-part pedagogical lesson breakdown."""
    text = article["full_text"]
    sections = dict(article["sections"])

    # 1. Research Question / Problem statement
    objective = (
        sections.get("Objective")
        or sections.get("Background")
        or sections.get("Rationale")
    )
    if not objective:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
        objective = sentences[0] if sentences else "Explores contemporary biomedical challenges."

    # 2. Methodology & Findings Narrative
    methods = sections.get("Methods") or sections.get("Methodology")
    results = sections.get("Results") or sections.get("Findings")

    if methods and results:
        narrative = f"Researchers executed the study through: {methods}\n\nDuring analysis, the experimental outcomes demonstrated that {results}"
    else:
        # Heuristic extraction of explanatory sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 25]
        middle = " ".join(sentences[1:-1]) if len(sentences) > 2 else text
        narrative = middle or "Detailed experimental procedures and observed metrics are outlined in the core text."

    # 3. High-Yield Bullet Takeaways
    bullets = []
    if results:
        bullets.append(f"**Primary Evidence:** {results[:220]}...")
    concl = sections.get("Conclusions") or sections.get("Conclusion")
    if concl:
        bullets.append(f"**Author Proposition:** {concl}")
    
    # If standard labeled sections are absent, extract quantified findings
    if not bullets:
        cand_sentences = [
            s for s in re.split(r"(?<=[.!?])\s+", text)
            if re.search(r"(\d+%|p\s*[<=]|significant|increased|decreased|observed)", s, re.I)
        ]
        for c in cand_sentences[:3]:
            bullets.append(c)
        if not bullets and text:
            bullets.append(text[:250] + "...")

    # 4. Critical Perspective / Caveats
    limitations = (
        "As with all primary findings, clinical translation depends on replication across broader cohort demographics, "
        "sample size validity, and resolving confounding physiological pathways."
    )

    return {
        "question": objective,
        "narrative": narrative,
        "bullets": bullets,
        "perspective": limitations,
    }


def generate_notesheet_markdown(article: dict, lesson: dict) -> str:
    authors_str = ", ".join(article["authors"][:3]) + (" et al." if len(article["authors"]) > 3 else "")
    bullets_txt = "\n".join([f"- {b}" for b in lesson["bullets"]])
    return f"""# Study Notesheet: {article['title']}
**Source:** {article['journal']} ({article['year']}) | **PMID:** {article['pmid']} | **Authors:** {authors_str}

---

## 1. Core Problem & Objective
{lesson['question']}

## 2. Experimental Mechanism & Narrative
{lesson['narrative']}

## 3. High-Yield Takeaways
{bullets_txt}

## 4. Critical Assessment & Nuance
{lesson['perspective']}

---
*Synthesized via ScholarPulse Biomedical Digest*
"""


def generate_word_document_html(article: dict, lesson: dict) -> str:
    """Produces a clean Word-compatible HTML document."""
    bullets_html = "".join([f"<li>{html.escape(b)}</li>" for b in lesson["bullets"]])
    return f"""<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
    <head><title>{html.escape(article['title'])}</title>
    <style>
    body {{ font-family: Calibri, Arial, sans-serif; line-height: 1.5; color: #1E293B; }}
    h1 {{ font-size: 18pt; color: #0F172A; }}
    h2 {{ font-size: 13pt; color: #4338CA; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; margin-top: 18px; }}
    p {{ font-size: 11pt; }}
    .meta {{ font-size: 10pt; color: #64748B; margin-bottom: 15px; }}
    </style></head>
    <body>
        <h1>{html.escape(article['title'])}</h1>
        <div class="meta">{html.escape(article['journal'])} ({article['year']}) | PMID: {article['pmid']}</div>
        <h2>1. The Core Research Dilemma</h2>
        <p>{html.escape(lesson['question'])}</p>
        <h2>2. Methodological Breakdown & Detailed Narrative</h2>
        <p>{html.escape(lesson['narrative'])}</p>
        <h2>3. High-Yield Insights</h2>
        <ul>{bullets_html}</ul>
        <h2>4. Critical Perspective</h2>
        <p>{html.escape(lesson['perspective'])}</p>
    </body></html>"""


# -----------------------------------------------------------------------------
# Sidebar: Library, Controls, & LLM Options
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🧬 ScholarPulse")
    st.caption("Biomedical Research Synthesizer")
    st.divider()

    # Saved Library Section
    st.markdown("#### 📚 Saved Library")
    if st.session_state.library:
        for pmid_id, saved_item in list(st.session_state.library.items()):
            col_open, col_del = st.columns([4, 1])
            with col_open:
                if st.button(f"{saved_item['title'][:28]}...", key=f"lib_{pmid_id}", use_container_width=True):
                    st.session_state.active_pmid = pmid_id
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"del_{pmid_id}", help="Remove from library"):
                    del st.session_state.library[pmid_id]
                    st.rerun()
    else:
        st.caption("No papers bookmarked yet. Look up an article and click 'Bookmark'.")

    st.divider()

    # Optional OpenAI Key for full Conversational AI
    st.markdown("#### 🤖 Socratic Dialogue Engine")
    openai_key = st.text_input(
        "OpenAI API Key (Optional)",
        type="password",
        help="If provided, the Socratic Tutor uses GPT-4o-mini for open-ended conversation. If left blank, the app uses an interactive rule-based diagnostic tutor.",
    )

    st.divider()
    st.markdown("#### 🔍 Try Curated Papers")
    c1, c2 = st.columns(2)
    if c1.button("CRISPR 38157930", use_container_width=True):
        st.session_state.active_pmid = "38157930"
        st.rerun()
    if c2.button("mRNA 32284366", use_container_width=True):
        st.session_state.active_pmid = "32284366"
        st.rerun()


# -----------------------------------------------------------------------------
# Main Application Header & Search
# -----------------------------------------------------------------------------
col_input, col_btn = st.columns([5, 1], vertical_alignment="bottom")

with col_input:
    query_pmid = st.text_input(
        "Enter PubMed ID (PMID)",
        value=st.session_state.active_pmid,
        placeholder="e.g., 38157930, 32284366, 25957688",
    )

with col_btn:
    fetch_clicked = st.button("Synthesize", type="primary", use_container_width=True)

if fetch_clicked and query_pmid.strip():
    st.session_state.active_pmid = query_pmid.strip()
    st.rerun()

current_pmid = st.session_state.active_pmid

# -----------------------------------------------------------------------------
# Fetch and Render Article Content
# -----------------------------------------------------------------------------
try:
    with st.spinner("Accessing Entrez & constructing pedagogical lesson..."):
        article = fetch_pubmed_record(current_pmid)
        lesson = synthesize_lesson(article)
        notesheet_md = generate_notesheet_markdown(article, lesson)
        word_doc_html = generate_word_document_html(article, lesson)
        related_articles = fetch_related_papers(current_pmid)

    # 1. Header & Actions Bar
    authors_preview = ", ".join(article["authors"][:4]) + (" et al." if len(article["authors"]) > 4 else "")
    
    st.markdown(f'<div class="paper-title">{article["title"]}</div>', unsafe_allow_html=True)
    
    doi_badge = f'<span class="meta-chip">DOI: {article["doi"]}</span>' if article["doi"] else ""
    st.markdown(
        f"""
        <div class="meta-chip-bar">
            <span class="meta-chip">🏛️ {article['journal']} ({article['year']})</span>
            <span class="meta-chip">PMID: {article['pmid']}</span>
            {doi_badge}
            <span>✍️ {authors_preview}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action Toolbar
    act_col1, act_col2, act_col3, act_col4 = st.columns([1.2, 1.4, 1.4, 1.2])

    with act_col1:
        is_saved = current_pmid in st.session_state.library
        btn_label = "★ Saved" if is_saved else "☆ Bookmark"
        if st.button(btn_label, use_container_width=True):
            if is_saved:
                del st.session_state.library[current_pmid]
            else:
                st.session_state.library[current_pmid] = {"title": article["title"]}
            st.rerun()

    with act_col2:
        encoded_title = urllib.parse.quote(article["title"])
        docs_url = f"https://docs.google.com/document/create?title={encoded_title}"
        st.link_button("↗ Google Docs", docs_url, use_container_width=True, help="Opens a new Google Doc ready to paste your notesheet.")

    with act_col3:
        st.download_button(
            label="📄 Word (.doc)",
            data=word_doc_html,
            file_name=f"Study_Notes_PMID_{current_pmid}.doc",
            mime="application/msword",
            use_container_width=True,
        )

    with act_col4:
        st.download_button(
            label="📝 Notes (.md)",
            data=notesheet_md,
            file_name=f"Lesson_{current_pmid}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.write("")

    # -------------------------------------------------------------------------
    # Main Tabs: Lesson, Socratic Tutor, Explorations
    # -------------------------------------------------------------------------
    tab_lesson, tab_chat, tab_explore = st.tabs(["📖 Lesson & Takeaways", "💬 Socratic Comprehension Tutor", "🔬 Deep Search & Related"])

    # TAB 1: Pedagogy & Lesson Breakdown
    with tab_lesson:
        st.markdown(
            f"""
            <div class="lesson-card">
                <div class="lesson-header">1. The Research Dilemma & Context</div>
                <div class="lesson-body">{lesson['question']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="lesson-card">
                <div class="lesson-header">2. Methodological Mechanics & Narrative</div>
                <div class="lesson-body">{lesson['narrative']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### High-Yield Takeaways")
        for b in lesson["bullets"]:
            st.markdown(f'<div class="insight-bullet">{b}</div>', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="lesson-card" style="border-left: 3px solid #F59E0B; margin-top: 1rem;">
                <div class="lesson-header" style="color: #D97706;">3. Scientific Nuance & Limitations</div>
                <div class="lesson-body">{lesson['perspective']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Show Unedited PubMed Abstract"):
            st.write(article["full_text"])

    # TAB 2: Socratic Comprehension Chatbot
    with tab_chat:
        st.caption("Test whether you truly grasp the underlying mechanisms, endpoints, and caveats of this paper.")
        
        chat_key = f"chat_{current_pmid}"
        if chat_key not in st.session_state.chat_history:
            st.session_state.chat_history[chat_key] = [
                {
                    "role": "assistant",
                    "content": f"Hello! I am your study partner for **'{article['title'][:55]}...'**.\n\nTo test your grasp: in your own words, **what is the primary problem this study attempts to solve, and what experimental intervention or finding supports it?**",
                }
            ]

        # Display conversational stream
        for msg in st.session_state.chat_history[chat_key]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_query = st.chat_input("Explain your understanding or answer the question above...")

        if user_query:
            # Render user message
            st.session_state.chat_history[chat_key].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # Response logic: OpenAI if key available, else Socratic Heuristic Engine
            with st.chat_message("assistant"):
                if openai_key.strip():
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_key.strip())
                        system_prompt = f"""You are a brilliant biomedical professor conducting a Socratic oral examination on a medical student regarding this paper:
Title: {article['title']}
Abstract: {article['full_text']}

Guidelines:
1. Don't simply give away answers.
2. Evaluate their explanation: praise valid intuitions, challenge misconceptions, and probe their understanding of mechanism, control groups, and statistical conclusions.
3. Keep responses conversational, concise (under 120 words), and intellectually stimulating.
"""
                        api_messages = [{"role": "system", "content": system_prompt}] + [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.chat_history[chat_key][-5:]
                        ]
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=api_messages,
                            temperature=0.4,
                        )
                        reply_text = response.choices[0].message.content
                    except Exception as e:
                        reply_text = f"*(API error: {e}. Reverting to local evaluation mode.)*\n\n"
                else:
                    # Built-in Heuristic Socratic Engine
                    tokens = set(re.findall(r"\w{4,}", user_query.lower()))
                    abstract_tokens = set(re.findall(r"\w{4,}", article["full_text"].lower()))
                    overlap = tokens.intersection(abstract_tokens)

                    if len(overlap) >= 3:
                        reply_text = (
                            f"**Good observation.** You accurately engaged with key concepts ({', '.join(list(overlap)[:3])}). "
                            "Now, let's go one layer deeper: **What potential confounders, control variables, or biological limitations** "
                            "might prevent this conclusion from holding true in all real-world conditions?"
                        )
                    else:
                        reply_text = (
                            "You're on the right track, but try to tie your reasoning more directly to the specific results recorded in the text. "
                            f"Consider: **What did the authors specifically measure or manipulate ({article['journal']}, {article['year']})?**"
                        )

                st.markdown(reply_text)
                st.session_state.chat_history[chat_key].append({"role": "assistant", "content": reply_text})

    # TAB 3: Exploration & Related Citations
    with tab_explore:
        st.markdown("##### Real-Time Related Articles (NCBI Citation Network)")
        if related_articles:
            for item in related_articles:
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background: white; border: 1px solid #E2E8F0; padding: 0.8rem; border-radius: 6px; margin-bottom: 0.5rem;">
                            <strong>{item['title']}</strong><br/>
                            <span style="font-size: 0.8rem; color: #64748B;">{item['source']} ({item['pubdate']}) &bull; PMID: {item['pmid']}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(f"Load PMID {item['pmid']}", key=f"rel_{item['pmid']}"):
                        st.session_state.active_pmid = item["pmid"]
                        st.rerun()
        else:
            st.info("No immediate related neighbor citations retrieved for this PMID.")

        st.divider()
        st.markdown("##### External Academic Gateways")
        query_encoded = urllib.parse.quote(article["title"])
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.link_button(
                "Search on Google Scholar ↗",
                f"https://scholar.google.com/scholar?q={query_encoded}",
                use_container_width=True,
            )
        with col_g2:
            st.link_button(
                "View on Official PubMed Portal ↗",
                f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
                use_container_width=True,
            )

except ValueError as ve:
    st.error(f"Input Error: {ve}")
except LookupError as le:
    st.warning(f"Record Not Found: {le}")
except RuntimeError as re_err:
    st.error(f"Connection Issue: {re_err}")