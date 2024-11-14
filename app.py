import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, flash, request, render_template, g, redirect, Response, url_for, session, jsonify
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = 'your_secret_key'

### Database credentials
DB_USER = "ccr2157"
DB_PASSWORD = "ccr2157"
DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.comw/w4111"
DATABASEURI = "postgresql://ccr2157:ccr2157@w4111.cisxo09blonu.us-east-1.rds.amazonaws.com/w4111"

engine = create_engine(DATABASEURI)

# Login management setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self,email,priv):
        self.email = email
        self.priv = priv
    
        
        

    def get_id(self):
        return str(self.email)


@login_manager.user_loader
def load_user(email):
    result = g.conn.execute(
        text("SELECT email,privileges as priv FROM ccr2157.app_user WHERE email = :email"),
        {"email": email}
    )
    
    user_row = result.fetchone()
    if user_row:
        return User(user_row.email,user_row.priv)
    return None     

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        session.pop('_flashes', None)

        result = g.conn.execute(
            text("SELECT email, password FROM ccr2157.app_user WHERE email = :email"),
            {"email": email}
        )
        user_row = result.fetchone()

        if user_row and user_row[1] == password:
            user = User(user_row[0],null)
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html', topics=g.topics)

@app.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('home'))

@app.before_request
def before_request():
    # Open database connection
    g.conn = engine.connect()
    
    # Get topics for navigation
    result = g.conn.execute(text("SELECT topic_name FROM ccr2157.topic"))
    g.topics = [row[0] for row in result]
    
    # Get followers if user is authenticated
    if current_user.is_authenticated:
        result = g.conn.execute(
            text("SELECT sub.followed_email FROM ccr2157.follow sub WHERE sub.follower_email = :email"),
            {"email": current_user.get_id()}
        )
        g.followers = [row[0] for row in result]

        result = g.conn.execute(
            text("SELECT event_id FROM ccr2157.event_attendence sub WHERE email = :email"),
            {"email": current_user.get_id()}
        )
        g.event_attendence = [row[0] for row in result]


    else:
        g.followers = []
        g.event_attendence = []

    
    
    

@app.teardown_request
def teardown_request(exception):
    try:
        if g.conn:
            g.conn.close()
    except Exception as e:
        print(f"Error closing connection: {e}")

@app.route('/topic/<topic_name>')
def view_topic(topic_name):
    # Get topic info
    result = g.conn.execute(
        text("SELECT topic_name FROM ccr2157.topic WHERE topic_name = :name"),
        {"name": topic_name}
    )
    topic = result.fetchone()

    if topic is None:
        return "Topic not found", 404

    # Get threads for this topic with like counts
    result = g.conn.execute(
        text(""" 
            SELECT thread.thread_id, thread.title, thread.body, thread.timestamp, 
                   creates.email as email, COALESCE(thread_like_count.like_count, 0) as like_count 
            FROM ccr2157.part_of pf 
            JOIN ccr2157.thread thread ON thread.thread_id = pf.thread_id
            JOIN ccr2157.topic topic ON pf.topic_id = topic.topic_id
            JOIN ccr2157.creates creates ON creates.thread_id = thread.thread_id
            LEFT JOIN (
                SELECT r.thread_id, COUNT(*) as like_count
                FROM ccr2157.reply r
                JOIN ccr2157.likes_has lh ON lh.comment_id = r.comment_id
                GROUP BY r.thread_id
            ) as thread_like_count ON thread_like_count.thread_id = thread.thread_id
            WHERE topic.topic_name = :name
        """),
        {"name": topic_name}
    )
    topic_threads = result.fetchall()

    # Check subscription status
    is_subscribed = False
    if current_user.is_authenticated:
        result = g.conn.execute(
            text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
            {"topic_name": topic_name}
        )
        topic = result.fetchone()

        if topic:
            subscription = g.conn.execute(
                text("SELECT 1 FROM ccr2157.subscribe WHERE email = :email AND topic_id = :topic_id"),
                {"email": current_user.get_id(), "topic_id": topic[0]}
            ).fetchone()
            is_subscribed = subscription is not None

    return render_template(
        'topic.html',
        topic_threads=topic_threads,
        topics=g.topics,
        topic_name=topic_name,
        is_subscribed=is_subscribed,
    )

@app.route('/subscribe/<string:topic_name>', methods=['POST'])
def subscribe(topic_name):
    # Retrieve the topic_id based on the topic_name
    result = g.conn.execute(
        text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
        {"topic_name": topic_name}
    )
    topic = result.fetchone()
    if topic:
        topic_id = topic[0]
        # Find the subscription record
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


@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
def view_thread(thread_id):
    if request.method == 'POST' and current_user.is_authenticated:
        comment_text = request.form.get('comment')
        
        if not comment_text:
            flash('Comment cannot be empty', 'error')
            return redirect(url_for('view_thread', thread_id=thread_id))

        try:
            # Get next comment_id
            result = g.conn.execute(text("SELECT MAX(comment_id) FROM ccr2157.comment"))
            next_id = (result.scalar() or 0) + 1

            # Insert comment
            g.conn.execute(
                text("""
                INSERT INTO ccr2157.comment (comment_id, comment, timestamp)
                VALUES (:comment_id, :comment, CURRENT_DATE)
                """),
                {"comment_id": next_id, "comment": comment_text}
            )

            # Create reply connection
            g.conn.execute(
                text("""
                INSERT INTO ccr2157.reply (comment_id, email, thread_id)
                VALUES (:comment_id, :email, :thread_id)
                """),
                {
                    "comment_id": next_id,
                    "email": current_user.email,
                    "thread_id": str(thread_id)
                }
            )

            g.conn.execute(text("COMMIT;"))
            flash('Comment added successfully', 'success')
            
        except Exception as e:
            print(f"Error adding comment: {str(e)}")
            flash(f'Error adding comment: {str(e)}', 'error')
            
        return redirect(url_for('view_thread', thread_id=thread_id))

    # Get thread details
    thread_result = g.conn.execute(
        text("""
        SELECT thread.thread_id, thread.title, thread.body, thread.timestamp, creates.email as author
        FROM ccr2157.thread thread
        JOIN ccr2157.creates creates ON creates.thread_id = thread.thread_id
        WHERE thread.thread_id = :thread_id
        """),
        {"thread_id": thread_id}
    )
    thread = thread_result.fetchone()
    
    if thread is None:
        return "Thread not found", 404

    # Get comments with user info and like counts
    comments_result = g.conn.execute(
        text("""
        SELECT 
            comment.comment_id,
            comment.comment,
            comment.timestamp,
            reply.email as commenter,
            COALESCE(like_counts.like_count, 0) as like_count
        FROM ccr2157.comment comment
        JOIN ccr2157.reply reply ON reply.comment_id = comment.comment_id
        LEFT JOIN (
            SELECT comment_id, COUNT(*) as like_count
            FROM ccr2157.likes_has
            GROUP BY comment_id
        ) like_counts ON like_counts.comment_id = comment.comment_id
        WHERE reply.thread_id = :thread_id
        ORDER BY comment.timestamp DESC
        """),
        {"thread_id": thread_id}
    )
    comments = comments_result.fetchall()

    return render_template(
        "thread.html",
        thread=thread,
        comments=comments,
        topics=g.topics,
        followed=g.followers
        
    )

@app.route('/thread/<int:thread_id>/<comment_id>/delete/<email>', methods=['POST'])
def delete_comment(comment_id, thread_id, email):

    if(current_user.priv == 1 or current_user.email == email):
        g.conn.execute(text("""DELETE FROM ccr2157.reply WHERE comment_id =:comment_id AND
                            thread_id =:thread_id and email =:email"""),
                            {"comment_id": comment_id,
                            "thread_id": thread_id,
                            "email": email})
        g.conn.commit() 

        g.conn.execute(text("DELETE FROM ccr2157.comment WHERE comment_id =:comment_id"),{"comment_id": comment_id})
        g.conn.commit()

        flash("Comment by "+email+" has been deleted")
    
    else:
        flash("You can't delete this user's comment!")
    
    
    return redirect(request.referrer)


@app.route('/like_comment/<int:comment_id>>', methods=['GET','POST'])
@login_required
def like_comment(comment_id):
    existing_like = g.conn.execute(
            text("SELECT * FROM ccr2157.likes_has WHERE email=:email and comment_id=:comment_id"),
            {"comment_id": comment_id, "email": current_user.email}
        ).fetchone()
    
    like_exists = existing_like is not None

    if like_exists:
        g.conn.execute(
            text("DELETE FROM ccr2157.likes_has WHERE email=:email and comment_id=:comment_id"),
            {"comment_id": comment_id, "email": current_user.email})
        g.conn.commit() 
    
    else:
        g.conn.execute(
            text("INSERT INTO ccr2157.likes_has(email,comment_id) VALUES (:email,:comment_id) "),
            {"comment_id": comment_id, "email": current_user.email})
        g.conn.commit() 

    return redirect(request.referrer)
    
@app.route('/topic/<topic_name>/create_thread', methods=['GET', 'POST'])
@login_required
def create_thread(topic_name):
    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        
        if not all([title, body]):
            flash('Please fill in all fields', 'error')
            return redirect(url_for('create_thread', topic_name=topic_name))
            
        try:
            # Get the topic_id
            topic_result = g.conn.execute(
                text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
                {"topic_name": topic_name}
            )
            topic_id = topic_result.fetchone()
            
            if not topic_id:
                flash('Invalid topic', 'error')
                return redirect(url_for('view_topic', topic_name=topic_name))
                
            topic_id = topic_id[0]
            
            # Get next thread_id
            result = g.conn.execute(text("SELECT COALESCE(MAX(thread_id), 0) + 1 FROM ccr2157.thread"))
            next_thread_id = result.scalar()
            
            # Begin transaction
            g.conn.execute(text("BEGIN"))
            
            # Insert thread
            g.conn.execute(
                text("""
                    INSERT INTO ccr2157.thread (thread_id, title, body, timestamp)
                    VALUES (:thread_id, :title, :body, CURRENT_DATE)
                """),
                {
                    "thread_id": next_thread_id,
                    "title": title,
                    "body": body
                }
            )
            
            # Create thread-user relationship
            g.conn.execute(
                text("""
                    INSERT INTO ccr2157.creates (thread_id, email)
                    VALUES (:thread_id, :email)
                """),
                {
                    "thread_id": next_thread_id,
                    "email": current_user.email
                }
            )
            
            # Create thread-topic relationship
            g.conn.execute(
                text("""
                    INSERT INTO ccr2157.part_of (thread_id, topic_id)
                    VALUES (:thread_id, :topic_id)
                """),
                {
                    "thread_id": next_thread_id,
                    "topic_id": topic_id
                }
            )
            
            # Commit transaction
            g.conn.execute(text("COMMIT"))
            
            flash('Thread created successfully!', 'success')
            return redirect(url_for('view_thread', topic_name=topic_name, thread_id=next_thread_id))
            
        except Exception as e:
            g.conn.execute(text("ROLLBACK"))
            print(f"Error creating thread: {str(e)}")
            flash(f'Error creating thread: {str(e)}', 'error')
            return redirect(url_for('create_thread', topic_name=topic_name))
            
    return render_template('create_thread.html', topic_name=topic_name, topics=g.topics)

@app.route('/')
@app.route('/home')
def home():
    if current_user.is_authenticated:
        result = g.conn.execute(text("""
            WITH top_liked_threads AS (
                SELECT thread.thread_id, count(lh.comment_id) as like_count
                FROM ccr2157.comment comment
                LEFT JOIN ccr2157.likes_has lh ON lh.comment_id = comment.comment_id
                JOIN ccr2157.reply reply ON comment.comment_id = reply.comment_id
                RIGHT JOIN ccr2157.thread thread ON reply.thread_id = thread.thread_id
                GROUP BY thread.thread_id
               
            )
            SELECT tls.thread_id thread_id, tls.like_count, title, body, timestamp, creates.email
            FROM ccr2157.subscribe sub 
            JOIN ccr2157.part_of ON sub.topic_id = part_of.topic_id
            JOIN top_liked_threads tls ON part_of.thread_id = tls.thread_id
            JOIN ccr2157.thread thread ON thread.thread_id = tls.thread_id
            JOIN ccr2157.creates creates ON creates.thread_id = tls.thread_id 
            WHERE sub.email = :email
            ORDER BY like_count DESC
            LIMIT 3
        """),
        {"email": current_user.get_id()})

        events = g.conn.execute(text("""SELECT e.event_id, e.title, e.capacity, e.timestamp,
                   e.email as creator_email, t.topic_name, count(ea.event_id) as count
            FROM ccr2157.event_created_by e
            JOIN ccr2157.under u ON e.event_id = u.event_id 
                AND e.email = u.app_user_email
            JOIN ccr2157.topic t ON u.topic_id = t.topic_id
            LEFT JOIN ccr2157.event_attendence ea ON ea.event_id = e.event_id
            JOIN ccr2157.follow f ON e.email = f.followed_email
            WHERE f.follower_email =:email
            GROUP BY e.event_id, e.title, e.capacity, e.timestamp,
                  creator_email, t.topic_name
            ORDER BY count DESC
            """),{"email":current_user.email}

)




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
            SELECT tlc.like_count, thread.title, thread.body, thread.timestamp, creates.email, tlc.thread_id
            FROM top_liked_comment tlc
            JOIN ccr2157.thread thread ON tlc.thread_id = thread.thread_id
            JOIN ccr2157.creates creates ON creates.thread_id = tlc.thread_id
        """))

        events = g.conn.execute(text("""SELECT e.event_id, e.title, e.capacity, e.timestamp,
                   e.email as creator_email, t.topic_name, count(ea.event_id) as count
            FROM ccr2157.event_created_by e
            JOIN ccr2157.under u ON e.event_id = u.event_id 
                AND e.email = u.app_user_email
            JOIN ccr2157.topic t ON u.topic_id = t.topic_id
            LEFT JOIN ccr2157.event_attendence ea ON ea.event_id = e.event_id
            JOIN ccr2157.follow f ON e.email = f.followed_email

            GROUP BY e.event_id, e.title, e.capacity, e.timestamp,
                  creator_email, t.topic_name
            ORDER BY count DESC
            LIMIT 3
            """))
        
    top_threads = result.fetchall()
    top_events = events.fetchall()
    return render_template('home.html', 
                           topics=g.topics, 
                           top_threads=top_threads, 
                           top_events=top_events,
                           attend=g.event_attendence
                           )

@app.route('/follow/<string:followed_email>', methods=['POST'])
@login_required
def follow(followed_email):
    follow_status = g.conn.execute(
        text("SELECT * FROM ccr2157.follow WHERE follower_email = :user_email AND followed_email = :followed_email"),
        {"user_email": current_user.get_id(), "followed_email": followed_email}
    ).fetchone()
    
    if follow_status is None:
        g.conn.execute(
            text("INSERT INTO ccr2157.follow(follower_email, followed_email) VALUES (:user_email, :followed_email)"),
            {"user_email": current_user.get_id(), "followed_email": followed_email}
        )
        g.conn.commit()
        flash("You are now following: " + followed_email)
    else:
        g.conn.execute(
            text("DELETE FROM ccr2157.follow WHERE follower_email = :user_email and followed_email = :followed_email"),
            {"user_email": current_user.get_id(), "followed_email": followed_email}
        )
        g.conn.commit()
        flash("You have unfollowed: " + followed_email)
    return redirect(request.referrer)

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        title = request.form.get('title')
        capacity = request.form.get('capacity')
        topic_name = request.form.get('topic')
        
        if not all([title, capacity, topic_name]):
            flash('Please fill in all fields', 'error')
            return redirect(url_for('create_event'))
            
        try:
            # Get the topic_id for the selected topic
            topic_result = g.conn.execute(
                text("SELECT topic_id FROM ccr2157.topic WHERE topic_name = :topic_name"),
                {"topic_name": topic_name}
            )
            topic_id = topic_result.fetchone()
            
            if not topic_id:
                flash('Invalid topic selected', 'error')
                return redirect(url_for('create_event'))
                
            topic_id = topic_id[0]
            
            # Get the next event_id
            event_id_result = g.conn.execute(
                text("SELECT COALESCE(MAX(event_id), 0) + 1 FROM ccr2157.event_created_by")
            )
            next_event_id = event_id_result.scalar()
            
            # Begin transaction
            g.conn.execute(text("START TRANSACTION"))
            
            # Insert into event_created_by table
            g.conn.execute(
                text("""
                    INSERT INTO ccr2157.event_created_by 
                    (email, title, event_id, capacity, timestamp) 
                    VALUES (:email, :title, :event_id, :capacity, CURRENT_DATE)
                """),
                {
                    "email": current_user.email,
                    "title": title,
                    "event_id": next_event_id,
                    "capacity": int(capacity)
                }
            )
            
            # Insert into under table
            g.conn.execute(
                text("""
                    INSERT INTO ccr2157.under 
                    (event_id, app_user_email, topic_id) 
                    VALUES (:event_id, :email, :topic_id)
                """),
                {
                    "event_id": next_event_id,
                    "email": current_user.email,
                    "topic_id": topic_id
                }
            )
            
            # Commit the transaction
            g.conn.execute(text("COMMIT"))
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('view_events'))
            
        except Exception as e:
            # Rollback on error
            g.conn.execute(text("ROLLBACK"))
            print(f"Error creating event: {str(e)}")
            flash(f'Error creating event: {str(e)}', 'error')
            return redirect(url_for('create_event'))
            
    return render_template('create_event.html', topics=g.topics)

@app.route('/events')
def view_events():
    # Query to get all events with their topics and creator info
    result = g.conn.execute(
        text("""
            SELECT e.event_id, e.title, e.capacity, e.timestamp, 
                   e.email as creator_email, t.topic_name
            FROM ccr2157.event_created_by e
            JOIN ccr2157.under u ON e.event_id = u.event_id 
                AND e.email = u.app_user_email
            JOIN ccr2157.topic t ON u.topic_id = t.topic_id
            ORDER BY e.timestamp DESC
        """)
    )
    events = result.fetchall()
    return render_template('events.html', events=events, topics=g.topics)




# Add this route to app.py after the view_topic route
@app.route('/topic/<topic_name>/events')
def view_topic_events(topic_name):
    # Query to get events for a specific topic
    result = g.conn.execute(
        text("""
            SELECT e.event_id, e.title, e.capacity, e.timestamp,
                   e.email as creator_email, t.topic_name, count(ea.event_id) as event_attendence
            FROM ccr2157.event_created_by e
            JOIN ccr2157.under u ON e.event_id = u.event_id 
                AND e.email = u.app_user_email
            JOIN ccr2157.topic t ON u.topic_id = t.topic_id
            LEFT JOIN ccr2157.event_attendence ea on e.event_id = ea.event_id
            WHERE t.topic_name = :topic_name
            GROUP BY e.event_id, e.title, e.capacity, e.timestamp,
                   creator_email, t.topic_name
            ORDER BY e.timestamp DESC
        """),
        {"topic_name": topic_name}
    )
    events = result.fetchall()

    
    return render_template(
        'topic_events.html',
        topic_name=topic_name,
        events=events,
        topics=g.topics,
        attend=g.event_attendence
    )

@app.route('/<event_id>/attend', methods=['GET', 'POST'])
@login_required
def attend_event(event_id):
    existing_attendence = g.conn.execute(
            text("SELECT * FROM ccr2157.event_attendence WHERE email=:email and event_id=:event_id"),
            {"email": current_user.email, "event_id": event_id}
        ).fetchone()

    is_attending = existing_attendence is not None
    
    if is_attending:
        g.conn.execute(
            text("DELETE FROM ccr2157.event_attendence WHERE email=:email and event_id=:event_id"),
            {"email": current_user.email, "event_id": event_id})
        g.conn.commit() 
        flash("You are not attending this event anymore.")
    
    else:
        g.conn.execute(text("INSERT INTO ccr2157.event_attendence(email,event_id) Values(:email,:event_id)"),
        {"email": current_user.email, "event_id": event_id})
        g.conn.commit() 
        flash("You are attending this event.")
       
        
    return redirect(request.referrer)

if __name__ == '__main__':
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using

            python server.py

        Show the help text using

            python server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


run()