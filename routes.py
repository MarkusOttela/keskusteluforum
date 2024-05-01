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

from flask      import render_template, request, flash, session, redirect, url_for, Response
from sqlalchemy import text

from app import app
from db import db, get_thread, get_users_id, insert_reply_into_db, get_forum_thread_dict, \
    get_list_of_ids_and_categories, insert_thread_into_db, get_total_post_dict, get_most_recent_post_tstamp_dict, \
    initialize_db, get_username_by_reply_id, delete_reply_from_db, get_username_by_thread_id, delete_thread_from_db, \
    update_thread_in_db, get_reply_by_id, update_reply_in_db, insert_like_to_db, user_has_liked_reply, \
    remove_like_from_db, search_from_db

USERNAME = "username"
POST = "POST"
GET  = "GET"

class Template:
    INDEX          = 'index.html'
    THREAD         = 'thread.html'
    NEW_THREAD     = 'new_thread.html'
    NEW_USER       = 'new_user.html'
    NEW_REPLY      = 'new_reply.html'
    REPLY          = 'reply.html'
    EDIT_REPLY     = 'edit_reply.html'
    SEARCH_RESULTS = 'search_results.html'

###############################################################################
#                                     MAIN                                    #
###############################################################################

@app.before_request
def create_tables():
    """Initialize the database tables."""
    app.before_request_funcs[None].remove(create_tables)  # Run only on first request
    initialize_db()


@app.route("/")
def index() -> str:
    """Return the Index page."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    return render_template(Template.INDEX,
                           username=session[USERNAME],
                           forum_threads=get_forum_thread_dict(),
                           total_post_dict=get_total_post_dict(),
                           most_recent_post_dict=get_most_recent_post_tstamp_dict())


###############################################################################
#                                   THREADS                                   #
###############################################################################

@app.route("/thread/<int:thread_id>/")
def thread(thread_id: int) -> str:
    """Return thread page matching the given thread_id."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    return render_template(Template.THREAD,
                           user_id=get_users_id(),
                           username=session[USERNAME],
                           thread=get_thread(thread_id))


@app.route("/new_thread/", methods=[GET, POST])
def new_thread() -> str:
    """Create new thread to the forum."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    return render_template(Template.NEW_THREAD,
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_ids_and_categories())


@app.route("/submit_thread/", methods=[GET, POST])
def submit_thread() -> str:
    """Submit thread from user to the forum."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        title       = request.form.get('title')
        message     = request.form.get('message')

        # Validate input
        if not category_id.isnumeric():
            flash("Virhe: Kategoriatunnus ei ollut numero.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        if not title:
            flash("Virhe: Otsikko ei voi olla tyhjä.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        thread_id = insert_thread_into_db(int(category_id), get_users_id(), title, message)

        return render_template(Template.THREAD,
                               username=session[USERNAME],
                               thread=get_thread(thread_id))

    else:
        return render_template(Template.INDEX,
                               username=session[USERNAME],
                               forum_threads=get_forum_thread_dict())


@app.route("/edit_thread/<int:thread_id>/", methods=[GET, POST])
def edit_thread(thread_id: int) -> str:
    """Edit thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    return render_template("edit_thread.html",
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_ids_and_categories(),
                           thread=get_thread(thread_id))


@app.route("/submit_modified_thread/<int:thread_id>/", methods=[GET, POST])
def submit_modified_thread(thread_id: int) -> str:
    """Submit modified thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if request.method == 'POST':

        title = request.form.get('title')
        message = request.form.get('message')

        if not title:
            flash("Virhe: Otsikko ei voi olla tyhjä.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        if get_username_by_thread_id(thread_id) != session[USERNAME]:
            flash("Virhe: Väärä käyttäjä.")
            return render_template(Template.NEW_THREAD,
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_ids_and_categories())

        update_thread_in_db(thread_id, title, message)
        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_thread/<int:thread_id>/", methods=[GET, POST])
def delete_thread(thread_id: int) -> str:
    """Delete thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if get_username_by_thread_id(thread_id) == session[USERNAME]:
        delete_thread_from_db(thread_id)
        flash("Ketju poistettu.")
    else:
        flash("Virhe: Väärä käyttäjä.")

    return redirect(url_for('index'))  # type: ignore


###############################################################################
#                                   REPLIES                                   #
###############################################################################

@app.route("/new_reply/<int:thread_id>/")
def reply_form(thread_id: int) -> str:
    """Send reply upload form to the user."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    return render_template(Template.NEW_REPLY,
                           username=session[USERNAME],
                           thread=get_thread(thread_id))


@app.route("/submit_reply/<int:thread_id>/", methods=[GET, POST])
def submit_reply(thread_id: int) -> str:
    """Submit reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if request.method == POST:
        message = request.form.get('message')

        # Validate input
        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template(Template.NEW_REPLY,
                                   username=session[USERNAME],
                                   thread=get_thread(thread_id))

        insert_reply_into_db(thread_id, get_users_id(), message)


    return render_template(Template.THREAD,
                           username=session[USERNAME],
                           thread=get_thread(thread_id))


@app.route("/edit_reply/<int:thread_id>/<int:reply_id>", methods=[GET, POST])
def edit_reply(thread_id: int, reply_id: int) -> str:
    """Edit Reply."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    reply = get_reply_by_id(reply_id)

    return render_template(Template.EDIT_REPLY,
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_ids_and_categories(),
                           thread=get_thread(thread_id),
                           reply=reply)


@app.route("/submit_modified_reply/<int:thread_id>/<int:reply_id>", methods=[GET, POST])
def submit_modified_reply(thread_id: int, reply_id: int) -> str:
    """Submit edited reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if request.method == POST:
        message = request.form.get('message')

        # Validate input
        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template(Template.EDIT_REPLY,
                                   username=session[USERNAME],
                                   thread=get_thread(thread_id))

        if get_username_by_reply_id(reply_id) != session[USERNAME]:
            flash("Virhe: Väärä käyttäjä.")
            return render_template(Template.THREAD,
                                   username=session[USERNAME],
                                   thread=get_thread(thread_id))

        update_reply_in_db(reply_id, message)

        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def delete_reply(thread_id: int, reply_id: int) -> str:
    """Delete reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        delete_reply_from_db(reply_id)
        flash("Viesti poistettu.")
    else:
        flash("Virhe: Väärä käyttäjä.")

    return redirect(f"/thread/{thread_id}")  # type: ignore


###############################################################################
#                                    LIKES                                    #
###############################################################################

@app.route("/like_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def like_reply(thread_id: int, reply_id: int) -> str:
    """Store like from user to a reply."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omasta vastauksestasi.")
    elif user_has_liked_reply(get_users_id(), reply_id):
        flash("Et voi tykätä vastauksesta uudestaan.")
    else:
        insert_like_to_db(get_users_id(), reply_id)

    return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/unlike_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def unlike_reply(thread_id: int, reply_id: int) -> str:
    """Remove user's like to a reply."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omista vastauksistasi ja siksi poistaa niistä tykkäyksiä.")
    elif not user_has_liked_reply(get_users_id(), reply_id):
        flash("Et voi poistaa tykkäystä vastauksesta uudestaan.")
    else:
        remove_like_from_db(get_users_id(), reply_id)

    return redirect(f"/thread/{thread_id}")  # type: ignore


###############################################################################
#                                    SEARCH                                   #
###############################################################################

@app.route("/search_posts/", methods=[GET, POST])
def search_posts() -> str:
    """Search posts."""
    if not USERNAME in session.keys():
        return render_template(Template.INDEX)

    query = request.args["query"]

    if not query:
        flash(f"Et voi hakea tyhjällä syötteellä.")
        return redirect(url_for('index'))  # type: ignore

    thread_ids = search_from_db(query)

    if not thread_ids:
        flash(f"Ei tuloksia haulle '{query}'.")
        return redirect(url_for('index'))  # type: ignore

    else:
        threads = [get_thread(thread_id) for thread_id in thread_ids]

        return render_template(Template.SEARCH_RESULTS,
                               username=session[USERNAME],
                               query=query,
                               most_recent_post_dict=get_most_recent_post_tstamp_dict(),
                               threads=threads)


###############################################################################
#                                 USER ACCOUNT                                #
###############################################################################


@app.route("/new_user", methods=[GET, POST])
def new_user() -> str:
    """Render page that asks for information from the new user."""
    return render_template(Template.NEW_USER)


@app.route("/register", methods=[GET, POST])
def register() -> str:
    """Register to Keskusteluforum."""
    username  = request.form[USERNAME]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    # Username validation
    sql    = text("SELECT EXISTS(SELECT 1 FROM users WHERE username=(:username))")
    result = db.session.execute(sql, {USERNAME: username})
    if result.first()[0]:
        flash('Käyttäjänimi on jo käytössä.')
        return render_template(Template.NEW_USER)

    # Password validation
    if password1 != password2:
        flash("Salasanat eivät täsmänneet.")
        return render_template(Template.NEW_USER)

    # Store hash
    password_hash = argon2.PasswordHasher().hash(password=password1, salt=getrandom(32, flags=0))
    sql = text("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)")
    db.session.execute(sql, {USERNAME: username, "password_hash": password_hash})
    db.session.commit()

    flash('Olet nyt rekisteröitynyt.')
    return render_template(Template.INDEX)


@app.route("/login", methods=[POST])
def login() -> str | Response:
    """Authentication to Keskusteluforum."""
    login_error = "Käyttäjätunnusta ei löytynyt tai salasana on väärin."

    username = request.form[USERNAME]
    sql      = text("SELECT password_hash FROM users WHERE username=(:username)")
    result   = db.session.execute(sql, {USERNAME: username}).first()

    if result is None:
        # Username does not exist
        flash(login_error)
        return render_template(Template.INDEX)

    # Authenticate user with password
    try:
        argon2.PasswordHasher().verify(result[0], request.form["password"])
        session[USERNAME] = username
    except argon2.exceptions.VerifyMismatchError:
        flash(login_error)

    return redirect(url_for('index'))


@app.route("/logout")
def logout():
    """Log out the user."""
    del session[USERNAME]
    return redirect("/")
