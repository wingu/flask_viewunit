"""
Test running and assertion machinery for Flask views
"""

#pylint: disable=C0302
from contextlib import contextmanager
import json
import functools
import html5lib
import pprint
import re
import types
import unittest
import urlparse

import flask
from nose.tools import eq_, nottest, ok_
from werkzeug.utils import parse_cookie

from viewunit import config


class ViewTestMixin(object):
    """
    Unit testing framework for views.

    Is a mixin so that other projects can mix it in with a class other
    than unittest.TestCase.  For most purposes, you'll want to use the
    pre-canned ViewTestCase class below.

    Mocks up various objects which represent the outside world to a
    view.  This allows setting of data beforehand, and checking for
    results afterwards.

    Provides one primary method: run_view, which hooks up the view to
    all the mock objects, runs it, and checks for the various expected
    results. Uses nose's assertion mechanisms to report issues. If
    all the assertions pass, it returns the response from the view.

    Also provides a db-focused analogue to setUp/tearDown via
    dbSetUp/dbTearDown.  If db work is placed in these methods, it can
    automatically be run against the test version of the database.

    Important (and Unfortunate) Note: if a subclass of this overrides
    setUp/tearDown, it *must* call super().setUp/tearDown() or much will break.
    This should be fixed.  And/or the fundamental assumptions of
    object-oriented programming should be fixed.

    The postconditions which can be checked via the expect mechanism:

     - expect_tmpl: The name of the template file called

     - expect_tmpl_has: A list of names to find in the data used to fill the
       template (ignoring data associated with those names).  Dot-separated
       names will be parsed, so you can say expect_tmpl_has=['obj.key']

     - expect_tmpl_lacks: A list of names which should *not* be in the
       template data

     - expect_tmpl_data: A dict which should be contained in the data used
       to fill the template (see note).

     - expect_json: A dict which when converted to json will be equivalent to
       the json response.

     - expect_form_errors: A tuple of form name (in the template), field name,
       number of errors expected.

     - expect_session_has:   A list of names to find in the session

     - expect_session_lacks: A list of names which should *not* be in session

     - expect_session_data:  A dict of data to find in the session  (see note)

     - expect_header_data: A dict of {response header name => header value}

     - expect_cookie_data: A dict of cookie values (see note)

     - expect_redir: The URL path for which a redirect is issued (path,
       meaning, everything to the right of the host)

     - expect_db_has: A list of (table name, dict) pairs

     - expect_db_lacks: A list of (table name, dict) pairs

     - expect_flashes_has: A list of (category, regexp) pairs

     - expect_flashes_lacks: A list of (category, regexp) pairs

     - expect_response: A list of functions to call with the response
       as a single argument.  They are expected to do their own
       checking.

     - expect_well_formed: Assuming the response data is HTML asserts that the
       data is well formed.
       Will check response bodies where the content-type is text/html and the
       status code is 200. Does not currently follow redirects.
       True by default.

    Note: for the data-type expects, we check containment, with a primitive
    notion of deep-equality.  If a List is found in the dict, it must be
    element-by-element 'equal'.  If a Dict is found, it must be contained
    in the actual dict (again, via the 'equality').
    """

    def run_view(self,
                 path,
                 method='GET',
                 session=None,
                 data=None,
                 user_id=None,
                 **expects):
        """
        Run a test of a single view
        """
        _check_expect_names(expects)

        response = None
        with config.get_app().test_client() as client:
            with client.session_transaction() as test_session:
                set_session_user_id(test_session, user_id)
                if session is not None:
                    test_session.update(session)

            # If we need to expose client.open()'s open_kwargs to the caller of
            # run_view, it can be passed in above, and used here.
            response = client.open(path=path,
                                   method=method,
                                   data=data)
            response.template_data = _get_tmpl_data()
            self._check_expects(expects, response, flask.session)

        # TODO: Flask issue? FlaskClient.__exit__ isn't cleaning up properly...
        #pylint: disable=W0212
        flask._request_ctx_stack.pop()

        return response

    def start_full(self):
        """
        Set up for full view testing.

        Should be called from setUp.
        """
        self._was_testing = config.get_app().testing
        config.get_app().testing = True

        self._old_csrf_enabled = config.get_app().config.get('CSRF_ENABLED')
        config.get_app().config['CSRF_ENABLED'] = False

        self.teardown_hooks = []

        if callable(getattr(self, 'dbSetUp', None)):
            self.dbSetUp()

    def end_full(self):
        """
        End the full view test and clean up.

        Should be called from tearDown.
        """
        try:
            for func in self.teardown_hooks:
                func()
            if hasattr(self, 'dbTearDown') and callable(self.dbTearDown):
                self.dbTearDown()
        except Exception, exc:
            print 'Exception during teardown hook:', exc
            raise
        finally:
            config.get_app().config['CSRF_ENABLED'] = self._old_csrf_enabled
            config.get_app().testing = self._was_testing

    def dbSetUp(self):
        """
        Override to do any custom setUp to the database
        """
        pass

    def dbTearDown(self):
        """
        Override to tear down anything done in sbSetUp
        """
        pass

    def _check_expects(self, expects, response, session):
        """
        Signal an error via nose.tools assertions if any of the
        postconditions specified specified in the list of expects fail to be
        met
        """
        self._check_request_var_expects(expects, response, session)
        self._check_form_errors(expects)
        self._check_db_expects(expects)
        self._check_flashes_expects(expects)
        self._check_json(expects, response)
        self._check_response_expects(expects, response)
        self._check_well_formed(expects, response)

    def _check_well_formed(self, expects, response):
        """
        Assert that, if the response is HTML that it is well formed.
        """
        # Caller can pass expect_well_formed = False to skip this check.
        if not expects.get('expect_well_formed', True):
            return

        # If the content-type is text/html and the status code was 200 validate
        # the HTML is well formed.
        # Does not follow redirects.
        if ('text/html' in response.headers['Content-Type']
            and response.status_code == 200):
            parser = html5lib.HTMLParser(strict=True)
            try:
                parser.parse(response.data)
            except html5lib.html5parser.ParseError:
                template = _get_tmpl_called()

                line = str(parser.errors[0][0][0])
                error = parser.errors[0][1]

                element = None
                if 'name' in parser.errors[0][2]:
                    element = parser.errors[0][2]['name']
                self.fail('Template %s is not well formed %s - %s line: %s'
                          % (template, error, element, line))

    #pylint: disable=R0201
    def _check_json(self, expects, response):
        """
        Check that the expected json data matches what is going to be sent by
        the response object.
        """
        if 'expect_json' in expects:
            json_data = expects['expect_json']
            eq_(json_data, json.loads(response.data))

    def _check_response_expects(self, expects, response):
        """
        Run any general response expects.
        """
        for resp_check in expects.get('expect_response', []):
            resp_check(response)

    #pylint: disable=R0914
    def _check_request_var_expects(self, expects, response, session):
        """
        Check postconditions for values set by request debug instrumentation
        """

        expect_tmpl = expects.get('expect_tmpl')
        if expect_tmpl:
            tmpl = _get_tmpl_called()
            # Verbose message if no template was called, in case viewunit
            # hasn't been configured. Hard to tell if this is a bug in using
            # viewunit, or in the flask view itself.
            ok_(tmpl,
                "Expected tmpl to be '%s', found None. Does your render()"
                "function call viewunit.template_called()?")
            eq_(expect_tmpl,
                tmpl,
                "Expected tmpl to be '%s', found '%s'" % (
                    expect_tmpl, _get_tmpl_called()))

        redirect_url = _extract_path(response.headers.get('Location', None))
        equals = [("expect_redir", redirect_url)]
        for exp_name, actual_val in equals:
            if exp_name in expects:
                exp_val = expects[exp_name]
                eq_(actual_val,
                    exp_val,
                    "Expected %s to be '%s', found '%s'" %
                    (_show(exp_name), exp_val, actual_val))

        cookies = _get_cookies(response.headers)
        contains = [("expect_tmpl_data", _get_tmpl_data()),
                     ("expect_session_data", session),
                     ("expect_cookie_data", cookies),
                     ("expect_header_data", response.headers),
                     ("expect_site_data", _get_site_data())]
        for exp_name, actual_dict in contains:
            if exp_name in expects:
                for key, exp_val in expects[exp_name].items():
                    self._check_contains(_show(exp_name),
                                         key,
                                         exp_val,
                                         actual_dict)

        has = [("expect_tmpl_has", _get_tmpl_data()),
                ("expect_session_has", session),
                ("expect_site_has", _get_site_data())]
        for exp_name, actual_dict in has:
            if exp_name in expects:
                for exp_key in expects[exp_name]:
                    self._check_has(actual_dict, exp_key, exp_name)

        lacks = [("expect_tmpl_lacks", _get_tmpl_data()),
                  ("expect_session_lacks", session),
                  ("expect_site_lacks", _get_site_data())]
        for exp_name, actual_dict in lacks:
            if exp_name in expects:
                for key in expects[exp_name]:
                    ok_(not key in actual_dict,
                        "Found unexpected key '%s' in %s" %
                        (key, _show(exp_name)))

    def _check_has(self, actual_dict, exp_key, exp_name):
        """
        Verify the presence of the exp_key in actual_dict. Use assert mechanism
        to report failures, using exp_name to label the expectation.

        Note that if the key contains dots (e.g. 'foo.bar'), the system will
        attempt to unpack those and dig into inner, contained dicts/objects.
        """
        exp_parts = exp_key.split('.')
        found_parts = []

        cur_dict = actual_dict
        while exp_parts:
            part = exp_parts.pop(0)
            cur_dict = _dot(cur_dict, part)
            ok_(cur_dict != None,
                "Couldn't find key '%s' in %s (found prefix '%s')" %
                (exp_key, _show(exp_name), ".".join(found_parts)))
            found_parts.insert(0, part)

    def _check_form_errors(self, expects):
        """
        Check for form validation errors by form/field name.
        """
        if not 'expect_form_errors' in expects:
            return

        tmpl_data = _get_tmpl_data()
        for form, field, num_errors in expects['expect_form_errors']:
            field = getattr(tmpl_data[form], field)
            eq_(num_errors, len(field.errors))

    def _check_db_expects(self, expects):
        """
        Check for db postconditions
        """
        if 'expect_db_has' in expects:
            for table, dct in expects["expect_db_has"]:
                clauses = []
                values = []
                for k, v in dct.items():
                    if v == None:
                        clauses.append("%s is null" % k)
                    else:
                        clauses.append("%s = %%s" % k)
                        values.append(v)
                rows = self.db_select(
                    "SELECT * FROM " + table + " WHERE " +
                    " AND ".join(clauses),
                    values)
                if len(rows) == 0:
                    self.fail("In db table '%(table)s', couldn't find "
                              "data specified by %(dct)s" % locals())

        if "expect_db_lacks" in expects:
            for table, dct in expects["expect_db_lacks"]:
                clauses = []
                values = []
                for k, v in dct.items():
                    if v == None:
                        clauses.append("%s is null" % k)
                    else:
                        clauses.append("%s = %%s" % k)
                        values.append(v)
                rows = self.db_select(
                    "SELECT * FROM " + table + " WHERE " +
                    " AND ".join(clauses),
                    values)
                if len(rows) > 0:
                    self.fail(
                        "In db table '%(table)s', found data which should "
                        "not be present: %(dct)s" % locals())

    def _check_flashes_expects(self, expects):
        """
        Check that the Flask flash messaging system contains messages of
        the expected categories matching the expected patterns.
        """
        flashes = flask.get_flashed_messages(with_categories=True)

        if 'expect_flashes_has' in expects:
            if not flashes:
                self.fail('Found no flashes, but expected at least %s' %
                          len(expects['expect_flashes_has']))

            for (category, pattern) in expects['expect_flashes_has']:
                has_match = False
                for fcategory, message in flashes:
                    if fcategory == category and re.search(pattern, message):
                        has_match = True
                if not has_match:
                    self.fail('flash (%s, %s) not found' % (category, pattern))

        if 'expect_flashes_lacks' in expects and flashes:
            for category, pattern in expects['expect_flashes_lacks']:
                has_match = False
                for fcategory, message in flashes:
                    if fcategory == category and re.search(pattern, message):
                        has_match = False
                if has_match:
                    self.fail('flash (%s, %s) found' % (category, pattern))

    def _check_contains(self, exp_name, key, val, dict_or_inst):
        """Check that a given actual dictionary or instance contains the value
        at the key or method specified.  If the expected value is a List
        or Dict, work recursively to check containment.  Signal failure via
        the nose.tools assert functions."""
        if hasattr(dict_or_inst, key):
            actual_val = getattr(dict_or_inst, key)
            if callable(actual_val):
                actual_val = actual_val()
        elif hasattr(dict_or_inst, '__contains__'):
            if not key in dict_or_inst:
                self.fail("%s was missing key '%s'" % (exp_name, key))
            actual_val = dict_or_inst[key]
        else:
            self.fail("%s was missing attr/method '%s'" % (exp_name, key))

        if isinstance(val, types.ListType):
            self._check_lists(exp_name, val, actual_val)
        elif isinstance(val, types.DictType):
            val_dict = val
            for inner_key, inner_val in val_dict.items():
                self._check_contains(exp_name, inner_key, inner_val,
                                    actual_val)
        else:
            eq_(val, actual_val,
                "While examining %s, expected key '%s' to yield %s, found %s" %
                (exp_name, key, repr(val), repr(actual_val)))

    def _check_lists(self, exp_name, exp_list, actual_list):
        """Check that the expected list and actual list contain the same
        data, in the same order.  If an element of the expected list is a
        Dict or a List, recursively check them."""
        if len(exp_list) != len(actual_list):
            self.fail(
                "In examining %s, expected list:\n%s\n\nFound list:\n%s" %
                (exp_name,
                 pprint.pformat(exp_list),
                 pprint.pformat(actual_list)))
        for exp_val, actual_val in zip(exp_list, actual_list):
            if isinstance(exp_val, types.ListType):
                self._check_lists(exp_name + " >>", exp_val, actual_val)
            elif isinstance(exp_val, types.DictType):
                for k, v in exp_val.items():
                    self._check_contains(exp_name, k, v, actual_val)
            else:
                eq_(exp_val,
                    actual_val,
                    "In examining %s, within a list, expected %s, found %s" %
                    (exp_name, exp_val, actual_val))
    #pylint: enable=R0914

    def db_select(self, *args, **kwargs):
        """
        Get and call the db hook set by viewunit.config.set_db_select_hook
        """
        select = config.get_db_select_hook()
        return select(*args, **kwargs)
    #pylint: enable=R0201


TMPL_CALLED = "test_tmpl_called"
TMPL_DATA = "test_tmpl_data"
SITE_DATA = "site"


def _get_tmpl_data():
    """
    Return a (single) dictionary of all data passed to the template.  Meaning,
    flatten the search list into a single dictionary (but make sure that the
    order of dict merging properly favors keys from *earlier* dicts in the list
    over later).
    """
    tmpl_data = getattr(flask.g, TMPL_DATA, None)
    if not tmpl_data:
        return {}

    # Support Jinja (just a map) and also Cheetah (list of maps).
    try:
        tmpl_data.get('_fake', None)
        # Looks like a mapping, return it
        return tmpl_data
    except AttributeError:
        # Okay, assume we have a list
        pass

    search_list = tmpl_data

    result = {}
    # Reverse so that we search in proper order
    for d in reversed(search_list):
        result.update(d)

    return result


def _get_site_data():
    """
    Return a (single) dictionary of data put into the site global object.
    Meaning, flatten the search list into a single dictionary
    (but make sure that the order of dict merging properly favors keys from
    *earlier* dicts in the list over later).
    """
    tmpl_data = getattr(flask.g, SITE_DATA, None)
    if not tmpl_data:
        return {}

    # Support Jinja (just a map) and also Cheetah (list of maps).
    try:
        tmpl_data.get('_fake', None)
        # Looks like a mapping, return it
        return tmpl_data
    except AttributeError:
        # Okay, assume we have a list
        pass

    search_list = tmpl_data

    result = {}
    # Reverse so that we search in proper order
    for d in reversed(search_list):
        result.update(d)

    return result


def _dot(obj, attr):
    """
    Return the value of '<obj>.<attr>', mimicking the templates system, or None
    if no value is found.  Do not auto-call any methods on the way.
    """
    if hasattr(obj, attr):
        return getattr(obj, attr)

    try:
        return obj[attr]
    except KeyError:
        return None


def _get_tmpl_called():
    """
    Return the name of template called
    """
    return getattr(flask.g, TMPL_CALLED, None)


def template_called(name, data):
    """
    Mark the template as called for this request
    """
    # Only record the first template per request
    if not hasattr(flask.g, TMPL_CALLED):
        flask.g.test_tmpl_called = name
        flask.g.test_tmpl_data = data

EXPECT_LIST = [
    "tmpl",
    "tmpl_has",
    "tmpl_lacks",
    "tmpl_data",
    "site_data",
    "site_has",
    "site_lacks",
    "perms_has",
    "perms_lacks",
    "form_errors",
    "cookie_data",
    "header_data",
    "redir",
    "session_has",
    "session_lacks",
    "session_data",
    "db_has",
    "db_lacks",
    "flashes_has",
    "flashes_lacks",
    "json",
    "response",
    "well_formed"
    ]
EXPECT_DICT = dict([("expect_" + e, True) for e in EXPECT_LIST])


def _check_expect_names(expects):
    """
    Verify that all the generic keyword args are valid 'expect'-type args:
    meaning, they start with expect_ and fit into our known list.
    """
    for k in expects.keys():
        if not k.startswith('expect_'):
            raise Exception("Unknown non-expect keyword argument: " + k)

        if not k in EXPECT_DICT:
            raise Exception("List of expects has unknown key: " + k)


def _extract_path(url):
    """
    Extract and return the path from a url.  If an empty string is passed in,
    return it.
    """
    if not url:
        return url

    _scheme, _netloc, path, query, fragment = urlparse.urlsplit(url)
    return urlparse.urlunsplit((None, None, path, query, fragment))


def _show(expect_name):
    """
    Return a user-facing version of an expectation name.  E.g. expect_tmpl ->
    tmpl
    """
    if expect_name.endswith('_has'):
        expect_name = expect_name[:-4]
    elif expect_name.endswith('_lacks'):
        expect_name = expect_name[:-6]

    return expect_name[7:]


class ViewTestCase(unittest.TestCase, ViewTestMixin):
    """
    A unit test case for views, inheriting all the rights and
    responsibilities of ViewTestMixin, which you should see.

    If you're writing a standard view test, this is the class you
    want.
    """
    @nottest
    @contextmanager
    def test_request_context(self, request_url, user_id=None, headers=None):
        """
        Delegates to config.get_app() to provide a context manager for a Flask
        test request context.
        """
        app = config.get_app()
        with app.test_request_context(request_url, headers=headers):
            if user_id:
                set_session_user_id(flask.session, user_id)
            yield

    @nottest
    @contextmanager
    def test_client(self, user_id=None):
        """
        Delegates to config.get_app() to provide a context manager for a Flask
        test client.
        """
        with config.get_app().test_client() as client:
            if user_id:
                set_session_user_id(flask.session, user_id)
            yield client

    def setUp(self):
        """
        Set up the db, file access and fixtures for testing
        """
        self.start_full()

    def on_teardown(self, func, *args, **kwargs):
        """
        Adds the function (and args & kwargs) to run during the next teardown.
        Useful for cleanup actions that are dependent on state within the test.
        """
        to_run = functools.partial(func, *args, **kwargs)
        self.teardown_hooks.append(to_run)

    def tearDown(self):
        """
        Tear down the file/db/fixture resources from setUp
        """
        self.end_full()


def _get_cookies(headers):
    """
    Convert a list of headers into all the cookies set
    """
    result = {}
    for cookie_str in headers.getlist('Set-Cookie'):
        cookie = parse_cookie(cookie_str)
        result.update(cookie)  # cookies are k => val dicts

        return result


def set_session_user_id(test_session, user_id):
    """
    If user_id is None, this is a noop.

    If this handler is overridden, run_view will accept a user_id keyword
    argument which, using this handler, will set up the test session as
    though user_id were logged in.
    """
    if user_id is None:
        return

    setter = config.get_session_user_setter()
    setter(test_session, user_id)
