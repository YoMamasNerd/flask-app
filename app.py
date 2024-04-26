from flask import Flask, render_template, request, url_for, flash, redirect, session
from flask_session import Session
from werkzeug.exceptions import abort
from bson import ObjectId
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_login import login_required
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime
from pytz import timezone
from pymongo import DESCENDING
import fe_klassen as fe
import re
import tools
import os


# LoginManager initialisieren
login_manager = LoginManager()
login_manager.init_app(app)


# User-Model initialisieren
class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(64))
    surname = db.Column(db.String(64))
    admin = db.Column(db.Boolean, default=False)
    owner =  db.Column(db.Boolean, default=False)

    def __init__(self, username, password_hash, name, surname, admin=False, owner=False):
        self.username = username
        self.password_hash = password_hash
        self.name = name
        self.surname = surname
        self.admin = admin
        self.owner = owner


    def __repr__(self):
        return f'<User {self.username}>'


# Function to check if it's currently between sunrise and sunset in Berlin
def is_daytime():
    # Define Berlin's location information
    berlin_location = LocationInfo("Berlin", "Germany", "Europe/Berlin", 52.52, 13.405)  
    # Get current time in Berlin timezone
    berlin_timezone = timezone("Europe/Berlin")
    current_time_berlin = datetime.now(berlin_timezone)
    
    # Calculate sunrise and sunset times for Berlin
    s = sun(berlin_location.observer, date=current_time_berlin, tzinfo=berlin_timezone)

    # Check if current time is between sunrise and sunset in Berlin
    return s['sunrise'] < current_time_berlin < s['sunset']


# Context processor to inject background color into all templates
@app.context_processor
def inject_background_color():
    if current_user.is_anonymous:
        is_day = is_daytime()
        if is_day:
            return {'background_color': 'light'}
        else:
            return {'background_color': 'dark'}
            
    match tools.get_single_conf(current_user.id, 'background_color_option'):
        case 'light':
            return {'background_color': 'light'}
        case 'dark':
            return {'background_color': 'dark'}
        case 'auto':
            is_day = is_daytime()
            if is_day:
                return {'background_color': 'light'}
            else:
                return {'background_color': 'dark'}
        case _:
            is_day = is_daytime()
            if is_day:
                return {'background_color': 'light'}
            else:
                return {'background_color': 'dark'}



# Routes - Manage Page
@app.route('/manage', methods=['GET', 'POST'])
def  manage():
    
    if current_user.is_anonymous:
        return redirect(url_for('login'))
    users = User.query.all()
    tasks = tools.get_all_klassen()
    
    teacher_student_count = dict()
    for user in users:
        conn = tools.get_db_conn()
        count = conn.find({'teacher': str(user.id)})
        teacher_student_count[user.id] = len(list(count))
    
    # get options from db
    conf = tools.get_db_conn('conf')
    conf_user = conf.find_one({'_id': current_user.id})
    
    # if user has no conf create one
    if conf_user is None:
        conf_user = {
            '_id': current_user.id,
            'sorting_option': 'name',
            'background_color_option': 'auto'
        }
        conf.insert_one(conf_user)
    
    if request.method == 'POST':
        
        sorting_option = request.form['sorting_option']
        conf_user['sorting_option'] = sorting_option
        
        background_color_option = request.form['background_color_option']
        conf_user['background_color_option'] = background_color_option
        
        conf.replace_one({'_id': current_user.id}, conf_user)
            
    return render_template('manage.html', users=users, conf=conf_user, tasks=tasks, teacher_student_count=teacher_student_count)



# Routes - Index
@app.route('/', methods=['GET', 'POST'])
def index():
    
    if current_user.is_anonymous:
        return render_template('not_logged_in.html')
        
    conn = tools.get_db_conn()
    if conn is None:
        return render_template('no_mongodb.html')
    
    if User.query.count() == 0:
        return redirect(url_for('register'))
    
    # Determine which tab is active based on the URL parameter
    active_tab = request.args.get('tab', default='my_students')
    
    # set sorting option
    sorting_option = tools.get_single_conf(current_user.id, 'sorting_option')
    # if sorting_option is None set it to 'name'
    if sorting_option is None:
        sorting_option = 'name'
    
    # Get all students assigned to the current user
    if current_user.is_authenticated:
        my_students = conn.find({'teacher': str(current_user.id), 'archived': {'$ne': True}}).sort(sorting_option)
    else:
        my_students = None
    
    # Get all students from the database
    all_students = conn.find().sort(sorting_option)
    
    # Get all archived students
    archive_students = conn.find({'archived': True}).sort(sorting_option)
    
    # Count the number of students in each category
    if current_user.is_authenticated:
        my_students_count = conn.count_documents({'teacher': str(current_user.id), 'archived': {'$ne': True}})
    # Get count of all students from the database
    all_students_count = conn.count_documents({})
    # Get count of all archived students
    archive_students_count = conn.count_documents({'archived': True})
    
    count_list = [my_students_count, all_students_count, archive_students_count]
    
    # Get all users
    users = User.query.all()
    # convert users id to str
    for user in users:
        user.id = str(user.id)
    
    if request.method == 'POST':
        
        search = request.form['searchInput']
        try:
            filter = request.form['klasseSelect']
        except KeyError:
            filter = "all"
        pattern = "^" + search + ".*"
        regex_pattern = re.compile(pattern, re.IGNORECASE)
        
        # My Search
        query_my = {
            '$or': [
                {'name': {'$regex': regex_pattern}},
                {'surname': {'$regex': regex_pattern}},
            ],
            'teacher': str(current_user.id), 
            'archived': {'$ne': True}
        }
        
        # All Search
        query_all = {
            '$or': [
                {'name': {'$regex': regex_pattern}},
                {'surname': {'$regex': regex_pattern}}
            ],
        }
        
        # Archived Search
        query_archived = {
            '$or': [
                {'name': {'$regex': regex_pattern}},
                {'surname': {'$regex': regex_pattern}}
            ],
            'archived': True
        }
        
        all_queries = [query_my, query_all, query_archived]
        for query in all_queries:
            # Add filtering based on "klasse" if it's not "all"
            if filter != "all":
                query['$and'] = [{'klasse': filter}]
        
        # Get all students from the database
        my_students = conn.find(query_my).sort(sorting_option)
        
        all_students = conn.find(query_all).sort(sorting_option)
        
        archive_students = conn.find(query_archived).sort(sorting_option)
        
        # Count the number of students in each category
        my_students_count = conn.count_documents(query_my)
        all_students_count = conn.count_documents(query_all)
        archive_students_count = conn.count_documents(query_archived)
        
        count_list = [my_students_count, all_students_count, archive_students_count]
        
        return render_template('index.html', sorting_option=sorting_option, klassen=tools.get_all_klassen(), count_list=count_list, users=users, my_students=my_students, all_students=all_students, archive_students=archive_students, active_tab=active_tab)        
        
    return render_template('index.html', sorting_option=sorting_option, klassen=tools.get_all_klassen(), count_list=count_list, users=users, my_students=my_students, all_students=all_students, archive_students=archive_students, active_tab=active_tab)