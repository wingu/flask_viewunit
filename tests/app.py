"""
A Flask app for testing viewunit. Demonstrates the basic use pattern for
viewunit, and provides a flask app for testing. This file would ordinarily be
split into multiple areas in a larger app (template rendering, app
configuration and several individual files of views), but it's collected into
one file for this example.

See tests/test_example.py for an example of using ViewUnit, and
tests/app_test.py for an example of configuring it.
"""
import os
from uuid import uuid4

import flask

from flask.ext import viewunit


STATIC_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'app_templates')
app = flask.Flask(__name__, template_folder=STATIC_FOLDER)
app.secret_key = uuid4().hex  # DON'T DO THIS in a real-world situation, or
                              # sessions will expire on every app restart.


def render(name, data):
    """
    To use the template verification of viewunit (expect_tmpl and
    expect_tmpl_has), you'll need to provide your own call to render that will
    intercept the arguments before passing them on to flask.render_template.
    """
    viewunit.template_called(name, data)
    return flask.render_template(name, **data)


# This little view's output depends on the current user and querystring input
@app.route('/', methods=['GET'])
def index():
    """
    Display a personalized greeting and announce which letter is our sponsor.
    """
    user_id = get_user_id()
    if not user_id:
        user_name = "new user"
    else:
        user_name = "user #%s" % user_id

    magic_letter = flask.request.args.get('letter', 'Z')

    return render("index.html", {
        'user_name': user_name,
        'magic_letter': magic_letter,
    })


def get_user_id():
    """
    In this test app, user authentication is just handled by throwing a user_id
    in the session. If you have something more complicated, or if you put more
    data in there, make sure it's also in your set_session_user implementation.
    """
    return flask.session.get('user_id')
