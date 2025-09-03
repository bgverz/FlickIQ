import os
import io
import csv
from collections import Counter
from datetime import datetime

import requests
import streamlit as st
import matplotlib.pyplot as plt  # for the genres chart

DEFAULT_API = os.environ.get("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")
st.title("🎬 Movie Recommender")

# ------------- Helpers -------------
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

def to_csv_bytes(rows, field_order=None):
    import io as _io
    import csv as _csv
    buf = _io.StringIO()
    if not rows:
        rows = []
    if field_order is None:
        keys = set()
        for r in rows:
            if isinstance(r, dict):
                keys.update(r.keys())
        field_order = sorted(keys) if keys else []
    writer = _csv.DictWriter(buf, fieldnames=field_order)
    writer.writeheader()
    for r in rows:
        if isinstance(r, dict):
            writer.writerow({k: r.get(k, "") for k in field_order})
    return buf.getvalue().encode("utf-8")

def parse_dt(dt_str):
    """Best-effort parse for created_at; returns datetime or None."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    return None

def ensure_movie_dict(x, cache_map):
    """
    Build a movie-like dict from an interaction row (x).
    If API doesn't include metadata, fall back to cache_map by movie_id.
    """
    mid = (x or {}).get("movie_id")
    if mid in cache_map:
        return cache_map[mid]
    return {
        "movie_id": mid,
        "title": x.get("title"),
        "year": x.get("year"),
        "overview": x.get("overview"),
        "poster_path": x.get("poster_path"),
        "genres": x.get("genres"),
    }

# ------------- Sidebar -------------
with st.sidebar:
    st.header("Settings")
    api_base = st.text_input("API base URL", value=DEFAULT_API)
    user_id = st.number_input("Active user ID", min_value=1, value=1001, step=1)

    # simple local profile store (per user_id)
    if "profiles" not in st.session_state:
        st.session_state["profiles"] = {}  # { user_id: {"display_name": "...", "bio": "..."} }
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

# ------------- Session for "Similar" -------------
if "similar_results" not in st.session_state:
    st.session_state["similar_results"] = []
if "similar_title" not in st.session_state:
    st.session_state["similar_title"] = ""

# ------------- Session for per-user liked movies cache (instant UI updates) -------------
if "likes_cache" not in st.session_state:
    st.session_state["likes_cache"] = {}  # { user_id: {movie_id: movie_dict} }
_ = st.session_state["likes_cache"].setdefault(int(user_id), {})

# ------------- Grid Renderer -------------
def render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="default"):
    grid_cols = st.columns(cols)
    for i, m in enumerate(movies or []):
        if not isinstance(m, dict):
            continue
        with grid_cols[i % cols]:
            poster = m.get("poster_path")
            title = m.get("title") or "Untitled"
            year = m.get("year")
            overview = m.get("overview")

            if poster:
                st.image(poster, caption=title, width=300)
            else:
                st.caption(title)
            if year:
                st.caption(f"{year}")

            b1, b2 = st.columns(2)
            if show_like and m.get("movie_id") is not None:
                with b1:
                    if st.button(f"👍 Like #{m['movie_id']}", key=f"{section}_like_{m['movie_id']}"):
                        payload = {"user_id": int(user_id), "movie_id": int(m["movie_id"]), "interaction_type": "like"}
                        ok, resp = safe_post(f"{api_base}/interactions", json=payload, timeout=15)
                        if ok:
                            st.success("Saved!")
                            # Add to likes cache so it shows up instantly in Profile
                            uid = int(user_id)
                            cache = st.session_state["likes_cache"].setdefault(uid, {})
                            cache[m["movie_id"]] = {
                                "movie_id": m.get("movie_id"),
                                "title": m.get("title"),
                                "year": m.get("year"),
                                "overview": m.get("overview"),
                                "poster_path": m.get("poster_path"),
                                "genres": m.get("genres"),
                            }
                        else:
                            st.error(str(resp))

            if show_similar and m.get("movie_id") is not None:
                with b2:
                    if st.button("🎯 Similar", key=f"{section}_sim_{m['movie_id']}"):
                        ok, resp = safe_get(
                            f"{api_base}/similar/{int(m['movie_id'])}",
                            params={"limit": int(similar_limit)},
                            timeout=30,
                        )
                        if ok:
                            st.session_state["similar_results"] = resp
                            st.session_state["similar_title"] = title
                        else:
                            st.warning(str(resp))

            if overview:
                text = str(overview)
                st.write(text[:220] + ("..." if len(text) > 220 else ""))
            st.write("---")

# ------------- Tabs -------------
home_tab, profile_tab = st.tabs(["🏠 Home", "👤 Profile"])

with home_tab:
    # --- Search & like ---
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

    # --- Similar to selected ---
    if st.session_state["similar_results"]:
        st.subheader(f"🎯 Similar to: {st.session_state['similar_title']}")
        render_movie_grid(
            st.session_state["similar_results"],
            cols=6,
            show_like=True,
            show_similar=False,
            section="similar",
        )

    st.markdown("---")

    # --- User-based recommendations ---
    st.subheader("👤 Recommendations for the active user")
    k = st.slider("How many results?", 1, 30, 10, key="rec_k")
    if st.button("Get Recommendations"):
        ok, data = safe_get(f"{api_base}/recommendations/{int(user_id)}", params={"limit": int(k)}, timeout=30)
        if ok:
            items = (data or {}).get("items", [])
            if items:
                render_movie_grid(items, cols=5, show_like=True, show_similar=True, similar_limit=12, section="recommendations")
            else:
                st.info("No recommendations yet. Try liking a few movies first.")
        else:
            st.error(str(data))

    st.markdown("---")

    # --- Browse All Movies ---
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
            movies = data or []
            if movies:
                render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="browse")
            else:
                st.info("No movies found with those filters.")
        else:
            st.error(str(data))

with profile_tab:
    st.subheader("👤 Profile")

    # Header card
    colA, colB = st.columns([1, 3])
    with colA:
        initials = (profile["display_name"].strip()[:1] or str(user_id)[:1]).upper()
        st.markdown(f"""
        <div style="width:96px;height:96px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;font-size:36px;">
            {initials}
        </div>
        """, unsafe_allow_html=True)
    with colB:
        st.markdown(f"**User ID:** `{int(user_id)}`")
        if profile.get("display_name"):
            st.markdown(f"**Name:** {profile['display_name']}")
        if profile.get("bio"):
            st.markdown(f"> {profile['bio']}")

    st.markdown("---")

    # Controls
    rcol1, rcol2 = st.columns([1, 1])
    with rcol1:
        if st.button("🔄 Refresh from API"):
            st.session_state["_force_liked_reload"] = True
    with rcol2:
        if st.button("🧹 Clear local likes cache"):
            st.session_state["likes_cache"].pop(int(user_id), None)
            st.session_state["likes_cache"][int(user_id)] = {}

    # Fetch liked movies from new API endpoint
    liked_movies_api = []
    if st.session_state.get("_force_liked_reload", True):
        ok, data = safe_get(f"{api_base}/users/{int(user_id)}/liked", params={"limit": 200}, timeout=30)
        if ok and isinstance(data, list):
            liked_movies_api = data
        elif not ok:
            st.warning(str(data))
        st.session_state["_force_liked_reload"] = False

    # Use liked movies count as total for now (to avoid 422 error)
    total_interactions = len(liked_movies_api)

    # Merge API likes with local cache for instant UI
    uid = int(user_id)
    cache_map = st.session_state["likes_cache"].get(uid, {})  # {movie_id: movie_dict}

    # Create merged liked movies list
    merged = {}
    for m in liked_movies_api:
        if m.get("movie_id") is not None:
            merged[m["movie_id"]] = m
    for mid, m in cache_map.items():
        merged[mid] = {**merged.get(mid, {}), **m}

    liked_movies = list(merged.values())

    # Basic stats
    st.metric("Total interactions", total_interactions)
    st.metric("Liked movies", len(liked_movies))

    if liked_movies:
        # CSV export
        csv_bytes = to_csv_bytes(liked_movies, field_order=[
            "movie_id","title","year","overview","poster_path","genres"
        ])
        st.download_button(
            "⬇️ Download Liked Movies (CSV)",
            data=csv_bytes,
            file_name=f"user_{uid}_liked_movies.csv",
            mime="text/csv"
        )

        # Genre preferences chart in expandable section
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

        # My Liked Movies section (main display)
        st.subheader("🎬 My Liked Movies")
        render_movie_grid(
            liked_movies[:24],  # Show up to 24 movies to avoid overwhelming the UI
            cols=6, 
            show_like=False, 
            show_similar=False,  # Remove similar buttons from profile
            similar_limit=12, 
            section="liked_movies"
        )

        if len(liked_movies) > 24:
            st.info(f"Showing 24 of {len(liked_movies)} liked movies. Download CSV for complete list.")

        # Similar results from clicked movies (same as Home tab)
        if st.session_state["similar_results"]:
            st.markdown("---")
            st.subheader(f"🎯 Similar to: {st.session_state['similar_title']}")
            render_movie_grid(
                st.session_state["similar_results"],
                cols=6,
                show_like=True,
                show_similar=False,
                section="profile_similar",
            )

        # Because you liked section (randomly selected from user's likes)
        if liked_movies:
            import random
            seed_movie = random.choice(liked_movies)  # Randomly select from liked movies
            if seed_movie and seed_movie.get("movie_id"):
                st.markdown("---")
                st.subheader(f"🎯 Because you liked **{seed_movie.get('title','this movie')}**")
                ok, recs = safe_get(f"{api_base}/similar/{int(seed_movie['movie_id'])}", params={"limit": 12}, timeout=30)
                if ok and isinstance(recs, list) and recs:
                    render_movie_grid(recs, cols=6, show_like=True, show_similar=True, similar_limit=12, section="seed_recs")
                else:
                    st.info("No similar recommendations available right now.")
                    
                # Add a refresh button to get recommendations based on a different liked movie
                if st.button("🔄 Try another movie", key="refresh_seed"):
                    st.rerun()

    else:
        st.info("No liked movies yet. Like some on the Home tab!")

    st.markdown("---")
    st.caption("Tip: display name and bio are stored locally in this app (not in the API).")