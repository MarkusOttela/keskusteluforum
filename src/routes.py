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

import argon2

from flask      import render_template, request, flash, session, redirect, url_for, Response
from sqlalchemy import text

from src.statics import USERNAME, ADMIN, GET, POST

from app import app

from src.db import (db, create_tables, mock_db_content,
                    insert_admin_account_into_db, insert_new_user_into_db,
                    get_user_id_for_session, get_user_ids_and_names, get_username_by_reply_id,
                    get_username_by_thread_id,
                    insert_category_to_db, delete_category_from_db, category_exists_in_db,
                    get_list_of_category_ids_and_names,
                    insert_thread_into_db, update_thread_in_db, delete_thread_from_db, get_thread_by_thread_id,
                    insert_reply_into_db, update_reply_in_db, delete_reply_from_db, get_reply_by_id,
                    insert_like_to_db, delete_like_from_db, user_has_liked_reply,
                    search_from_db, get_forum_category_dict, insert_permission_into_db, user_has_permission_to_category,
                    delete_permissions_for_category_from_db)


###############################################################################
#                                     MAIN                                    #
###############################################################################

@app.before_request
def init_db():
    """Initialize the database tables."""
    app.before_request_funcs[None].remove(init_db)  # Run only on first request
    create_tables()
    mock_db_content()
    insert_admin_account_into_db()


@app.route("/")
def index() -> str:
    """Return the Index page."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    return render_template('index.html',
                           username=session[USERNAME],
                           user_id=get_user_id_for_session(),
                           forum_categories=get_forum_category_dict())


###############################################################################
#                                  PERMISSIONS                                #
###############################################################################

def permissions_ok(message: str, category_id: int = None, thread_id: int = None) -> bool:
    """Check if user has permission to do action."""

    if thread_id is not None and category_id is None:
        category_id = get_thread_by_thread_id(thread_id).category_id

    user_is_admin = (session[USERNAME] == ADMIN)
    restricted_category = get_forum_category_dict()[category_id].is_restricted
    user_has_permission = user_has_permission_to_category(category_id, get_user_id_for_session())

    if not user_is_admin and restricted_category and not user_has_permission:
        flash(message)
        return False
    return True


###############################################################################
#                                  CATEGORIES                                 #
###############################################################################

@app.route("/new_category")
def new_category() -> str:
    """Return the create new category page."""
    if not USERNAME in session.keys():
        return render_template('index.html')
    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat luoda kategorioita!")
        return render_template('index.html')

    return render_template('new_category.html',
                           user_ids_and_names=get_user_ids_and_names(),
                           category_name='')


@app.route("/create_category", methods=["GET", "POST"])
def create_category() -> str:
    """Create a new category."""
    if not USERNAME in session.keys():
        return render_template('index.html')
    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat luoda kategorioita!")
        return render_template('index.html')

    category_name = request.form.get("category_name")
    all_users = request.form.get('all')
    sel_users = request.form.getlist('sel_users')

    if not category_name:
        flash("Anna kategorialle nimi.")
    if category_exists_in_db(category_name):
        flash("Kategoria on jo olemassa.")
    if all_users is None and not sel_users:
        flash("Valitse kategorian näkyvyys.")

    if '_flashes' in session:
        return render_template('new_category.html',
                               user_ids_and_names=get_user_ids_and_names(),
                               category_name=category_name)

    category_id = insert_category_to_db(category_name, restricted=all_users is None)

    if all_users is None and sel_users:
        for user_id in sel_users:
            insert_permission_into_db(category_id, int(user_id))

    flash(f"Uusi kategoria '{category_name}' luotu")
    return redirect(url_for('index'))  # type: ignore


@app.route("/delete_category/<int:category_id>")
def delete_category(category_id: int) -> str:
    """Delete a category from the forum."""
    if not USERNAME in session.keys():
        return render_template('index.html')
    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat poistaa kategorioita!")
        return render_template('index.html')

    categories = get_forum_category_dict()

    category = categories[category_id]

    for thread_ in category.threads.values():
        for reply in thread_.replies.values():
            for like in reply.likes.values():
                delete_like_from_db(like.user_id, like.reply_id)
            delete_reply_from_db(reply.reply_id)
        delete_thread_from_db(thread_.thread_id)

    delete_permissions_for_category_from_db(category_id)
    delete_category_from_db(category_id)

    flash(f"Kategoria '{categories[category_id].name}' poistettu.")
    return redirect(url_for('index'))  # type: ignore


###############################################################################
#                                   THREADS                                   #
###############################################################################

@app.route("/thread/<int:thread_id>/")
def thread(thread_id: int) -> str:
    """Return thread page matching the given thread_id."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole pääsyä ketjuun.", thread_id=thread_id):
        return render_template('index.html')

    return render_template('thread.html',
                           user_id=get_user_id_for_session(),
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/new_thread/", methods=[GET, POST])
def new_thread() -> str:
    """Create new thread to the forum."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    ids_and_cat_names = [(id_, name) for id_, name in get_list_of_category_ids_and_names()
                         if user_has_permission_to_category(id_, get_user_id_for_session())]

    return render_template('new_thread.html',
                           username=session[USERNAME],
                           ids_and_categories=ids_and_cat_names)


@app.route("/submit_thread/", methods=[GET, POST])
def submit_thread() -> str:
    """Submit thread from user to the forum."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if request.method == POST:
        category_id = request.form.get('category_id')
        title       = request.form.get('title')
        content     = request.form.get('content')

        # Validate input
        if not category_id.isnumeric():
            flash("Virhe: Kategoriatunnus ei ollut numero.")
        if not title:
            flash("Virhe: Otsikko ei voi olla tyhjä.")
        if not content:
            flash("Virhe: Viesti ei voi olla tyhjä.")

        if '_flashes' in session:
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names())

        category_id = int(category_id)

        if not permissions_ok("Sinulla ei ole oikeutta luoda ketjua.", category_id=category_id):
            return redirect(url_for('index'))  # type: ignore

        thread_id = insert_thread_into_db(category_id, get_user_id_for_session(), title, content)

        return render_template('thread.html',
                               user_id=get_user_id_for_session(),
                               username=session[USERNAME],
                               thread=get_thread_by_thread_id(thread_id))

    else:
        return redirect(url_for('index'))  # type: ignore


@app.route("/edit_thread/<int:thread_id>/", methods=[GET, POST])
def edit_thread(thread_id: int) -> str:
    """Edit thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta muokata ketjua.", thread_id=thread_id):
        return render_template('index.html')

    return render_template("edit_thread.html",
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_category_ids_and_names(),
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/submit_modified_thread/<int:thread_id>/", methods=[GET, POST])
def submit_modified_thread(thread_id: int) -> str:
    """Submit modified thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if request.method == POST:

        title = request.form.get('title')
        message = request.form.get('message')

        if not title:
            flash("Virhe: Otsikko ei voi olla tyhjä.")
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names())

        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names())

        if get_username_by_thread_id(thread_id) != session[USERNAME]:
            flash("Virhe: Väärä käyttäjä.")
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names())

        if not permissions_ok("Sinulla ei ole oikeutta muokata ketjua.", thread_id=thread_id):
            return render_template('index.html')

        update_thread_in_db(thread_id, title, message)
        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_thread/<int:thread_id>/", methods=[GET, POST])
def delete_thread(thread_id: int) -> str:
    """Delete thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta poistaa ketjua.", thread_id=thread_id):
        return render_template('index.html')

    if get_username_by_thread_id(thread_id) == session[USERNAME]:

        thread_ = get_thread_by_thread_id(thread_id)
        for reply in thread_.replies.values():
            for like in reply.likes.values():
                delete_like_from_db(like.user_id, like.reply_id)
            delete_reply_from_db(reply.reply_id)
        delete_thread_from_db(thread_.thread_id)
        flash("Ketju poistettu.")
    else:
        flash("Et voi poistaa muiden käyttäjien ketjuja.")

    return redirect(url_for('index'))  # type: ignore


###############################################################################
#                                   REPLIES                                   #
###############################################################################

@app.route("/new_reply/<int:thread_id>/")
def reply_form(thread_id: int) -> str:
    """Send reply upload form to the user."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta vastata ketjuun.", thread_id=thread_id):
        return render_template('index.html')

    return render_template('new_reply.html',
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/submit_reply/<int:thread_id>/", methods=[GET, POST])
def submit_reply(thread_id: int) -> str:
    """Submit reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta vastata ketjuun.", thread_id=thread_id):
        return render_template('index.html')

    if request.method == POST:
        message = request.form.get('message')

        # Validate input
        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template('new_reply.html',
                                   username=session[USERNAME],
                                   thread=get_thread_by_thread_id(thread_id))

        insert_reply_into_db(thread_id, get_user_id_for_session(), message)

    return render_template('thread.html',
                           user_id=get_user_id_for_session(),
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/edit_reply/<int:thread_id>/<int:reply_id>", methods=[GET, POST])
def edit_reply(thread_id: int, reply_id: int) -> str:
    """Edit Reply."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta muokata vastausta.", thread_id=thread_id):
        return render_template('index.html')

    reply = get_reply_by_id(reply_id)

    return render_template('edit_reply.html',
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_category_ids_and_names(),
                           thread=get_thread_by_thread_id(thread_id),
                           reply=reply)


@app.route("/submit_modified_reply/<int:thread_id>/<int:reply_id>", methods=[GET, POST])
def submit_modified_reply(thread_id: int, reply_id: int) -> str:
    """Submit edited reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if request.method == POST:
        message = request.form.get('message')

        # Validate input
        if not message:
            flash("Virhe: Viesti ei voi olla tyhjä.")
            return render_template('edit_reply.html',
                                   username=session[USERNAME],
                                   thread=get_thread_by_thread_id(thread_id))

        if get_username_by_reply_id(reply_id) != session[USERNAME]:
            flash("Virhe: Väärä käyttäjä.")
            return render_template('thread.html',
                                   user_id=get_user_id_for_session(),
                                   username=session[USERNAME],
                                   thread=get_thread_by_thread_id(thread_id))

        if not permissions_ok("Sinulla ei ole oikeutta muokata vastausta.", thread_id=thread_id):
            return render_template('index.html')

        update_reply_in_db(reply_id, message)

        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def delete_reply(thread_id: int, reply_id: int) -> str:
    """Delete reply from user to the thread."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta poistaa ketjua.", thread_id=thread_id):
        return render_template('index.html')

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
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta tykätä vastauksesta.", thread_id=thread_id):
        return render_template('index.html')

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omasta vastauksestasi.")
    elif user_has_liked_reply(get_user_id_for_session(), reply_id):
        flash("Et voi tykätä vastauksesta uudestaan.")
    else:
        insert_like_to_db(get_user_id_for_session(), reply_id)

    return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/unlike_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def unlike_reply(thread_id: int, reply_id: int) -> str:
    """Remove user's like to a reply."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    if not permissions_ok("Sinulla ei ole oikeutta poistaa tykkäystä vastauksesta.", thread_id=thread_id):
        return render_template('index.html')

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omista vastauksistasi ja siksi poistaa niistä tykkäyksiä.")
    elif not user_has_liked_reply(get_user_id_for_session(), reply_id):
        flash("Et voi poistaa tykkäystä vastauksesta uudestaan.")
    else:
        delete_like_from_db(get_user_id_for_session(), reply_id)

    return redirect(f"/thread/{thread_id}")  # type: ignore


###############################################################################
#                                    SEARCH                                   #
###############################################################################

@app.route("/search_posts/", methods=[GET, POST])
def search_posts() -> str:
    """Search posts."""
    if not USERNAME in session.keys():
        return render_template('index.html')

    query = request.args["query"]

    # TODO: Permission check

    if not query:
        flash(f"Et voi hakea tyhjällä syötteellä.")
        return redirect(url_for('index'))  # type: ignore

    thread_ids = search_from_db(query)

    if not thread_ids:
        flash(f"Ei tuloksia haulle '{query}'.")
        return redirect(url_for('index'))  # type: ignore

    else:
        category_dict = get_forum_category_dict()

        return render_template('search_results.html',
                               username=session[USERNAME],
                               query=query,
                               category_dict=category_dict,
                               thread_ids=thread_ids)


###############################################################################
#                                 USER ACCOUNT                                #
###############################################################################


@app.route("/new_user", methods=[GET, POST])
def new_user() -> str:
    """Render page that asks for information from the new user."""
    return render_template('new_user.html')


@app.route("/register", methods=[GET, POST])
def register() -> str:
    """Register to Keskusteluforum."""
    username  = request.form[USERNAME]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    # Username validation
    sql    = text("SELECT EXISTS(SELECT 1 FROM users WHERE username=(:username))")
    result = db.session.execute(sql, {USERNAME: username})

    if username == ADMIN:
        flash('Käyttäjänimi on varattu admineille.')
        return render_template('new_user.html')

    if result.first()[0]:
        flash('Käyttäjänimi on jo käytössä.')
        return render_template('new_user.html')

    # Password validation
    if password1 != password2:
        flash("Salasanat eivät täsmänneet.")
        return render_template('new_user.html')

    # Store hash
    insert_new_user_into_db(username, password1)

    flash('Olet nyt rekisteröitynyt.')
    return render_template('index.html')


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
        return render_template('index.html')

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
