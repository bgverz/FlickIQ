import os
import psycopg2
import streamlit as st


DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


st.set_page_config(page_title="Movie Recommender", layout="wide")
st.title("🎬 Movie Recommender")

user_id = st.number_input("User ID", min_value=1, value=1, step=1)
limit = st.slider("How many recommendations?", min_value=1, max_value=50, value=10)

if st.button("Get Recommendations"):
    if not DATABASE_URL:
        st.error("DATABASE_URL is not set")
    else:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.title, m.year, m.poster_path, m.overview
                FROM (
                    SELECT movie_id
                    FROM item_embeddings ie
                    JOIN (SELECT embedding FROM user_embeddings WHERE user_id = %s) ue ON true
                    WHERE ie.movie_id NOT IN (SELECT movie_id FROM interactions WHERE user_id = %s)
                    ORDER BY (1 - (ie.embedding <#> ue.embedding)) DESC
                    LIMIT %s
                ) recs
                JOIN movies m ON m.movie_id = recs.movie_id
                """,
                (user_id, user_id, limit),
            )
            rows = cur.fetchall()
            cols = st.columns(5)
            for idx, (title, year, poster, overview) in enumerate(rows):
                with cols[idx % 5]:
                    if poster:
                        st.image(f"https://image.tmdb.org/t/p/w342{poster}", use_column_width=True)
                    st.markdown(f"**{title}** ({year or 'N/A'})")
                    if overview:
                        st.caption(overview[:160] + ("…" if len(overview) > 160 else ""))


