import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

app = Flask(__name__)


DB_USER = "ccr2157"
DB_PASSWORD = "ccr2157"

DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.comw/w4111"

DATABASEURI = "postgresql://ccr2157:ccr2157@w4111.cisxo09blonu.us-east-1.rds.amazonaws.com/w4111"

engine = create_engine(DATABASEURI)



@app.before_request
def before_request():
    # Open a database connection at the start of each request
    g.conn = engine.connect()
    result = g.conn.execute(text("SELECT topic_name FROM ccr2157.topic"))

        
        # Extract topic names from the result
    g.topics = [row[0] for row in result]

@app.teardown_request
def teardown_request(exception):
    # Close the database connection at the end of each request
    try:
        if g.conn:
            g.conn.close()
    except Exception as e:
        print(f"Error closing connection: {e}")

@app.route('/topic/<topic_name>')
def view_topic(topic_name):
    result = g.conn.execute(
        text("SELECT topic_name FROM ccr2157.topic WHERE topic_name = :name"),
        {"name": topic_name}
    )
    topic = result.fetchone()

    if topic is None:
        return "Topic not found", 404

    return render_template('topic.html', topic=topic,topics=g.topics)

@app.route('/')
def home():
      
    result = g.conn.execute(text("""
        WITH top_liked_comment AS (
      SELECT r.thread_id AS thread_id, COUNT(*) AS like_count
      FROM ccr2157.reply r
      JOIN ccr2157.likes_has lh ON lh.comment_id = r.comment_id
      GROUP BY r.thread_id
      ORDER BY like_count DESC
      LIMIT 3
        )
        SELECT tlc.like_count, thread.title, thread.body, thread.timestamp, creates.email
        FROM top_liked_comment tlc
        JOIN ccr2157.thread thread ON tlc.thread_id = thread.thread_id
        JOIN ccr2157.creates creates ON creates.thread_id = tlc.thread_id;
        """))
    top_threads = result.fetchall()  # Fetch all top threads

    return render_template('home.html', topics=g.topics,top_threads=top_threads)

if __name__ == '__main__':
    app.run(debug=True)