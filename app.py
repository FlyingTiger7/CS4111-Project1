import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

app = Flask(__name__)


DB_USER = "ah4100"
DB_PASSWORD = "03220322"

DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"

DATABASEURI = "postgresql://"+DB_USER+":"+DB_PASSWORD+"@"+DB_SERVER+"/proj1part2"

engine = create_engine(DATABASEURI)



@app.route('/tables')
def list_tables():
    with engine.connect() as connection:
        # Query to list tables owned by ah4100
        result = connection.execute(text("""
            SELECT tablename 
            FROM pg_catalog.pg_tables 
            WHERE tableowner = 'ah4100'
        """))
        tables = [row['tablename'] for row in result]

    return render_template('tables.html', tables=tables)

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)