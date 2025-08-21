import os
import requests
import streamlit as st

DEFAULT_API = os.environ.get("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")
st.title("🎬 Movie Recommender")

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    api_base = st.text_input("API base URL", value=DEFAULT_API)
    user_id = st.number_input("Active user ID", min_value=1, value=1001, step=1)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ensure User"):
            r = requests.post(f"{api_base}/users", json={"user_id": int(user_id)}, timeout=15)
            st.success(r.json() if r.ok else r.text)
    with c2:
        if st.button("View Interactions"):
            r = requests.get(f"{api_base}/interactions/{int(user_id)}", params={"limit": 50}, timeout=15)
            st.json(r.json() if r.ok else r.text)

st.markdown("---")

# --- Session state for "Similar" ---
if "similar_results" not in st.session_state:
    st.session_state["similar_results"] = []
if "similar_title" not in st.session_state:
    st.session_state["similar_title"] = ""

# --- Grid renderer ---
def render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="default"):
    grid_cols = st.columns(cols)
    for i, m in enumerate(movies):
        with grid_cols[i % cols]:
            st.image(m.get("poster_path"), caption=m.get("title", "Untitled"), width=300)
            if m.get("year"):
                st.caption(f"{m['year']}")
            # Always create two subcolumns; ignore the one we don't need
            b1, b2 = st.columns(2)
            if show_like:
                with b1:
                    if st.button(f"👍 Like #{m['movie_id']}", key=f"{section}_like_{m['movie_id']}"):
                        payload = {"user_id": int(user_id), "movie_id": int(m["movie_id"]), "interaction_type": "like"}
                        rr = requests.post(f"{api_base}/interactions", json=payload, timeout=15)
                        st.success("Saved!" if rr.ok else rr.text)
            if show_similar:
                with b2:
                    if st.button("🎯 Similar", key=f"{section}_sim_{m['movie_id']}"):
                        resp = requests.get(
                            f"{api_base}/similar/{int(m['movie_id'])}",
                            params={"limit": int(similar_limit)},
                            timeout=30,
                        )
                        if resp.ok:
                            st.session_state["similar_results"] = resp.json()
                            st.session_state["similar_title"] = m.get("title", "")
                        else:
                            st.warning(resp.text)
            if m.get("overview"):
                text = m["overview"]
                st.write(text[:220] + ("..." if len(text) > 220 else ""))
            st.write("---")

# --- Search & like ---
st.subheader("🔎 Search movies and 👍 like them")
q = st.text_input("Search by title", placeholder="e.g., Inception")
if q:
    r = requests.get(f"{api_base}/movies/search", params={"q": q, "limit": 16}, timeout=30)
    if r.ok:
        movies = r.json()
        if movies:
            render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="search")
        else:
            st.info("No results.")
    else:
        st.error(r.text)

# --- Similar to selected ---
if st.session_state["similar_results"]:
    st.subheader(f"🎯 Similar to: {st.session_state['similar_title']}")
    render_movie_grid(
        st.session_state["similar_results"],
        cols=6,                # dense layout for more results
        show_like=True,
        show_similar=False,    # avoid nesting Similar buttons
        section="similar"
    )

st.markdown("---")

# --- User-based recommendations ---
st.subheader("👤 Recommendations for the active user")
k = st.slider("How many results?", 1, 30, 10)
if st.button("Get Recommendations"):
    r = requests.get(f"{api_base}/recommendations/{int(user_id)}", params={"limit": int(k)}, timeout=30)
    if r.ok:
        items = r.json().get("items", [])
        if items:
            render_movie_grid(items, cols=5, show_like=True, show_similar=True, similar_limit=12, section="recommendations")
        else:
            st.info("No recommendations yet. Try liking a few movies first.")
    else:
        st.error(r.text)

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
        params["year_min"] = 2010
        params["year_max"] = 2019
    elif year_filter == "2000-2009":
        params["year_min"] = 2000
        params["year_max"] = 2009
    elif year_filter == "1990-1999":
        params["year_min"] = 1990
        params["year_max"] = 1999
    
    r = requests.get(f"{api_base}/movies", params=params, timeout=30)
    if r.ok:
        movies = r.json()
        if movies:
            render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12, section="browse")
        else:
            st.info("No movies found with those filters.")
    else:
        st.error(r.text)