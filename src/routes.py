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

import os

import argon2

from flask      import render_template, request, flash, session, redirect, url_for, Response
from sqlalchemy import text

from app import app

from src.statics import USERNAME, ADMIN, GET, POST
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

def permissions_ok(message     : str,
                   category_id : int = None,
                   thread_id   : int = None
                   ) -> bool:
    """Check if user has permission to do action."""
    if thread_id is not None and category_id is None:
        category_id = get_thread_by_thread_id(thread_id).category_id

    if not user_has_permission_to_category(category_id, get_user_id_for_session()):
        flash(message, category='error')
        return False
    return True


###############################################################################
#                                  CATEGORIES                                 #
###############################################################################

@app.route("/new_category")
def new_category() -> str:
    """Return the create new category page."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat luoda kategorioita!", category='error')
        return redirect(url_for('index'))  # type: ignore

    return render_template('new_category.html',
                           user_ids_and_names=get_user_ids_and_names(),
                           category_name='')


@app.route("/create_category", methods=[GET, POST])
def create_category() -> str:
    """Create a new category."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat luoda kategorioita!", category='error')
        return redirect(url_for('index'))  # type: ignore

    category_name = request.form.get("category_name")
    all_users = request.form.get('all')
    sel_users = request.form.getlist('sel_users')

    if not category_name:
        flash("Anna kategorialle nimi.", category='error')
    if category_exists_in_db(category_name):
        flash("Kategoria on jo olemassa.", category='error')
    if all_users is None and not sel_users:
        flash("Valitse kategorian näkyvyys.", category='error')

    if '_flashes' in session:
        return render_template('new_category.html',
                               user_ids_and_names=get_user_ids_and_names(),
                               category_name=category_name)

    category_id = insert_category_to_db(category_name, restricted=all_users is None)

    if all_users is None and sel_users:
        for user_id in sel_users:
            insert_permission_into_db(category_id, int(user_id))

    flash(f"Uusi kategoria '{category_name}' luotu", category='success')
    return redirect(url_for('index'))  # type: ignore


@app.route("/delete_category/<int:category_id>")
def delete_category(category_id: int) -> str:
    """Delete a category from the forum."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if session[USERNAME] != ADMIN:
        flash("Vain adminit voivat poistaa kategorioita!", category='error')
        return redirect(url_for('index'))  # type: ignore

    category = get_forum_category_dict()[category_id]

    for thread_ in category.threads.values():
        for reply in thread_.replies.values():
            for like in reply.likes.values():
                delete_like_from_db(like.user_id, like.reply_id)
            delete_reply_from_db(reply.reply_id)
        delete_thread_from_db(thread_.thread_id)

    delete_permissions_for_category_from_db(category_id)
    delete_category_from_db(category_id)

    flash(f"Kategoria '{category.name}' poistettu.", category='success')
    return redirect(url_for('index'))  # type: ignore


###############################################################################
#                                   THREADS                                   #
###############################################################################

@app.route("/thread/<int:thread_id>/")
def thread(thread_id: int) -> str:
    """Return thread page matching the given thread_id."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole pääsyä ketjuun.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    return render_template('thread.html',
                           user_id=get_user_id_for_session(),
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/new_thread/", methods=[GET, POST])
def new_thread() -> str:
    """Create new thread to the forum."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    # Filter category drop-down menu items
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
            flash("Virhe! Kategoriatunnus ei ollut numero.", category='error')
        if not title:
            flash("Otsikko ei voi olla tyhjä.", category='error')
        if len(title) > 130:
            flash("Otsikko voi olla enintään 130 merkkiä.", category='error')
        if not content:
            flash("Viesti ei voi olla tyhjä.", category='error')
        if len(content) > 3000:
            flash("Viesti voi olla enintään 3000 merkkiä.", category='error')

        if '_flashes' in session:
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names())

        category_id = int(category_id)

        if not permissions_ok("Sinulla ei ole oikeutta luoda ketjua.", category_id=category_id):
            return redirect(url_for('index'))  # type: ignore

        thread_id = insert_thread_into_db(category_id, get_user_id_for_session(), title, content)

        flash(f"Uusi ketju '{title}' luotiin onnistuneesti.", category='success')
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
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta muokata ketjua.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    return render_template("edit_thread.html",
                           username=session[USERNAME],
                           ids_and_categories=get_list_of_category_ids_and_names(),
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/submit_modified_thread/<int:thread_id>/", methods=[GET, POST])
def submit_modified_thread(thread_id: int) -> str:
    """Submit modified thread."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if request.method == POST:

        title = request.form.get('title')
        content = request.form.get('content')

        if not title:
            flash("Otsikko ei voi olla tyhjä.", category='error')
        if len(title) > 130:
            flash("Otsikko voi olla enintään 130 merkkiä.", category='error')
        if not content:
            flash("Viesti ei voi olla tyhjä.", category='error')
        if len(content) > 3000:
            flash("Viesti voi olla enintään 3000 merkkiä.", category='error')
        if get_username_by_thread_id(thread_id) != session[USERNAME]:
            flash("Virhe: Väärä käyttäjä.", category='error')

        if '_flashes' in session:
            return render_template('new_thread.html',
                                   username=session[USERNAME],
                                   ids_and_categories=get_list_of_category_ids_and_names(),
                                   title=title, content=content)

        if not permissions_ok("Sinulla ei ole oikeutta muokata ketjua.", thread_id=thread_id):
            return redirect(url_for('index'))  # type: ignore

        update_thread_in_db(thread_id, title, content)
        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_thread/<int:thread_id>/", methods=[GET, POST])
def delete_thread(thread_id: int) -> str:
    """Delete thread."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta poistaa ketjua.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if get_username_by_thread_id(thread_id) == session[USERNAME]:
        thread_ = get_thread_by_thread_id(thread_id)
        for reply in thread_.replies.values():
            for like in reply.likes.values():
                delete_like_from_db(like.user_id, like.reply_id)
            delete_reply_from_db(reply.reply_id)
        delete_thread_from_db(thread_.thread_id)
        flash("Ketju poistettu.", category='success')
    else:
        flash("Et voi poistaa muiden käyttäjien ketjuja.", category='error')

    return redirect(url_for('index'))  # type: ignore


###############################################################################
#                                   REPLIES                                   #
###############################################################################

@app.route("/new_reply/<int:thread_id>/")
def reply_form(thread_id: int) -> str:
    """Send reply upload form to the user."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta vastata ketjuun.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    return render_template('new_reply.html',
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/submit_reply/<int:thread_id>/", methods=[GET, POST])
def submit_reply(thread_id: int) -> str:
    """Submit reply from user to the thread."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta vastata ketjuun.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if request.method == POST:
        # Validate input
        content = request.form.get('content')

        if len(content) == 0:
            flash("Viesti ei voi olla tyhjä.", category='error')
        if len(content) > 3000:
            flash("Viesti voi olla enintään 3000 merkkiä.", category='error')

        if '_flashes' in session:
            return render_template('new_reply.html',
                                   username=session[USERNAME],
                                   thread=get_thread_by_thread_id(thread_id))

        insert_reply_into_db(thread_id, get_user_id_for_session(), content)

    return render_template('thread.html',
                           user_id=get_user_id_for_session(),
                           username=session[USERNAME],
                           thread=get_thread_by_thread_id(thread_id))


@app.route("/edit_reply/<int:thread_id>/<int:reply_id>", methods=[GET, POST])
def edit_reply(thread_id: int, reply_id: int) -> str:
    """Edit Reply."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta muokata vastausta.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

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
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta muokata vastausta.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if request.method == POST:

        if get_username_by_reply_id(reply_id) != session[USERNAME]:
            flash("Väärä käyttäjä.", category='error')

        # Validate input
        content = request.form.get('content')

        if len(content) == 0:
            flash("Viesti ei voi olla tyhjä.", category='error')
        if len(content) > 3000:
            flash("Viesti voi olla enintään 3000 merkkiä.", category='error')

        if '_flashes' in session:
            return render_template('edit_reply.html',
                                   username=session[USERNAME],
                                   thread=get_thread_by_thread_id(thread_id))

        update_reply_in_db(reply_id, content)

        return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/delete_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def delete_reply(thread_id: int, reply_id: int) -> str:
    """Delete reply from user to the thread."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta poistaa ketjua.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        delete_reply_from_db(reply_id)
        flash("Viesti poistettu.", category='success')
    else:
        flash("Virhe: Väärä käyttäjä.", category='error')

    return redirect(f"/thread/{thread_id}")  # type: ignore


###############################################################################
#                                    LIKES                                    #
###############################################################################

@app.route("/like_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def like_reply(thread_id: int, reply_id: int) -> str:
    """Store like from user to a reply."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta tykätä vastauksesta.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omasta vastauksestasi.", category='error')
    elif user_has_liked_reply(get_user_id_for_session(), reply_id):
        flash("Et voi tykätä vastauksesta uudestaan.", category='error')
    else:
        insert_like_to_db(get_user_id_for_session(), reply_id)

    return redirect(f"/thread/{thread_id}")  # type: ignore


@app.route("/unlike_reply/<int:thread_id>/<int:reply_id>/", methods=[GET, POST])
def unlike_reply(thread_id: int, reply_id: int) -> str:
    """Remove user's like to a reply."""
    if not USERNAME in session.keys():
        return redirect(url_for('index'))  # type: ignore

    if not permissions_ok("Sinulla ei ole oikeutta poistaa tykkäystä vastauksesta.", thread_id=thread_id):
        return redirect(url_for('index'))  # type: ignore

    if get_username_by_reply_id(reply_id) == session[USERNAME]:
        flash("Et voi tykätä omista vastauksistasi ja siksi poistaa niistä tykkäyksiä.", category='error')
    elif not user_has_liked_reply(get_user_id_for_session(), reply_id):
        flash("Et voi poistaa tykkäystä vastauksesta uudestaan.", category='error')
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
        return redirect(url_for('index'))  # type: ignore

    query = request.args["query"]

    if not query:
        flash(f"Et voi hakea tyhjällä syötteellä.", category='error')
        return redirect(url_for('index'))  # type: ignore

    thread_ids = search_from_db(query)

    if not thread_ids:
        flash(f"Ei tuloksia haulle '{query}'.", category='success')
        return redirect(url_for('index'))  # type: ignore

    else:
        category_dict = get_forum_category_dict()

        # Filter results by permission
        restricted_categories = [(id_, name) for id_, name in  get_list_of_category_ids_and_names()
                                 if not user_has_permission_to_category(id_, get_user_id_for_session())]

        for category_id, _ in restricted_categories:
            del category_dict[category_id]

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

    sql    = text("SELECT EXISTS(SELECT 1 FROM users WHERE username=(:username))")
    result = db.session.execute(sql, {USERNAME: username})

    # Field validation
    if len(username) < 3 or len(username) > 20:
        flash('Käyttäjänimen on oltava vähintään kolme, ja enintään 20 merkkiä.', category='error')
    if username == ADMIN:
        flash('Käyttäjänimi on varattu admineille.', category='error')
    if result.first()[0]:
        flash('Käyttäjänimi on jo käytössä.', category='error')
    if password1 != password2:
        flash("Salasanat eivät täsmänneet.", category='error')
    if len(password1) < 12:
        flash("Salasanan on oltava vähintään 12 merkkiä.", category='error')
    if not any(c.isnumeric for c in password1):
        flash("Salasanassa on oltava vähintään 1 numero.", category='error')

    if '_flashes' in session:
        return render_template('new_user.html')

    # Store hash
    insert_new_user_into_db(username, password1)

    flash('Olet nyt rekisteröitynyt.', category='success')
    return redirect(url_for('index'))  # type: ignore


@app.route("/login", methods=[POST])
def login() -> str | Response:
    """Authentication to Keskusteluforum."""
    login_error = "Käyttäjätunnusta ei löytynyt tai salasana on väärin."

    username = request.form[USERNAME]
    sql      = text("SELECT password_hash FROM users WHERE username=(:username)")
    result   = db.session.execute(sql, {USERNAME: username}).first()

    if result is None:
        # Username does not exist
        flash(login_error, category='error')
        return redirect(url_for('index'))  # type: ignore

    # Authenticate user with password
    try:
        argon2.PasswordHasher().verify(result[0], request.form["password"])
        session[USERNAME] = username
        session["csrf_token"] = os.getrandom(32, flags=0).hex()
    except argon2.exceptions.VerifyMismatchError:
        flash(login_error, category='error')

    return redirect(url_for('index'))


@app.route("/logout")
def logout():
    """Log out the user."""
    del session[USERNAME]
    flash('Sinut on nyt kirjattu ulos', category='success')
    return redirect(url_for('index'))
