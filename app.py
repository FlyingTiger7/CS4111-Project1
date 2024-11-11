import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, flash, request, render_template, g, redirect, Response, url_for,session
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# secret_key below is needed for login authentication, blackbox under the covers done by flask

app = Flask(__name__)
app.secret_key = 'your_secret_key'

### database credentials

DB_USER = "ccr2157"
DB_PASSWORD = "ccr2157"
DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.comw/w4111"
DATABASEURI = "postgresql://ccr2157:ccr2157@w4111.cisxo09blonu.us-east-1.rds.amazonaws.com/w4111"

engine = create_engine(DATABASEURI)
##OUR LOGIN ENGINE - keeps track of user that is logged in and makes a huge difference in terms of functionality.######################################################################################################
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, email):
        self.email = email

    def get_id(self):
        return str(self.email)

@login_manager.user_loader
def load_user(email):
    # Query to load user based on email
    result = g.conn.execute(
        text("SELECT email FROM ccr2157.app_user WHERE email = :email"),
        {"email": email}
    )
    user_row = result.fetchone()
    if user_row:
        return User(user_row.email)
    return None     

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        session.pop('_flashes', None)


        # Query the database for the user's credentials
        result = g.conn.execute(
            text("SELECT email, password FROM ccr2157.app_user WHERE email = :email"),
            {"email": email}
        )
    
        user_row = result.fetchone()

        if user_row and user_row[1] == password:
            user = User(user_row[0])
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))  # Redirect to dashboard or home page
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html',topics =g.topics)

@app.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('home'))
#########################################################################################################################################
@app.before_request
def before_request():

    # Open a database connection at the start of each request
    g.conn = engine.connect()
    result = g.conn.execute(text("SELECT topic_name FROM ccr2157.topic"))

        
        # Extract topic names from the result
    g.topics = [row[0] for row in result]

    if current_user.is_authenticated:
        result = g.conn.execute(text("SELECT sub.followed_email FROM ccr2157.follow sub WHERE sub.follower_email =:email"),{"email":current_user.get_id()})
    g.followers = [row[0] for row in result]
    print(g.followers)
    


@app.teardown_request
def teardown_request(exception):
    # Close the database connection at the end of each request
    try:
        if g.conn:
            g.conn.close()
    except Exception as e:
        print(f"Error closing connection: {e}")


### dynamically renders all threads associated with said topic
@app.route('/topic/<topic_name>')
def view_topic(topic_name):
    result = g.conn.execute(
        text("SELECT topic_name FROM ccr2157.topic WHERE topic_name = :name"),
        {"name": topic_name}
    )
    topic = result.fetchone()

    if topic is None:
        return "Topic not found", 404

    result = g.conn.execute(
        text(""" SELECT title,body,timestamp,email,like_count from ccr2157.part_of pf 
                 join ccr2157.thread thread on thread.thread_id = pf.thread_id
                 join ccr2157.topic topic on pf.topic_id = topic.topic_id
                 join ccr2157.creates creates on creates.thread_id = thread.thread_id
                 join (SELECT r.thread_id AS thread_id, COUNT(*) AS like_count
                      FROM ccr2157.reply r
                      JOIN ccr2157.likes_has lh ON lh.comment_id = r.comment_id
                      GROUP BY r.thread_id) as thread_like_count 
                 ON thread_like_count.thread_id = thread.thread_id

                 WHERE topic.topic_name = :name"""),
                 {"name": topic_name}
            )   
        
    topic_threads = result.fetchall()

    is_subscribed = False

    if current_user.is_authenticated:
        result = g.conn.execute(
        text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
        {"topic_name": topic_name}
        )
        topic = result.fetchone()

        subscription = g.conn.execute(
            text("SELECT 1 FROM ccr2157.subscribe WHERE email = :email AND topic_id = :topic_id"),
            {"email": current_user.get_id(), "topic_id": topic[0]}
        ).fetchone()
        is_subscribed = subscription is not None
    
    return render_template('topic.html', topic_threads=topic_threads,topics=g.topics,topic_name=topic_name,is_subscribed=is_subscribed,followed=g.followers)

@app.route('/topic/<topic_name>/thread/<thread_title>')
def view_thread(thread_title,topic_name):

    result = g.conn.execute("Select * from ccr2157.thread thread where thread.title = thread_title")

    return render_template("thread.html",thread_title = thread_title,tp=topic_name,topics=g.topics)
    




#/ and home will both route to the same default page/main page
@app.route('/')
@app.route('/home')
def home():

    if current_user.is_authenticated:
        result = g.conn.execute(text("""
        WITH top_liked_threads AS (select thread_id, count(*) like_count from ccr2157.likes_has lh 
                join ccr2157.comment comment ON lh.comment_id = comment.comment_id
        join ccr2157.reply reply ON comment.comment_id = reply.comment_id
        GROUP BY reply.thread_id)

        Select tls.like_count,title,body,timestamp,creates.email
        FROM ccr2157.subscribe sub JOIN ccr2157.part_of ON sub.topic_id = part_of.topic_id
        JOIN top_liked_threads tls ON part_of.thread_id = tls.thread_id
        JOIN ccr2157.thread thread ON thread.thread_id = tls.thread_id
        JOIN ccr2157.creates creates on creates.thread_id = tls.thread_id 
        WHERE sub.email = :email
        ORDER BY like_count DESC
        LIMIT 3"""),
        {"email": current_user.get_id()})
  


    else: 
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





#### handling subcriptions to topics
@app.route('/subscribe/<string:topic_name>', methods=['POST'])
@login_required
def subscribe_to_topic(topic_name):
    # Retrieve the topic_id based on the topic_name
    result = g.conn.execute(
        text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
        {"topic_name": topic_name}
    )
    topic = result.fetchone()

    if topic:
        topic_id = topic[0]
        # Insert the subscription record into the subscriptions table 

        existing_subscription = g.conn.execute(
            text("SELECT * FROM ccr2157.subscribe WHERE email = :email AND topic_id = :topic_id"),
            {"email": current_user.get_id(), "topic_id": topic_id}
        ).fetchone()
        
        is_subscribed = existing_subscription is not None

        if existing_subscription:
            # User is already subscribed
            g.conn.execute(
            text("DELETE FROM ccr2157.subscribe WHERE email = :email AND topic_id = :topic_id"),
            {"email": current_user.get_id(), "topic_id": topic_id}
            )

            g.conn.commit() 

            flash("You have unsubscribed from this topic.")

        else:
            g.conn.execute(
                text("INSERT INTO ccr2157.subscribe (email, topic_id) VALUES (:user_id, :topic_id)"),
                {"user_id": current_user.get_id(), "topic_id": topic_id})
            g.conn.commit() 
        
            flash(f"You have subscribed to {topic_name}")
    else:
        flash("Topic not found.")

    # Redirect back to the topic page
    return redirect(request.referrer)


###follow/following
@app.route('/follow/<string:followed_email>', methods=['POST'])
@login_required
def follow(followed_email):
    
    follow_status = g.conn.execute(
            text("SELECT * FROM ccr2157.follow WHERE follower_email = :user_email AND followed_email =:followed_email"),
            {"user_email": current_user.get_id(), "followed_email": followed_email}
        ).fetchone()
    
    if follow_status is None:
        g.conn.execute(
                text("INSERT INTO ccr2157.follow(follower_email, followed_email) VALUES (:user_email, :followed_email)"),
                {"user_email": current_user.get_id(), "followed_email": followed_email})
        g.conn.commit() 
        flash("You are now following:"+(followed_email))

    else:
        g.conn.execute(
                text("DELETE FROM ccr2157.follow WHERE follower_email = :user_email and followed_email = :followed_email"),
                {"user_email": current_user.get_id(), "followed_email": followed_email})
        g.conn.commit() 
        flash("You have unfollowed:"+(followed_email))
    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(debug=True)