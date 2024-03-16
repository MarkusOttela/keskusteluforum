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

import logging

from os import getenv

from dotenv           import load_dotenv
from flask            import cli, Flask
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

@app.route("/")
def index() -> str:
    """Return the Index page."""
    return "Hello World!"


def main() -> None:
    # Disable Flask banner
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    cli.show_server_banner = lambda *_: None

    # Set environment
    load_dotenv('.env')
    app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')

    # Set database
    db = SQLAlchemy(app)

    print("Keskusteluforum 0.1 Running in http://127.0.0.1:5000")
    app.run()


if __name__ == '__main__':
    main()
