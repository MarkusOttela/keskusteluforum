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

from flask      import render_template, request, flash, session, redirect
from sqlalchemy import text

from app import app
from db  import db


@app.before_request
def create_tables():
    """Initialize the database tables."""
    app.before_request_funcs[None].remove(create_tables)  # Run only on first request
    sql = text("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT, password_hash TEXT)")
    db.session.execute(sql)
    db.session.commit()


@app.route("/")
def index() -> str:
    """Return the Index page."""
    return render_template('index.html')


@app.route("/login", methods=["POST"])
def login() -> str:
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

    return render_template('index.html')


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
