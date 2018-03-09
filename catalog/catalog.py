from flask import (Flask, flash, jsonify, make_response, redirect,
                   make_response, render_template, request, url_for)
from flask import session as login_session
from database_setup import Base, Item, User
import random
import string
import httplib2
import json
import requests
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

app = Flask(__name__)

# Connect to DB and create session
engine = create_engine('sqlite:///catalogapp.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Generate state variable and render loginpage with Google signin
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route("/gconnect", methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state token'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data
    # Get credentials object using authorization code
    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('''
                    Failed to upgrade the authorization code'''), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Check for valid token
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # Exit if there is an error
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Check access token is for right user
    gplus_id = credentials.id_token['sub']
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps("Tokens do not match"), 401)
        print "Tokens do not match"
        reponse.headers['Content-Type'] = 'application/json'
        return response
    # Check if user is already logged in
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('User is already connected'), 200)
        response.headers['Content-Type'] = 'application/json'
    # Store token
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()
    login_session['username'] = data['name']
    login_session['email'] = data['email']
    # Check if returning user, else create DB entry
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    output = "Welcome %s!" % login_session['username']
    return output


@app.route("/gdisconnect")
def gdisconnect():
    access_token = login_session.get('credentials')
    # If no token
    if access_token is None:
        response = make_response(json.dumps('No user is connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % \
        login_session['credentials']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    # Delete token
    if result['status'] == '200':
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['user_id']
        response = make_response(json.dumps('Disconnected'), 200)
        response.headers['Content-Type'] = 'application/json'
        flash("Logged out!")
        return redirect(url_for('showCatalog'))
    # Invalid token
    else:
        response = make_response(json_dumps('Failed to revoke token'), 400)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('showCatalog'))


# JSON endpoint for all items
@app.route("/catalog/JSON")
def catalogJSON():
    items = session.query(Item).all()
    return jsonify(items=[i.serialize for i in items])


# JSON endpoint for items in specified category
@app.route("/catalog/<category>/JSON")
def categoryJSON(category):
    category = session.query(Item).filter_by(category=category).all()
    return jsonify(items=[i.serialize for i in category])


# JSON endpoint for single item
@app.route("/catalog/<category>/<item>/JSON")
def itemJSON(category, item):
    item = session.query(Item).filter_by(name=item).one()
    return jsonify(item=item.serialize)


# Default page
@app.route("/")
@app.route("/catalog/")
def showCatalog():
    categories = []
    # Get distinct categories from Item DB
    for item in session.query(Item).distinct(Item.category):
        categories.append(item.category)
    # Redirect to public catalog page if not logged in
    return render_template('catalog.html', categories=categories)


# Category page
@app.route("/catalog/<category>/")
def showCatagory(category):
    items = session.query(Item).filter_by(category=category).all()
    return render_template('category.html', category=category, items=items)


# Item page
@app.route("/catalog/<category>/<item>/")
def showItem(category, item):
    qitem = session.query(Item).filter_by(name=item).one()
    return render_template('item.html', qitem=qitem)


# Add new item
@app.route("/catalog/add/", methods=['GET', 'POST'])
def addItem():
    # Redirect if user is not logged in
    if 'username' not in login_session:
        return redirect('/login')
    # Create item on POST
    if request.method == 'POST':
        newItem = Item(name=request.form['name'],
                       description=request.form['description'],
                       category=request.form['category'],
                       user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash('New item %s successfully created' % (newItem.name))
        return redirect(url_for('showItem', category=request.form['category'],
                                item=request.form['name']))
    else:
        return render_template('additem.html')


# Edit item
@app.route("/catalog/<category>/<item>/edit/", methods=['GET', 'POST'])
def editItem(category, item):
    # Check if user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(Item).filter_by(name=item).one()
    # If user is not the original creator of item redirect to home page
    if editedItem.user_id != login_session['user_id']:
        redirect('/catalog')
    # Edit item and commit it to DB
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['category']:
            editedItem.category = request.form['category']
        session.add(editedItem)
        session.commit()
        flash('Item successfully edited!')
        return redirect(url_for('showItem', category=editedItem.category,
                                item=editedItem.name))
    else:
        return render_template('edititem.html', category=category,
                               item=editedItem)


# Delete Item
@app.route("/catalog/<category>/<item>/delete/", methods=['GET', 'POST'])
def deleteItem(category, item):
    # Check if user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    deletedItem = session.query(Item).filter_by(name=item).one()
    # If user is not original creator redirect to homepage
    if deletedItem.user_id != login_session['user_id']:
        redirect('/catalog')
    # Delete item from DB
    if request.method == 'POST':
        if deletedItem:
            session.delete(deletedItem)
            session.commit()
            flash('Item deleted!')
            return redirect(url_for('showCatalog'))
        else:
            flash('Item does not exist!')
            return redirect(url_for('showCatalog'))
    else:
        return render_template('deleteitem.html', category=category,
                               item=deletedItem)


# Get user ID based on Google email login
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except Exception:
        return None


# Get user DB entry
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user.id).one()
    return user


# Create new user DB entry and return ID
def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
