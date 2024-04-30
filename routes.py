#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Keskusteluforum

Copyright (C) 2024  Markus Ottela

This file is part of Keskusteluforum.

Keskusteluforum is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Keskusteluforum is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Keskusteluforum. If not, see <https://www.gnu.org/licenses/>.
"""

from os import getrandom

import argon2
import lorem

from flask      import render_template, request, flash, session, redirect, url_for, Response
from sqlalchemy import text

from app import app
from db import db, get_thread, get_user_id_by_name, insert_reply_into_db, get_forum_thread_dict, \
    get_list_of_ids_and_categories, insert_thread_into_db, get_total_post_dict, get_most_recent_post_tstamp_dict


@app.before_request
def create_tables():
    """Initialize the database tables."""
    app.before_request_funcs[None].remove(create_tables)  # Run only on first request
    sql = text("CREATE TABLE IF NOT EXISTS users ("
               "user_id SERIAL PRIMARY KEY, "
               "username TEXT, "
               "join_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "password_hash TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS categories ("
               "category_id SERIAL PRIMARY KEY, "
               "name TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS threads ("
               "thread_id SERIAL PRIMARY KEY, "
               "category_id INTEGER NOT NULL, "
               "FOREIGN KEY (category_id) REFERENCES categories(category_id), "
               "user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "thread_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "title TEXT,"
               "content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS replies ("
               "reply_id SERIAL PRIMARY KEY, "
               "thread_id INTEGER NOT NULL, "
               "FOREIGN KEY (thread_id) REFERENCES threads(thread_id), "
               "user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "reply_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    # Sentinel for checking the databases are filled with mock data only once.
    sql    = text("SELECT password_hash FROM users WHERE username=(:username)")
    result = db.session.execute(sql, {"username": "User1"}).first()
    if result is not None:
        return

    # Populate with test data:
    users = ["User1", "User2", "User3", "User4", "User5"]
    for user in users:
        password_hash = argon2.PasswordHasher().hash(password=user, salt=getrandom(32, flags=0))
        sql = text("INSERT INTO users (username, password_hash) "
                   "VALUES (:username, :password_hash)"
                   "ON CONFLICT DO NOTHING")
        db.session.execute(sql, {"username"      : user,
                                 "password_hash" : password_hash})
        db.session.commit()

    categories = ["Category 1", "Category 2", "Category 3", "Category 4"]
    for category in categories:
        sql = text("INSERT INTO categories (name) "
                   "VALUES (:category) "
                   "ON CONFLICT DO NOTHING")
        db.session.execute(sql, {"category": category})
        db.session.commit()

    sql = text("SELECT category_id FROM categories")
    category_ids = [t[0] for t in db.session.execute(sql).fetchall()]

    thread_titles = ["Title 1", "Title 2", "Title 3", "Title 4"]
    sql           = text("SELECT user_id FROM users")
    user_ids      = [t[0] for t in db.session.execute(sql).fetchall()]
    user_id       = user_ids[0]

    for category_id in category_ids:
        for thread_title in thread_titles:
            sql = text("INSERT INTO threads (category_id, user_id, title, content) "
                       "VALUES (:category_id, :user_id, :title, :content) "
                       "ON CONFLICT DO NOTHING")
            db.session.execute(sql, {"category_id" : category_id,
                                     "user_id"     : user_id,
                                     "title"       : thread_title,
                                     "content"     : lorem.sentence()})
            db.session.commit()

    sql        = text("SELECT thread_id FROM threads")
    thread_ids = [t[0] for t in db.session.execute(sql).fetchall()]

    for thread_id in thread_ids:
        for user_id in user_ids:
            sql = text("INSERT INTO replies (thread_id, user_id, content)"
                       "VALUES (:thread_id, :user_id, :content)"
                       "ON CONFLICT DO NOTHING")
            db.session.execute(sql, {"thread_id" : thread_id,
                                     "user_id"   : user_id,
                                     "content"   : lorem.sentence()})
            db.session.commit()


@app.route("/")
def index() -> str:
    """Return the Index page."""
    if not "username" in session.keys():
        return render_template('index.html')

    return render_template("index.html",
                           username=session["username"],
                           forum_threads=get_forum_thread_dict(),
                           total_post_dict=get_total_post_dict(),
                           most_recent_post_dict=get_most_recent_post_tstamp_dict())


@app.route("/thread/<int:thread_id>/")
def thread(thread_id: int) -> str:
    """Return thread page matching the given thread_id."""
    if not "username" in session.keys():
        return render_template('index.html')

    return render_template("thread.html", username=session["username"], thread=get_thread(thread_id))


@app.route("/new_reply/<int:thread_id>/")
def reply(thread_id: int) -> str:
    """Send reply upload form to the user."""
    if not "username" in session.keys():
        return render_template('index.html')

    return render_template("new_reply.html", username=session["username"], thread=get_thread(thread_id))


@app.route("/submit_reply/<int:thread_id>/", methods=["GET", "POST"])
def submit_reply(thread_id: int) -> str:
    """Submit reply from user to the thread."""
    if not "username" in session.keys():
        return render_template('index.html')

    if request.method == 'POST':
        message = request.form.get('message')

        # Validate input
        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template('new_reply.html', username=session["username"], thread=get_thread(thread_id))

        user_id = get_user_id_by_name()
        insert_reply_into_db(thread_id, user_id, message)


    return render_template("thread.html", username=session["username"], thread=get_thread(thread_id))


@app.route("/new_thread/", methods=["GET", "POST"])
def new_thread() -> str:
    """Create new thread to the forum."""
    if not "username" in session.keys():
        return render_template('index.html')

    return render_template("new_thread.html", username=session["username"], ids_and_categories=get_list_of_ids_and_categories())


@app.route("/submit_thread/", methods=["GET", "POST"])
def submit_thread() -> str:
    """Submit thread from user to the forum."""
    if not "username" in session.keys():
        return render_template('index.html')

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        title       = request.form.get('title')
        message     = request.form.get('message')

        # Validate input
        if not category_id.isnumeric():
            flash("Virhe: Kategoriatunnus ei ollut numero.")
            return render_template('new_thread.html', username=session["username"], ids_and_categories=get_list_of_ids_and_categories())

        if not title:
            flash("Virhe: Otsikko ei voi olla tyhjä.")
            return render_template('new_thread.html', username=session["username"], ids_and_categories=get_list_of_ids_and_categories())

        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template('new_thread.html', username=session["username"], ids_and_categories=get_list_of_ids_and_categories())

        thread_id = insert_thread_into_db(int(category_id), get_user_id_by_name(), title, message)

        return render_template("thread.html", username=session["username"], thread=get_thread(thread_id))

    else:
        return render_template("index.html", username=session["username"], forum_threads=get_forum_thread_dict())


@app.route("/login", methods=["POST"])
def login() -> str | Response:
    """Authentication to Keskusteluforum."""
    login_error = "Käyttäjätunnusta ei löytynyt tai salasana on väärin."

    username = request.form["username"]
    sql      = text("SELECT password_hash FROM users WHERE username=(:username)")
    result   = db.session.execute(sql, {"username": username}).first()

    if result is None:
        # Username does not exist
        flash(login_error)
        return render_template('index.html')

    # Authenticate user with password
    try:
        argon2.PasswordHasher().verify(result[0], request.form["password"])
        session['username'] = username
    except argon2.exceptions.VerifyMismatchError:
        flash(login_error)

    return redirect(url_for('index'))


@app.route("/logout")
def logout():
    del session["username"]
    return redirect("/")


@app.route("/new_user", methods=["GET", "POST"])
def new_user() -> str:
    """Render page that asks for information from the new user."""
    return render_template('new_user.html')


@app.route("/register", methods=["GET", "POST"])
def register() -> str:
    """Register to Keskusteluforum."""
    username  = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    # Username validation
    sql    = text("SELECT EXISTS(SELECT 1 FROM users WHERE username=(:username))")
    result = db.session.execute(sql, {"username": username})
    if result.first()[0]:
        flash('Käyttäjänimi on jo käytössä.')
        return render_template('new_user.html')

    # Password validation
    if password1 != password2:
        flash("Salasanat eivät täsmänneet.")
        return render_template('new_user.html')

    # Store hash
    password_hash = argon2.PasswordHasher().hash(password=password1, salt=getrandom(32, flags=0))
    sql = text("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)")
    db.session.execute(sql, {"username": username, "password_hash": password_hash})
    db.session.commit()

    flash('Olet nyt rekisteröitynyt.')
    return render_template('index.html')
