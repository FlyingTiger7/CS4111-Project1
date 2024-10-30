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

@app.route('/topics')
def view_topics():
    with engine.connect() as connection:
        # Query to retrieve topic names from the 'topic' table
        result = connection.execute(text("SELECT topic_name FROM ccr2157.topic"))
        
        # Extract topic names from the result
        topics = [row[0] for row in result]
    
        return render_template('topics.html', topics=topics)

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)