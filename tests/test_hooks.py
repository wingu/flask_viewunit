from nose.tools import ok_

from viewunit.viewunit import config, ViewTestCase
from app import app


class HookTest(ViewTestCase):
    """
    All the flask hooks/functions use module-wide global state, so this is not
    going to be entirely pretty. Sorry.
    """

    def test_app_hook(self):
        config.set_app(None)
        try:
            self.run_view('/')
            ok_(False,
                "Expected AssertionError calling run_view without setting app")
        except AssertionError:
            pass

        config.set_app(app)
        self.run_view('/')

    def test_session_hook(self):
        config.set_app(app)

        try:
            self.run_view('/', user_id=1)
            ok_(False, "Expected AssertionError without session hook")
        except AssertionError:
            pass

        def hook(test_session, user_id):
            test_session['user_id'] = user_id
        config.set_session_user_setter(hook)

        self.run_view('/', user_id=11)

    def test_db_hook(self):
        config.set_app(app)

        try:
            self.run_view('/', expect_db_has=[('tables', {'foo': 1})])
            ok_(False, "Expected AssertionError without session hook")
        except AssertionError:
            pass

        # Huge hack: Return a tuple no matter the query -- it's just being
        # len()ed anyway
        def db_select(_sql, _params):
            return [(1,)]

        config.set_db_select_hook(db_select)
        self.run_view('/', expect_db_has=[('tables', {'foo': 1})])

    def setUp(self):
        """
        Unset any viewunit hooks before tests
        """
        # Ignore Pylint errors for catching any exception type, for this little
        # hacky section
        # pylint: disable=W0702
        try:
            self._old_app = config.get_app()
        except:
            self._old_app = None
        config.set_app(app)

        super(HookTest, self).setUp()

        try:
            self._old_session_hook = config.get_session_user_setter()
        except:
            self._old_session_hook = None

        try:
            self._old_db_hook = config.get_db_select_hook()
        except:
            self._old_db_hook = None
        # pylint: enable=W0702

    def tearDown(self):
        """
        Restore the viewunit state to where it was before the tests
        """
        super(HookTest, self).tearDown()

        config.set_app(self._old_app)
        config.set_session_user_setter(self._old_session_hook)
        config.set_db_select_hook(self._old_db_hook)
