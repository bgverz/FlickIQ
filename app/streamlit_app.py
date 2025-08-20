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
def render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12):
    grid_cols = st.columns(cols)
    for i, m in enumerate(movies):
        with grid_cols[i % cols]:
            st.image(m.get("poster_path"), caption=m.get("title", "Untitled"), use_container_width=True)
            if m.get("year"):
                st.caption(f"{m['year']}")
            # Always create two subcolumns; ignore the one we don't need
            b1, b2 = st.columns(2)
            if show_like:
                with b1:
                    if st.button(f"👍 Like #{m['movie_id']}", key=f"like_{m['movie_id']}"):
                        payload = {"user_id": int(user_id), "movie_id": int(m["movie_id"]), "interaction_type": "like"}
                        rr = requests.post(f"{api_base}/interactions", json=payload, timeout=15)
                        st.success("Saved!" if rr.ok else rr.text)
            if show_similar:
                with b2:
                    if st.button("🎯 Similar", key=f"sim_{m['movie_id']}"):
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
            render_movie_grid(movies, cols=4, show_like=True, show_similar=True, similar_limit=12)
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
            render_movie_grid(items, cols=5, show_like=True, show_similar=True, similar_limit=12)
        else:
            st.info("No recommendations yet. Try liking a few movies first.")
    else:
        st.error(r.text)
