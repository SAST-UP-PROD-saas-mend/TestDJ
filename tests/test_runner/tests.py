"""
Tests for django test runner
"""
from __future__ import unicode_literals

import unittest

from admin_scripts.tests import AdminScriptTestCase
from django import db
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db.backends.dummy.base import DatabaseCreation
from django.test import (
    TestCase, TransactionTestCase, mock, skipUnlessDBFeature, testcases,
)
from django.test.runner import DiscoverRunner, dependency_ordered
from django.test.testcases import connections_support_transactions
from django.utils import six
from django.utils.encoding import force_text

from .models import Person


class DependencyOrderingTests(unittest.TestCase):

    def test_simple_dependencies(self):
        raw = [
            ('s1', ('s1_db', ['alpha'])),
            ('s2', ('s2_db', ['bravo'])),
            ('s3', ('s3_db', ['charlie'])),
        ]
        dependencies = {
            'alpha': ['charlie'],
            'bravo': ['charlie'],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, value in ordered]

        self.assertIn('s1', ordered_sigs)
        self.assertIn('s2', ordered_sigs)
        self.assertIn('s3', ordered_sigs)
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s1'))
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s2'))

    def test_chained_dependencies(self):
        raw = [
            ('s1', ('s1_db', ['alpha'])),
            ('s2', ('s2_db', ['bravo'])),
            ('s3', ('s3_db', ['charlie'])),
        ]
        dependencies = {
            'alpha': ['bravo'],
            'bravo': ['charlie'],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, value in ordered]

        self.assertIn('s1', ordered_sigs)
        self.assertIn('s2', ordered_sigs)
        self.assertIn('s3', ordered_sigs)

        # Explicit dependencies
        self.assertLess(ordered_sigs.index('s2'), ordered_sigs.index('s1'))
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s2'))

        # Implied dependencies
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s1'))

    def test_multiple_dependencies(self):
        raw = [
            ('s1', ('s1_db', ['alpha'])),
            ('s2', ('s2_db', ['bravo'])),
            ('s3', ('s3_db', ['charlie'])),
            ('s4', ('s4_db', ['delta'])),
        ]
        dependencies = {
            'alpha': ['bravo', 'delta'],
            'bravo': ['charlie'],
            'delta': ['charlie'],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, aliases in ordered]

        self.assertIn('s1', ordered_sigs)
        self.assertIn('s2', ordered_sigs)
        self.assertIn('s3', ordered_sigs)
        self.assertIn('s4', ordered_sigs)

        # Explicit dependencies
        self.assertLess(ordered_sigs.index('s2'), ordered_sigs.index('s1'))
        self.assertLess(ordered_sigs.index('s4'), ordered_sigs.index('s1'))
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s2'))
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s4'))

        # Implicit dependencies
        self.assertLess(ordered_sigs.index('s3'), ordered_sigs.index('s1'))

    def test_circular_dependencies(self):
        raw = [
            ('s1', ('s1_db', ['alpha'])),
            ('s2', ('s2_db', ['bravo'])),
        ]
        dependencies = {
            'bravo': ['alpha'],
            'alpha': ['bravo'],
        }

        self.assertRaises(ImproperlyConfigured, dependency_ordered, raw, dependencies=dependencies)

    def test_own_alias_dependency(self):
        raw = [
            ('s1', ('s1_db', ['alpha', 'bravo']))
        ]
        dependencies = {
            'alpha': ['bravo']
        }

        with self.assertRaises(ImproperlyConfigured):
            dependency_ordered(raw, dependencies=dependencies)

        # reordering aliases shouldn't matter
        raw = [
            ('s1', ('s1_db', ['bravo', 'alpha']))
        ]

        with self.assertRaises(ImproperlyConfigured):
            dependency_ordered(raw, dependencies=dependencies)


class MockTestRunner(object):
    def __init__(self, *args, **kwargs):
        pass

MockTestRunner.run_tests = mock.Mock(return_value=[])


class ManageCommandTests(unittest.TestCase):

    def test_custom_test_runner(self):
        call_command('test', 'sites',
                     testrunner='test_runner.tests.MockTestRunner')
        MockTestRunner.run_tests.assert_called_with(('sites',))

    def test_bad_test_runner(self):
        with self.assertRaises(AttributeError):
            call_command('test', 'sites',
                testrunner='test_runner.NonExistentRunner')


class CustomTestRunnerOptionsTests(AdminScriptTestCase):

    def setUp(self):
        settings = {
            'TEST_RUNNER': '\'test_runner.runner.CustomOptionsTestRunner\'',
        }
        self.write_settings('settings.py', sdict=settings)

    def tearDown(self):
        self.remove_settings('settings.py')

    def test_default_options(self):
        args = ['test', '--settings=test_project.settings']
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, '1:2:3')

    def test_default_and_given_options(self):
        args = ['test', '--settings=test_project.settings', '--option_b=foo']
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, '1:foo:3')

    def test_option_name_and_value_separated(self):
        args = ['test', '--settings=test_project.settings', '--option_b', 'foo']
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, '1:foo:3')

    def test_all_options_given(self):
        args = ['test', '--settings=test_project.settings', '--option_a=bar',
                '--option_b=foo', '--option_c=31337']
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, 'bar:foo:31337')


class Ticket17477RegressionTests(AdminScriptTestCase):
    def setUp(self):
        self.write_settings('settings.py')

    def tearDown(self):
        self.remove_settings('settings.py')

    def test_ticket_17477(self):
        """'manage.py help test' works after r16352."""
        args = ['help', 'test']
        out, err = self.run_manage(args)
        self.assertNoOutput(err)


class Sqlite3InMemoryTestDbs(TestCase):

    available_apps = []

    @unittest.skipUnless(all(db.connections[conn].vendor == 'sqlite' for conn in db.connections),
                         "This is an sqlite-specific issue")
    def test_transaction_support(self):
        """Ticket #16329: sqlite3 in-memory test databases"""
        old_db_connections = db.connections
        for option_key, option_value in (
                ('NAME', ':memory:'), ('TEST', {'NAME': ':memory:'})):
            try:
                db.connections = db.ConnectionHandler({
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        option_key: option_value,
                    },
                    'other': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        option_key: option_value,
                    },
                })
                other = db.connections['other']
                DiscoverRunner(verbosity=0).setup_databases()
                msg = "DATABASES setting '%s' option set to sqlite3's ':memory:' value shouldn't interfere with transaction support detection." % option_key
                # Transaction support should be properly initialized for the 'other' DB
                self.assertTrue(other.features.supports_transactions, msg)
                # And all the DBs should report that they support transactions
                self.assertTrue(connections_support_transactions(), msg)
            finally:
                db.connections = old_db_connections


class DummyBackendTest(unittest.TestCase):
    def test_setup_databases(self):
        """
        Test that setup_databases() doesn't fail with dummy database backend.
        """
        runner_instance = DiscoverRunner(verbosity=0)
        old_db_connections = db.connections
        try:
            db.connections = db.ConnectionHandler({})
            old_config = runner_instance.setup_databases()
            runner_instance.teardown_databases(old_config)
        except Exception as e:
            self.fail("setup_databases/teardown_databases unexpectedly raised "
                      "an error: %s" % e)
        finally:
            db.connections = old_db_connections


class AliasedDefaultTestSetupTest(unittest.TestCase):
    def test_setup_aliased_default_database(self):
        """
        Test that setup_datebases() doesn't fail when 'default' is aliased
        """
        runner_instance = DiscoverRunner(verbosity=0)
        old_db_connections = db.connections
        try:
            db.connections = db.ConnectionHandler({
                'default': {
                    'NAME': 'dummy'
                },
                'aliased': {
                    'NAME': 'dummy'
                }
            })
            old_config = runner_instance.setup_databases()
            runner_instance.teardown_databases(old_config)
        except Exception as e:
            self.fail("setup_databases/teardown_databases unexpectedly raised "
                      "an error: %s" % e)
        finally:
            db.connections = old_db_connections


class SetupDatabasesTests(unittest.TestCase):

    def setUp(self):
        self._old_db_connections = db.connections
        self._old_destroy_test_db = DatabaseCreation.destroy_test_db
        self._old_create_test_db = DatabaseCreation.create_test_db
        self.runner_instance = DiscoverRunner(verbosity=0)

    def tearDown(self):
        DatabaseCreation.create_test_db = self._old_create_test_db
        DatabaseCreation.destroy_test_db = self._old_destroy_test_db
        db.connections = self._old_db_connections

    def test_setup_aliased_databases(self):
        destroyed_names = []
        DatabaseCreation.destroy_test_db = (
            lambda self, old_database_name, verbosity=1, keepdb=False, serialize=True:
            destroyed_names.append(old_database_name)
        )
        DatabaseCreation.create_test_db = (
            lambda self, verbosity=1, autoclobber=False, keepdb=False, serialize=True:
            self._get_test_db_name()
        )

        db.connections = db.ConnectionHandler({
            'default': {
                'ENGINE': 'django.db.backends.dummy',
                'NAME': 'dbname',
            },
            'other': {
                'ENGINE': 'django.db.backends.dummy',
                'NAME': 'dbname',
            }
        })

        old_config = self.runner_instance.setup_databases()
        self.runner_instance.teardown_databases(old_config)

        self.assertEqual(destroyed_names.count('dbname'), 1)

    def test_destroy_test_db_restores_db_name(self):
        db.connections = db.ConnectionHandler({
            'default': {
                'ENGINE': settings.DATABASES[db.DEFAULT_DB_ALIAS]["ENGINE"],
                'NAME': 'xxx_test_database',
            },
        })
        # Using the real current name as old_name to not mess with the test suite.
        old_name = settings.DATABASES[db.DEFAULT_DB_ALIAS]["NAME"]
        db.connections['default'].creation.destroy_test_db(old_name, verbosity=0, keepdb=True)
        self.assertEqual(db.connections['default'].settings_dict["NAME"], old_name)

    def test_serialization(self):
        serialize = []
        DatabaseCreation.create_test_db = (
            lambda *args, **kwargs: serialize.append(kwargs.get('serialize'))
        )
        db.connections = db.ConnectionHandler({
            'default': {
                'ENGINE': 'django.db.backends.dummy',
            },
        })
        self.runner_instance.setup_databases()
        self.assertEqual(serialize, [True])

    def test_serialized_off(self):
        serialize = []
        DatabaseCreation.create_test_db = (
            lambda *args, **kwargs: serialize.append(kwargs.get('serialize'))
        )
        db.connections = db.ConnectionHandler({
            'default': {
                'ENGINE': 'django.db.backends.dummy',
                'TEST': {'SERIALIZE': False},
            },
        })
        self.runner_instance.setup_databases()
        self.assertEqual(serialize, [False])


class DeprecationDisplayTest(AdminScriptTestCase):
    # tests for 19546
    def setUp(self):
        settings = {
            'DATABASES': '{"default": {"ENGINE":"django.db.backends.sqlite3", "NAME":":memory:"}}'
        }
        self.write_settings('settings.py', sdict=settings)

    def tearDown(self):
        self.remove_settings('settings.py')

    def test_runner_deprecation_verbosity_default(self):
        args = ['test', '--settings=test_project.settings', 'test_runner_deprecation_app']
        out, err = self.run_django_admin(args)
        self.assertIn("Ran 1 test", force_text(err))
        six.assertRegex(self, err, r"RemovedInDjango\d\dWarning: warning from test")
        six.assertRegex(self, err, r"RemovedInDjango\d\dWarning: module-level warning from deprecation_app")

    def test_runner_deprecation_verbosity_zero(self):
        args = ['test', '--settings=test_project.settings', '--verbosity=0', 'test_runner_deprecation_app']
        out, err = self.run_django_admin(args)
        self.assertIn("Ran 1 test", err)
        self.assertNotIn("warning from test", err)


class AutoIncrementResetTest(TransactionTestCase):
    """
    Here we test creating the same model two times in different test methods,
    and check that both times they get "1" as their PK value. That is, we test
    that AutoField values start from 1 for each transactional test case.
    """

    available_apps = ['test_runner']

    reset_sequences = True

    @skipUnlessDBFeature('supports_sequence_reset')
    def test_autoincrement_reset1(self):
        p = Person.objects.create(first_name='Jack', last_name='Smith')
        self.assertEqual(p.pk, 1)

    @skipUnlessDBFeature('supports_sequence_reset')
    def test_autoincrement_reset2(self):
        p = Person.objects.create(first_name='Jack', last_name='Smith')
        self.assertEqual(p.pk, 1)


class EmptyDefaultDatabaseTest(unittest.TestCase):
    def test_empty_default_database(self):
        """
        Test that an empty default database in settings does not raise an ImproperlyConfigured
        error when running a unit test that does not use a database.
        """
        testcases.connections = db.ConnectionHandler({'default': {}})
        connection = testcases.connections[db.utils.DEFAULT_DB_ALIAS]
        self.assertEqual(connection.settings_dict['ENGINE'], 'django.db.backends.dummy')
        try:
            connections_support_transactions()
        except Exception as e:
            self.fail("connections_support_transactions() unexpectedly raised an error: %s" % e)
