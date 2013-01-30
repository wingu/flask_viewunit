"""
Configuration hooks for viewunit. You must call set_app to use viewunit; the
other setters are optional, but allow you to use additional test features.

- set_app: Required for all tests. This hooks the viewunit module up to your
    flask app, so it can get a test client.
- set_session_user_setter: Optional. This allows tests to set the logged in
    user for a request, which is useful for an app that has any kind of user
    authentication.
- set_db_select_hook: Optional. This allows tests to make simple database
    assertions.
"""


def set_app(app):
    """
    Set viewunit to use the given Flask app for testing
    """
    global _APP
    _APP = app


def set_session_user_setter(setter):
    """
    Set viewunit to use the given function for setting a session up with a
    specific user. The setter will be called as:

        setter(test_flask_session, user_id)

    It should update the session such that your views will believe that user_id
    is currently logged in.
    """
    global _SESSION_USER_SETTER
    _SESSION_USER_SETTER = setter


def set_db_select_hook(db_select):
    """
    Set viewunit to use the given function to run DB selects. db_select will be
    called as:

        db_select(query, sql_parameters)

    It should return a list of rows, which can be dicts, tuples or dtuples
    (which you can find by googling "dtuple.py").
    """
    global _DB_SELECT
    _DB_SELECT = db_select


_APP = None
_SESSION_USER_SETTER = None
_DB_SELECT = None


def get_app():
    """
    Gets the currently configured app for testing
    """
    assert _APP is not None, \
            "Call viewunit.config.set_app() before running tests"
    return _APP


def get_session_user_setter():
    """
    Gets the currently configured app for testing
    """
    assert _SESSION_USER_SETTER is not None, \
            "Call viewunit.config.set_session_user_setter() before " + \
            "running tests"
    return _SESSION_USER_SETTER


def get_db_select_hook():
    """
    Gets the currently configured app for testing
    """
    assert _DB_SELECT is not None, \
            "Call viewunit.config.set_db_select_hook() before running tests"
    return _DB_SELECT
