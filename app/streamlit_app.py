import os
import io
import re
import csv
from collections import Counter
from datetime import datetime

import requests
import streamlit as st
import matplotlib.pyplot as plt

# ----------------- Config -----------------
DEFAULT_API = os.environ.get("API_BASE", "http://127.0.0.1:8000")
st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")
st.title("🎬 Movie Recommender")

# ----------------- Styles -----------------
st.markdown("""
<style>
/* Tighter, consistent card layout */
.movie-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px;
  padding: 12px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Remove the faint “pill” above each poster by making wrapper transparent and reset height */
.poster-wrap {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: transparent; /* was #222 causing a pill look in some themes */
}

/* Poster keeps aspect ratio */
.poster {
  width: 100%;
  aspect-ratio: 2 / 3;
  object-fit: cover;
  display: block;
}

/* Title = at most 2 lines to keep rows tidy */
.title {
  font-weight: 700;
  font-size: 1rem;
  line-height: 1.25;
  min-height: 2.5em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Fixed-height overview box with ellipsis (8 lines for roomier copy) */
.overview-clamp {
  font-size: 0.98rem;
  color: #d6d6d6;
  display: -webkit-box;
  -webkit-line-clamp: 8;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 10.8em;  /* calibrate: ~8 lines at default Streamlit font size */
  margin-right: 2px;
}

/* A fixed space holder to keep rows aligned where "Read more…" isn’t shown */
.readmore-placeholder {
  height: 46px;               /* matches Streamlit button height with padding */
  border-radius: 0.5rem;
  border: 1px solid transparent;
  margin-top: 4px;
}

/* Keep the unlike row anchored to the bottom of each card */
.spacer-flex {
  flex: 1 1 auto;
}

/* Make rows breathe a bit */
.card-bottom-gap {
  height: 8px;
}

/* Slightly bigger gap between columns */
.block-container .stColumns {
  gap: 2rem !important;
}
</style>
""", unsafe_allow_html=True)

# ----------------- Helpers -----------------
def safe_get(url: str, **kwargs):
    try:
        r = requests.get(url, timeout=kwargs.pop("timeout", 30), **kwargs)
        return (r.ok, (r.json() if r.ok else r.text))
    except Exception as e:
        return (False, f"Request error: {e}")

def safe_post(url: str, **kwargs):
    try:
        r = requests.post(url, timeout=kwargs.pop("timeout", 30), **kwargs)
        return (r.ok, (r.json() if r.ok else r.text))
    except Exception as e:
        return (False, f"Request error: {e}")

def safe_delete(url: str, **kwargs):
    try:
        r = requests.delete(url, timeout=kwargs.pop("timeout", 30), **kwargs)
        return (r.ok, (r.json() if r.ok else r.text))
    except Exception as e:
        return (False, f"Request error: {e}")

def to_csv_bytes(rows, field_order=None):
    buf = io.StringIO()
    if not rows:
        rows = []
    if field_order is None:
        keys = set()
        for r in rows:
            if isinstance(r, dict):
                keys.update(r.keys())
        field_order = sorted(keys) if keys else []
    writer = csv.DictWriter(buf, fieldnames=field_order)
    writer.writeheader()
    for r in rows:
        if isinstance(r, dict):
            writer.writerow({k: r.get(k, "") for k in field_order})
    return buf.getvalue().encode("utf-8")

def parse_dt(dt_str):
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    return None

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()

# ----------------- Session init -----------------
if "_force_liked_reload" not in st.session_state:
    st.session_state["_force_liked_reload"] = True
if "similar_results" not in st.session_state:
    st.session_state["similar_results"] = []
if "similar_title" not in st.session_state:
    st.session_state["similar_title"] = ""
if "likes_cache" not in st.session_state:
    st.session_state["likes_cache"] = {}
if "profiles" not in st.session_state:
    st.session_state["profiles"] = {}
if "recommendation_results" not in st.session_state:
    st.session_state["recommendation_results"] = []
if "browse_results" not in st.session_state:
    st.session_state["browse_results"] = []

# ----------------- Sidebar -----------------
with st.sidebar:
    st.header("Settings")
    api_base = st.text_input("API base URL", value=DEFAULT_API)
    user_id = st.number_input("Active user ID", min_value=1, value=1001, step=1, key="user_id_input")

    profile = st.session_state["profiles"].setdefault(int(user_id), {"display_name": "", "bio": ""})
    profile["display_name"] = st.text_input("Display name (local)", value=profile.get("display_name", ""))
    profile["bio"] = st.text_area("Bio (local)", value=profile.get("bio", ""), height=80)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ensure User"):
            ok, data = safe_post(f"{api_base}/users", json={"user_id": int(user_id)}, timeout=15)
            st.success(data if ok else str(data))
    with c2:
        if st.button("View Interactions (raw)"):
            ok, data = safe_get(f"{api_base}/interactions/{int(user_id)}", params={"limit": 50}, timeout=15)
            if ok:
                st.json(data)
            else:
                st.warning(str(data))

st.markdown("---")

# Ensure per-user cache exists
_ = st.session_state["likes_cache"].setdefault(int(user_id), {})

# ----------------- Grid Renderer -----------------
def render_movie_grid(
    movies,
    cols=4,
    show_like=True,
    show_similar=True,
    show_unlike=False,
    similar_limit=12,
    section="default",
    profile_mode=False,           # NEW: profile layout (3 columns, larger desc, consistent spacing)
):
    if not movies:
        return

    # For profile we want 3 columns and bigger “grid gap”
    if profile_mode:
        cols = 3

    col_objs = st.columns(cols, gap="large")
    for i, m in enumerate(movies):
        if not isinstance(m, dict):
            continue

        with col_objs[i % cols]:
            raw_title = (m.get("title") or "Untitled").strip()
            year = m.get("year")
            title = f"{raw_title} ({year})" if year else raw_title
            poster = (m.get("poster_path") or "").strip()
            overview_full = normalize_text(m.get("overview"))
            mid = m.get("movie_id")

            st.markdown('<div class="movie-card">', unsafe_allow_html=True)

            # Poster (transparent wrapper to remove the “pill”)
            if poster:
                st.markdown(
                    f'<div class="poster-wrap"><img class="poster" src="{poster}" alt="{raw_title} poster" /></div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<div class="poster-wrap"><div class="poster" style="display:flex;align-items:center;justify-content:center;color:#777;">No Poster</div></div>',
                    unsafe_allow_html=True
                )

            # Title (no duplicate year added later)
            st.markdown(f'<div class="title">{title}</div>', unsafe_allow_html=True)

            # Overview (fixed height, then optional Read more…)
            if overview_full:
                st.markdown(f'<div class="overview-clamp">{overview_full}</div>', unsafe_allow_html=True)
                # Show popover only when it actually needs truncation
                if len(overview_full) > 300:
                    with st.popover("Read more …", use_container_width=True):
                        st.write(overview_full)
                else:
                    # Keep rows aligned by inserting a placeholder of the same height
                    st.markdown('<div class="readmore-placeholder"></div>', unsafe_allow_html=True)
            else:
                # No overview: reserve the space anyway so buttons align
                st.markdown('<div class="overview-clamp"></div>', unsafe_allow_html=True)
                st.markdown('<div class="readmore-placeholder"></div>', unsafe_allow_html=True)

            # Push actions to bottom consistently
            st.markdown('<div class="spacer-flex"></div>', unsafe_allow_html=True)

            # Action buttons (horizontal)
            btn_defs = []
            if show_like and mid is not None:
                btn_defs.append(("👍 Like", f"{section}_like_{mid}"))
            if show_unlike and mid is not None:
                btn_defs.append(("💔 Unlike", f"{section}_unlike_{mid}"))
            if show_similar and mid is not None:
                btn_defs.append(("🎯 Similar", f"{section}_sim_{mid}"))

            if btn_defs:
                bcols = st.columns(len(btn_defs), gap="small")
                for idx, (label, key) in enumerate(btn_defs):
                    with bcols[idx]:
                        if st.button(label, key=key, use_container_width=True):
                            if label.startswith("👍"):
                                payload = {"user_id": int(user_id), "movie_id": int(mid), "interaction_type": "like"}
                                ok, resp = safe_post(f"{api_base}/interactions", json=payload, timeout=15)
                                if ok:
                                    st.success("Saved!")
                                    uid = int(user_id)
                                    cache = st.session_state["likes_cache"].setdefault(uid, {})
                                    cache[mid] = {
                                        "movie_id": m.get("movie_id"),
                                        "title": m.get("title"),
                                        "year": m.get("year"),
                                        "overview": m.get("overview"),
                                        "poster_path": m.get("poster_path"),
                                        "genres": m.get("genres"),
                                    }
                                else:
                                    st.error(str(resp))
                            elif label.startswith("💔"):
                                ok, resp = safe_delete(f"{api_base}/interactions/{int(user_id)}/{int(mid)}", timeout=15)
                                if ok:
                                    st.success("Unliked!")
                                    uid = int(user_id)
                                    st.session_state["likes_cache"].get(uid, {}).pop(mid, None)
                                    st.session_state["_force_liked_reload"] = True
                                    st.rerun()
                                else:
                                    st.error(str(resp))
                            elif label.startswith("🎯"):
                                ok, resp = safe_get(
                                    f"{api_base}/similar/{int(mid)}",
                                    params={"limit": int(similar_limit)},
                                    timeout=30,
                                )
                                if ok:
                                    st.session_state["similar_results"] = resp
                                    st.session_state["similar_title"] = raw_title
                                else:
                                    st.warning(str(resp))

            st.markdown('<div class="card-bottom-gap"></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)  # end .movie-card
            st.write("")  # spacer

# ----------------- Tabs -----------------
home_tab, profile_tab = st.tabs(["🏠 Home", "👤 Profile"])

with home_tab:
    st.subheader("🔎 Search movies and 👍 like them")
    q = st.text_input("Search by title", placeholder="e.g., Inception", key="search_q")
    if q:
        ok, data = safe_get(f"{api_base}/movies/search", params={"q": q, "limit": 16}, timeout=30)
        if ok:
            movies = data or []
            if movies:
                render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="search")
            else:
                st.info("No results.")
        else:
            st.error(str(data))

    if st.session_state["similar_results"]:
        st.subheader(f"🎯 Similar to: {st.session_state['similar_title']}")
        render_movie_grid(
            st.session_state["similar_results"],
            cols=4,
            show_like=True,
            show_similar=False,
            section="similar",
        )

    st.markdown("---")

    st.subheader("👤 Recommendations for the active user")
    k = st.slider("How many results?", 1, 30, 10, key="rec_k")
    if st.button("Get Recommendations"):
        ok, data = safe_get(f"{api_base}/recommendations/{int(user_id)}", params={"limit": int(k)}, timeout=30)
        if ok:
            items = (data or {}).get("items", [])
            st.session_state["recommendation_results"] = items or []
            if not items:
                st.info("No recommendations yet. Try liking a few movies first.")
        else:
            st.session_state["recommendation_results"] = []
            st.error(str(data))

    if st.session_state["recommendation_results"]:
        render_movie_grid(
            st.session_state["recommendation_results"],
            cols=4,
            show_like=True,
            show_similar=True,
            similar_limit=12,
            section="recommendations",
        )

    st.markdown("---")

    st.subheader("🎬 Browse All Movies")
    col1, col2, col3 = st.columns(3)
    with col1:
        browse_limit = st.slider("Number of movies", 5, 50, 20)
    with col2:
        genre_filter = st.selectbox("Filter by genre", ["", "Action", "Comedy", "Drama", "Horror", "Sci-Fi", "Thriller"])
    with col3:
        year_filter = st.selectbox("Filter by year", ["", "2020+", "2010-2019", "2000-2009", "1990-1999"])

    if st.button("Browse Movies"):
        params = {"limit": browse_limit}
        if genre_filter:
            params["genre"] = genre_filter
        if year_filter == "2020+":
            params["year_min"] = 2020
        elif year_filter == "2010-2019":
            params["year_min"] = 2010; params["year_max"] = 2019
        elif year_filter == "2000-2009":
            params["year_min"] = 2000; params["year_max"] = 2009
        elif year_filter == "1990-1999":
            params["year_min"] = 1990; params["year_max"] = 1999

        ok, data = safe_get(f"{api_base}/movies", params=params, timeout=30)
        if ok:
            st.session_state["browse_results"] = data or []
            if not st.session_state["browse_results"]:
                st.info("No movies found with those filters.")
        else:
            st.session_state["browse_results"] = []
            st.error(str(data))

    if st.session_state["browse_results"]:
        render_movie_grid(
            st.session_state["browse_results"],
            cols=4,
            show_like=True,
            show_similar=True,
            similar_limit=12,
            section="browse_movies",
        )

with profile_tab:
    st.subheader("👤 Profile")

    # Header card
    colA, colB = st.columns([1, 3])
    with colA:
        initials = (st.session_state["profiles"][int(user_id)]["display_name"].strip()[:1] or str(user_id)[:1]).upper()
        st.markdown(f"""
        <div style="width:96px;height:96px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;font-size:36px;">
            {initials}
        </div>
        """, unsafe_allow_html=True)
    with colB:
        st.markdown(f"**User ID:** `{int(user_id)}`")
        prof = st.session_state["profiles"][int(user_id)]
        if prof.get("display_name"):
            st.markdown(f"**Name:** {prof['display_name']}")
        if prof.get("bio"):
            st.markdown(f"> {prof['bio']}")

    st.markdown("---")

    # Controls
    rcol1, rcol2 = st.columns([1, 1])
    with rcol2:
        if st.button("🧹 Clear local likes cache"):
            st.session_state["likes_cache"].pop(int(user_id), None)
            st.session_state["likes_cache"][int(user_id)] = {}

    # Fetch liked movies from API (once, or when forced)
    liked_movies_api = []
    if st.session_state.get("_force_liked_reload", True):
        ok, data = safe_get(f"{api_base}/users/{int(user_id)}/liked", params={"limit": 500}, timeout=30)
        if ok and isinstance(data, list):
            liked_movies_api = data
        else:
            st.warning(str(data) if not ok else "Unexpected response shape from /users/{id}/liked")
        st.session_state["_force_liked_reload"] = False
    else:
        ok, data = safe_get(f"{api_base}/users/{int(user_id)}/liked", params={"limit": 500}, timeout=30)
        if ok and isinstance(data, list):
            liked_movies_api = data

    # Merge API likes with local cache for instant UI
    uid = int(user_id)
    cache_map = st.session_state["likes_cache"].get(uid, {})
    merged = {}
    for m in liked_movies_api:
        if m.get("movie_id") is not None:
            merged[m["movie_id"]] = m
    for mid, m in cache_map.items():
        merged[mid] = {**merged.get(mid, {}), **m}
    liked_movies = list(merged.values())

    # Basic stats
    st.metric("Total interactions", len(liked_movies_api))
    st.metric("Liked movies", len(liked_movies))

    if liked_movies:
        csv_bytes = to_csv_bytes(liked_movies, field_order=[
            "movie_id","title","year","overview","poster_path","genres"
        ])
        st.download_button(
            "⬇️ Download Liked Movies (CSV)",
            data=csv_bytes,
            file_name=f"user_{uid}_liked_movies.csv",
            mime="text/csv"
        )

        with st.expander("📊 View Genre Preferences"):
            genres = []
            for m in liked_movies:
                gs = m.get("genres")
                if gs:
                    if isinstance(gs, str):
                        genres.extend([g.strip() for g in gs.split(",") if g.strip()])
                    elif isinstance(gs, list):
                        genres.extend([str(g).strip() for g in gs if str(g).strip()])
            if genres:
                counts = Counter(genres)
                top = counts.most_common(8)
                fig = plt.figure(figsize=(10, 6))
                labels = [k for k, _ in top]
                values = [v for _, v in top]
                plt.bar(labels, values)
                plt.title("Your Favorite Genres")
                plt.xlabel("Genre")
                plt.ylabel("Number of Liked Movies")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.info("No genre data available yet.")

        st.markdown("---")

        # 💖 My Liked Movies — profile layout on (3 columns, bigger desc, aligned buttons)
        st.subheader("🎬 My Liked Movies")
        render_movie_grid(
            liked_movies,
            cols=3,                      # explicitly 3 per row
            show_like=False,
            show_similar=False,
            show_unlike=True,
            similar_limit=12,
            section="liked_movies",
            profile_mode=True,
        )

        # Similar results (if previously clicked)
        if st.session_state["similar_results"]:
            st.markdown("---")
            st.subheader(f"🎯 Similar to: {st.session_state['similar_title']}")
            render_movie_grid(
                st.session_state["similar_results"],
                cols=3,
                show_like=True,
                show_similar=False,
                section="profile_similar",
                profile_mode=True,
            )

    else:
        st.info("No liked movies yet. Like some on the Home tab!")
