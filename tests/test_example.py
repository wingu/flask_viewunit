"""
This is an example of a viewunit test you might write for app.py.

See tests/app.py for the app being tested, and tests/app_test.py for an example
of configuring viewunit.
"""

from app_test import ViewTestCase


class ExampleTest(ViewTestCase):
    """
    An example of how to use viewunit.
    """

    def test_magic_letter(self):
        # Test that a querystring letter is fed to the template
        self.run_view('/?letter=a',
                      expect_tmpl_data={'user_name': 'new user',
                                        'magic_letter': 'a'})

    def test_user_id(self):
        # Confirm that a user is recognized by name, and that userless logins
        # are greeted as a "new user"
        self.run_view('/',
                      user_id=11,
                      expect_tmpl_data={'user_name': 'user #11'})
