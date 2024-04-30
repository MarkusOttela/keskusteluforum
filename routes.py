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

from collections import defaultdict
from os          import getrandom

import argon2
import lorem

from flask      import render_template, request, flash, session, redirect, url_for, Response
from sqlalchemy import text

from app import app
from db  import db

from src.classes import Thread


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
    try:
        if session["username"]:
            sql = text("SELECT category_id, name FROM categories")
            ids_and_categories = db.session.execute(sql).fetchall()

            sql = text("SELECT "
                       "  threads.thread_id, "
                       "  threads.category_id, "
                       "  threads.user_id, "
                       "  users.username, "
                       "  threads.thread_tstamp, "
                       "  threads.title, "
                       "  threads.content "
                       "FROM "
                       "  threads, users "
                       "WHERE"
                       "  threads.user_id = users.user_id "
                       "ORDER BY thread_tstamp")
            db_data = db.session.execute(sql).fetchall()
            threads = [Thread(*thread_data) for thread_data in db_data]

            forum_threads = defaultdict(list)
            for category_id, category in ids_and_categories:
                for thread in threads:
                    if thread.category_id == category_id:
                        forum_threads[category].append(thread)

            return render_template("index.html", username=session["username"], forum_threads=forum_threads)

    except KeyError:
        return render_template('index.html')


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
