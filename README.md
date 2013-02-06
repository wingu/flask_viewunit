flask_viewunit
==============

Framework for unit testing Flask views. `flask_viewunit` lets you test the
behavior of your views without going all the way to scripting the browser with
something like Selenium or Watir. It's ideal for verifying server-side
behavior that's light on JavaScript.

A test looks something like this:

    class ApiTest(ViewTestCase):
        def trivial_test(self):
            self.run_view('/',
                          expect_tmpl='index.html',
                          expect_tmpl_data={'user_id': None})

        def test_post_message_file(self):
            message_contents = "This is a test message!")
            resp = self.run_view(
                '/api/messages/add',
                'POST',
                data={'message': StringIO(message_contents),
                      'folder_id': TEST_FOLDER_ID},
                expect_db_has=[
                    ('messages', {'folder_id': TEST_FOLDER_ID,
                                  'message_text': message_contents})])

            eq_(201, resp.status_code)

For an example of how to set up ViewUnit tests for your app, see
`tests/app.py` (the Flask app being tested), `tests/app_test.py`
(configuration for ViewUnit) and `tests/test_example.py` (an actual test of app.py).


Dependencies
------------
`flask_viewunit` may work with different versions of the following dependencies.
* Python 2.7
* Flask 0.8
* Flask-WTF 0.6
* html5lib 0.95
* mock 0.8.0
* nose 1.2.1
