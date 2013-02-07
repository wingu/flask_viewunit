"""
To ensure ViewUnit is configured before testing, you can put your
configuration code at the module level of a file that you have to import in
order to access the ViewTestCase, like this.
"""

from flask.ext import viewunit
from app import app


# Viewunit session handler, for easily testing authenticated views
def set_session_user(test_session, user_id):
    """
    This handler simulates user_id having logged in earlier in the session. For
    the purposes of this sample, we do that the simplest way possible.

    This function mirrors app.get_user_id().
    """
    test_session['user_id'] = user_id


# Configure ViewUnit to use app and the above session setter. If there were a
# database portion of this test, the select function should be registered here
viewunit.config.set_app(app)
viewunit.config.set_session_user_setter(set_session_user)


# This is so your tests can say 'from app_test import ViewTestCase
ViewTestCase = viewunit.ViewTestCase
