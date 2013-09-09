from __future__ import unicode_literals

from types import MethodType

from django.core.checks import Error
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, models
from django.db.models.loading import cache
from django.test import TestCase
from django.test.utils import override_settings
from django.test.testcases import skipIfDBFeature


class IsolatedModelsTestCase(TestCase):

    def setUp(self):
        # If you create a model in a test, the model is accessible in other
        # tests. To avoid this, we need to clear list of all models created in
        # `invalid_models` module.
        cache.app_models['invalid_models'] = {}
        cache._get_models_cache = {}

    tearDown = setUp


class CharFieldTests(IsolatedModelsTestCase):

    def test_valid_field(self):
        class Model(models.Model):
            field = models.CharField(
                max_length=255,
                choices=[
                    ('1', 'item1'),
                    ('2', 'item2'),
                ],
                db_index=True)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = []
        self.assertEqual(errors, expected)

    def test_missing_max_length(self):
        class Model(models.Model):
            field = models.CharField()

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'The field must have "max_length" attribute.',
                hint=None,
                obj=field,
                id='E038',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_negative_max_length(self):
        class Model(models.Model):
            field = models.CharField(max_length=-1)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"max_length" must be a positive integer.',
                hint=None,
                obj=field,
                id='E039',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_bad_max_length_value(self):
        class Model(models.Model):
            field = models.CharField(max_length="bad")

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"max_length" must be a positive integer.',
                hint=None,
                obj=field,
                id='E039',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_non_iterable_choices(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, choices='bad')

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"choices" must be an iterable (e.g., a list or tuple).',
                hint=None,
                obj=field,
                id='E033',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_choices_containing_non_pairs(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, choices=[(1, 2, 3), (1, 2, 3)])

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'All "choices" elements must be a tuple of two elements '
                    '(the first one is the actual value to be stored '
                    'and the second element is the human-readable name).',
                hint=None,
                obj=field,
                id='E034',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_bad_db_index_value(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, db_index='bad')

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"db_index" must be either None, True or False.',
                hint=None,
                obj=field,
                id='E035',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_too_long_char_field_under_mysql(self):
        from django.db.backends.mysql.validation import DatabaseValidation

        class Model(models.Model):
            field = models.CharField(unique=True, max_length=256)

        field = Model._meta.get_field('field')
        validator = DatabaseValidation(connection=None)
        errors = validator.check_field(field)
        expected = [
            Error(
                'Under mysql backend, the field cannot have a "max_length" '
                    'greated than 255 when it is unique.',
                hint=None,
                obj=field,
                id='E047',
            )
        ]
        self.assertEqual(errors, expected)


class DecimalFieldTests(IsolatedModelsTestCase):

    def test_required_attributes(self):
        class Model(models.Model):
            field = models.DecimalField()

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'The field requires a "decimal_places" attribute.',
                hint=None,
                obj=field,
                id='E041',
            ),
            Error(
                'The field requires a "max_digits" attribute.',
                hint=None,
                obj=field,
                id='E043',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_negative_max_digits_and_decimal_places(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits=-1, decimal_places=-1)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"decimal_places" attribute must be a non-negative integer.',
                hint=None,
                obj=field,
                id='E042',
            ),
            Error(
                '"max_digits" attribute must be a positive integer.',
                hint=None,
                obj=field,
                id='E044',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_bad_values_of_max_digits_and_decimal_places(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits="bad", decimal_places="bad")

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"decimal_places" attribute must be a non-negative integer.',
                hint=None,
                obj=field,
                id='E042',
            ),
            Error(
                '"max_digits" attribute must be a positive integer.',
                hint=None,
                obj=field,
                id='E044',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_decimal_places_greater_than_max_digits(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits=9, decimal_places=10)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                '"max_digits" must be greater or equal to "decimal_places".',
                hint=None,
                obj=field,
                id='E040',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_valid_field(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits=10, decimal_places=10)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = []
        self.assertEqual(errors, expected)


class ImageFieldTests(IsolatedModelsTestCase):

    def test_pillow_installed(self):
        try:
            import django.utils.image
        except ImproperlyConfigured:
            pillow_installed = False
        else:
            pillow_installed = True

        class Model(models.Model):
            field = models.ImageField(upload_to='somewhere')

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [] if pillow_installed else [
            Error(
                'To use ImageFields, Pillow must be installed.',
                hint='Get Pillow at https://pypi.python.org/pypi/Pillow '
                    'or run command "pip install pillow".',
                obj=field,
                id='E032',
            ),
        ]
        self.assertEqual(errors, expected)


class RelativeFieldTests(IsolatedModelsTestCase):

    def test_valid_foreign_key_without_accessor(self):
        class Target(models.Model):
            # There would be a clash if Model.field installed an accessor.
            model = models.IntegerField()

        class Model(models.Model):
            field = models.ForeignKey(Target, related_name='+')

        field = Model._meta.get_field('field')
        errors = field.check()
        self.assertEqual(errors, [])

    def test_foreign_key_to_missing_model(self):
        # Model names are resolved when a model is being created, so we cannot
        # test relative fields in isolation and we need to attach them to a
        # model.
        class Model(models.Model):
            foreign_key = models.ForeignKey('Rel1')

        field = Model._meta.get_field('foreign_key')
        errors = field.check()
        expected = [
            Error(
                'The field has a relation with model Rel1, '
                    'which has either not been installed or is abstract.',
                hint='Ensure that you did not misspell the model name and '
                    'the model is not abstract. Does your INSTALLED_APPS '
                    'setting contain the app where Rel1 is defined?',
                obj=field,
                id='E030',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_many_to_many_to_missing_model(self):
        class Model(models.Model):
            m2m = models.ManyToManyField("Rel2")

        field = Model._meta.get_field('m2m')
        errors = field.check(from_model=Model)
        expected = [
            Error(
                'The field has a relation with model Rel2, '
                    'which has either not been installed or is abstract.',
                hint='Ensure that you did not misspell the model name and '
                    'the model is not abstract. Does your INSTALLED_APPS '
                    'setting contain the app where Rel2 is defined?',
                obj=field,
                id='E030',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_ambiguous_relationship_model(self):

        class Person(models.Model):
            pass

        class Group(models.Model):
            field = models.ManyToManyField('Person',
                through="AmbiguousRelationship", related_name='tertiary')

        class AmbiguousRelationship(models.Model):
            # Too much foreign keys to Person.
            first_person = models.ForeignKey(Person, related_name="first")
            second_person = models.ForeignKey(Person, related_name="second")
            second_model = models.ForeignKey(Group)

        field = Group._meta.get_field('field')
        errors = field.check(from_model=Group)
        expected = [
            Error(
                'The model is used as an intermediary model by '
                    'invalid_models.Group.field, but it has more than one '
                    'foreign key to Person, '
                    'which is ambiguous and is not permitted.',
                hint='If you want to create a recursive relationship, use '
                    'ForeignKey("self", symmetrical=False, '
                    'through="AmbiguousRelationship").',
                obj=field,
                id='E027',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_relationship_model_with_foreign_key_to_wrong_model(self):
        class WrongModel(models.Model):
            pass

        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField('Person',
                through="InvalidRelationship")

        class InvalidRelationship(models.Model):
            person = models.ForeignKey(Person)
            wrong_foreign_key = models.ForeignKey(WrongModel)
            # The last foreign key should point to Group model.

        field = Group._meta.get_field('members')
        errors = field.check(from_model=Group)
        expected = [
            Error(
                'The model is used as an intermediary model by '
                    'invalid_models.Group.members, but it misses '
                    'a foreign key to Group or Person.',
                hint=None,
                obj=InvalidRelationship,
                id='E028',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_relationship_model_missing_foreign_key(self):
        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField('Person',
                through="InvalidRelationship")

        class InvalidRelationship(models.Model):
            group = models.ForeignKey(Group)
            # No foreign key to Person

        field = Group._meta.get_field('members')
        errors = field.check(from_model=Group)
        expected = [
            Error(
                'The model is used as an intermediary model by '
                    'invalid_models.Group.members, but it misses '
                    'a foreign key to Group or Person.',
                hint=None,
                obj=InvalidRelationship,
                id='E028',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_missing_relationship_model(self):
        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField('Person',
                through="MissingM2MModel")

        field = Group._meta.get_field('members')
        errors = field.check(from_model=Group)
        expected = [
            Error(
                'The field specifies a many-to-many relation through model '
                    'MissingM2MModel, which has not been installed.',
                hint='Ensure that you did not misspell the model name and '
                    'the model is not abstract. Does your INSTALLED_APPS '
                    'setting contain the app where MissingM2MModel is defined?',
                obj=field,
                id='E023',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_symmetrical_self_referential_field(self):
        class Person(models.Model):
            # Implicit symmetrical=False.
            friends = models.ManyToManyField('self', through="Relationship")

        class Relationship(models.Model):
            first = models.ForeignKey(Person, related_name="rel_from_set")
            second = models.ForeignKey(Person, related_name="rel_to_set")

        field = Person._meta.get_field('friends')
        errors = field.check(from_model=Person)
        expected = [
            Error(
                'Many-to-many fields with intermediate tables must not be symmetrical.',
                hint=None,
                obj=field,
                id='E024',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_too_many_foreign_keys_in_self_referential_model(self):
        class Person(models.Model):
            friends = models.ManyToManyField('self',
                through="InvalidRelationship", symmetrical=False)

        class InvalidRelationship(models.Model):
            first = models.ForeignKey(Person, related_name="rel_from_set_2")
            second = models.ForeignKey(Person, related_name="rel_to_set_2")
            third = models.ForeignKey(Person, related_name="too_many_by_far")

        field = Person._meta.get_field('friends')
        errors = field.check(from_model=Person)
        expected = [
            Error(
                'The model is used as an intermediary model by '
                    'invalid_models.Person.friends, but it has more than two '
                    'foreign keys to Person, which is ambiguous and '
                    'is not permitted.',
                hint=None,
                obj=InvalidRelationship,
                id='E025',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_symmetric_self_reference_with_intermediate_table(self):
        class Person(models.Model):
            # Explicit symmetrical=True.
            friends = models.ManyToManyField('self',
                through="Relationship", symmetrical=True)

        class Relationship(models.Model):
            first = models.ForeignKey(Person, related_name="rel_from_set")
            second = models.ForeignKey(Person, related_name="rel_to_set")

        field = Person._meta.get_field('friends')
        errors = field.check(from_model=Person)
        expected = [
            Error(
                'Many-to-many fields with intermediate tables must not be symmetrical.',
                hint=None,
                obj=field,
                id='E024',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_foreign_key_to_abstract_model(self):
        class Model(models.Model):
            foreign_key = models.ForeignKey('AbstractModel')

        class AbstractModel(models.Model):
            class Meta:
                abstract = True

        field = Model._meta.get_field('foreign_key')
        errors = field.check()
        expected = [
            Error(
                'The field has a relation with model AbstractModel, '
                    'which has either not been installed or is abstract.',
                hint='Ensure that you did not misspell the model name and '
                    'the model is not abstract. Does your INSTALLED_APPS '
                    'setting contain the app where AbstractModel is defined?',
                obj=field,
                id='E030',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_m2m_to_abstract_model(self):
        class AbstractModel(models.Model):
            class Meta:
                abstract = True

        class Model(models.Model):
            m2m = models.ManyToManyField('AbstractModel')

        field = Model._meta.get_field('m2m')
        errors = field.check(from_model=Model)
        expected = [
            Error(
                'The field has a relation with model AbstractModel, '
                    'which has either not been installed or is abstract.',
                hint='Ensure that you did not misspell the model name and '
                    'the model is not abstract. Does your INSTALLED_APPS '
                    'setting contain the app where AbstractModel is defined?',
                obj=field,
                id='E030',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_unique_m2m(self):
        class Person(models.Model):
            name = models.CharField(max_length=5)

        class Group(models.Model):
            members = models.ManyToManyField('Person', unique=True)

        field = Group._meta.get_field('members')
        errors = field.check(from_model=Group)
        expected = [
            Error(
                'ManyToManyFields must not be unique.',
                hint=None,
                obj=field,
                id='E022',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_foreign_key_to_non_unique_field(self):
        class Target(models.Model):
            bad = models.IntegerField()  # No unique=True

        class Model(models.Model):
            foreign_key = models.ForeignKey('Target', to_field='bad')

        field = Model._meta.get_field('foreign_key')
        errors = field.check()
        expected = [
            Error(
                'Target.bad must have unique=True because it is referenced by a foreign key.',
                hint=None,
                obj=field,
                id='E019',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_foreign_key_to_non_unique_field_under_explicit_model(self):
        class Target(models.Model):
            bad = models.IntegerField()

        class Model(models.Model):
            field = models.ForeignKey(Target, to_field='bad')

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'Target.bad must have unique=True because it is referenced by a foreign key.',
                hint=None,
                obj=field,
                id='E019',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_foreign_object_to_non_unique_fields(self):
        class Person(models.Model):
            # Note that both fields are not unique.
            country_id = models.IntegerField()
            city_id = models.IntegerField()

        class MMembership(models.Model):
            person_country_id = models.IntegerField()
            person_city_id = models.IntegerField()

            person = models.ForeignObject(Person,
                from_fields=['person_country_id', 'person_city_id'],
                to_fields=['country_id', 'city_id'])

        field = MMembership._meta.get_field('person')
        errors = field.check()
        expected = [
            Error(
                'No unique=True constraint on field combination '
                    '"country_id,city_id" under model Person.',
                hint='Set unique=True argument on any of the fields '
                    '"country_id,city_id" under model Person.',
                obj=field,
                id='E018',
            )
        ]
        self.assertEqual(errors, expected)


    def test_on_delete_set_null_on_non_nullable_field(self):
        class Person(models.Model):
            pass

        class Model(models.Model):
            foreign_key = models.ForeignKey('Person',
                on_delete=models.SET_NULL)

        field = Model._meta.get_field('foreign_key')
        errors = field.check()
        expected = [
            Error(
                'The field specifies on_delete=SET_NULL, but cannot be null.',
                hint='Set null=True argument on the field.',
                obj=field,
                id='E020',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_on_delete_set_default_without_default_value(self):
        class Person(models.Model):
            pass

        class Model(models.Model):
            foreign_key = models.ForeignKey('Person',
                on_delete=models.SET_DEFAULT)

        field = Model._meta.get_field('foreign_key')
        errors = field.check()
        expected = [
            Error(
                'The field specifies on_delete=SET_DEFAULT, but has no default value.',
                hint=None,
                obj=field,
                id='E021',
            ),
        ]
        self.assertEqual(errors, expected)

    @skipIfDBFeature('interprets_empty_strings_as_nulls')
    def test_nullable_primary_key(self):
        class Model(models.Model):
            field = models.IntegerField(primary_key=True, null=True)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'Primary keys must not have null=True.',
                hint='Set null=False on the field or remove primary_key=True argument.',
                obj=field,
                id='E036',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_not_swapped_model(self):
        class SwappableModel(models.Model):
            # A model that can be, but isn't swapped out. References to this
            # model should *not* raise any validation error.
            class Meta:
                swappable = 'TEST_SWAPPABLE_MODEL'

        class Model(models.Model):
            explicit_fk = models.ForeignKey(SwappableModel,
                related_name='explicit_fk')
            implicit_fk = models.ForeignKey('invalid_models.SwappableModel',
                related_name='implicit_fk')
            explicit_m2m = models.ManyToManyField(SwappableModel,
                related_name='explicit_m2m')
            implicit_m2m = models.ManyToManyField(
                'invalid_models.SwappableModel',
                related_name='implicit_m2m')

        explicit_fk = Model._meta.get_field('explicit_fk')
        self.assertEqual(explicit_fk.check(), [])

        implicit_fk = Model._meta.get_field('implicit_fk')
        self.assertEqual(implicit_fk.check(), [])

        explicit_m2m = Model._meta.get_field('explicit_m2m')
        self.assertEqual(explicit_m2m.check(from_model=Model), [])

        implicit_m2m = Model._meta.get_field('implicit_m2m')
        self.assertEqual(implicit_m2m.check(from_model=Model), [])

    @override_settings(TEST_SWAPPED_MODEL='invalid_models.Replacement')
    def test_referencing_to_swapped_model(self):
        class Replacement(models.Model):
            pass

        class SwappedModel(models.Model):
            class Meta:
                swappable = 'TEST_SWAPPED_MODEL'

        class Model(models.Model):
            explicit_fk = models.ForeignKey(SwappedModel,
                related_name='explicit_fk')
            implicit_fk = models.ForeignKey('invalid_models.SwappedModel',
                related_name='implicit_fk')
            explicit_m2m = models.ManyToManyField(SwappedModel,
                related_name='explicit_m2m')
            implicit_m2m = models.ManyToManyField(
                'invalid_models.SwappedModel',
                related_name='implicit_m2m')

        fields = [
            Model._meta.get_field('explicit_fk'),
            Model._meta.get_field('implicit_fk'),
            Model._meta.get_field('explicit_m2m'),
            Model._meta.get_field('implicit_m2m'),
        ]

        expected_error = Error(
            'The field defines a relation with the model '
                'invalid_models.SwappedModel, which has been swapped out.',
            hint='Update the relation to point at settings.TEST_SWAPPED_MODEL',
            id='E029',
        )

        for field in fields:
            expected_error.obj = field
            errors = field.check(from_model=Model)
            self.assertEqual(errors, [expected_error])


class FileFieldTests(IsolatedModelsTestCase):

    def test_missing_upload_to(self):
        class Model(models.Model):
            field = models.FileField()

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'The field requires an "upload_to" attribute.',
                hint=None,
                obj=field,
                id='E031',
            ),
        ]
        self.assertEqual(errors, expected)


class BooleanFieldTests(IsolatedModelsTestCase):

    def test_nullable_boolean_field(self):
        class Model(models.Model):
            field = models.BooleanField(null=True)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'BooleanFields do not acceps null values.',
                hint='Use a NullBooleanField instead.',
                obj=field,
                id='E037',
            ),
        ]
        self.assertEqual(errors, expected)


class GenericIPAddressFieldTests(IsolatedModelsTestCase):

    def test_non_nullable_blank(self):
        class Model(models.Model):
            field = models.GenericIPAddressField(null=False, blank=True)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'The field cannot accept blank values if null values '
                    'are not allowed, as blank values are stored as null.',
                hint=None,
                obj=field,
                id='E046',
            ),
        ]
        self.assertEqual(errors, expected)


class FilePathFieldTests(IsolatedModelsTestCase):

    def test_forbidden_files_and_folders(self):
        class Model(models.Model):
            field = models.FilePathField(allow_files=False, allow_folders=False)

        field = Model._meta.get_field('field')
        errors = field.check()
        expected = [
            Error(
                'The field must have either "allow_files" or "allow_folders" set to True.',
                hint=None,
                obj=field,
                id='E045',
            ),
        ]
        self.assertEqual(errors, expected)


class BackendSpecificChecksTests(IsolatedModelsTestCase):

    def test_check_field(self):
        """ Test if backend specific checks are performed. """

        error = Error('an error', hint=None)

        def mock(self, field, **kwargs):
            return [error]

        class Model(models.Model):
            field = models.IntegerField()

        field = Model._meta.get_field('field')

        # Mock connection.validation.check_field method.
        v = connection.validation
        old_check_field = v.check_field
        v.check_field = MethodType(mock, v)
        try:
            errors = field.check()
        finally:
            # Unmock connection.validation.check_field method.
            v.check_field = old_check_field

        self.assertEqual(errors, [error])

    def test_validate_field(self):
        """ Errors raised by deprecated `validate_field` method should be
        collected. """

        def mock(self, errors, opts, field):
            errors.add(opts, "An error!")

        class Model(models.Model):
            field = models.IntegerField()

        field = Model._meta.get_field('field')
        expected = [
            Error(
                "An error!",
                hint=None,
                obj=field,
            )
        ]

        # Mock connection.validation.validate_field method.
        v = connection.validation
        old_validate_field = v.validate_field
        v.validate_field = MethodType(mock, v)
        try:
            errors = field.check()
        finally:
            # Unmock connection.validation.validate_field method.
            v.validate_field = old_validate_field

        self.assertEqual(errors, expected)


class AccessorClashTests(IsolatedModelsTestCase):

    def test_fk_to_integer(self):
        self._test_accessor_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey('Target'))

    def test_fk_to_fk(self):
        self._test_accessor_clash(
            target=models.ForeignKey('Another'),
            relative=models.ForeignKey('Target'))

    def test_fk_to_m2m(self):
        self._test_accessor_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ForeignKey('Target'))

    def test_m2m_to_integer(self):
        self._test_accessor_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField('Target'))

    def test_m2m_to_fk(self):
        self._test_accessor_clash(
            target=models.ForeignKey('Another'),
            relative=models.ManyToManyField('Target'))

    def test_m2m_to_m2m(self):
        self._test_accessor_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ManyToManyField('Target'))

    def _test_accessor_clash(self, target, relative):
        class Another(models.Model):
            pass

        class Target(models.Model):
            model_set = target

        class Model(models.Model):
            rel = relative

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.rel clashes with field Target.model_set.',
                hint='Rename field Target.model_set or add/change '
                    'a related_name argument to the definition '
                    'for field Model.rel.',
                obj=Model._meta.get_field('rel'),
                id='E014',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_clash_between_accessors(self):
        class Target(models.Model):
            pass

        class Model(models.Model):
            foreign = models.ForeignKey(Target)
            m2m = models.ManyToManyField(Target)

        errors = Model.check()
        expected = [
            Error(
                'Clash between accessors for Model.foreign and Model.m2m.',
                hint='Add or change a related_name argument to the definition '
                    'for Model.foreign or Model.m2m.',
                obj=Model._meta.get_field('foreign'),
                id='E016',
            ),
            Error(
                'Clash between accessors for Model.m2m and Model.foreign.',
                hint='Add or change a related_name argument to the definition '
                    'for Model.m2m or Model.foreign.',
                obj=Model._meta.get_field('m2m'),
                id='E016',
            ),
        ]
        self.assertEqual(errors, expected)


class ReverseQueryNameClashTests(IsolatedModelsTestCase):

    def test_fk_to_integer(self):
        self._test_reverse_query_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey('Target'))

    def test_fk_to_fk(self):
        self._test_reverse_query_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ForeignKey('Target'))

    def test_fk_to_m2m(self):
        self._test_reverse_query_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ForeignKey('Target'))

    def test_m2m_to_integer(self):
        self._test_reverse_query_name_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField('Target'))

    def test_m2m_to_fk(self):
        self._test_reverse_query_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ManyToManyField('Target'))

    def test_m2m_to_m2m(self):
        self._test_reverse_query_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ManyToManyField('Target'))

    def _test_reverse_query_name_clash(self, target, relative):
        class Another(models.Model):
            pass

        class Target(models.Model):
            model = target

        class Model(models.Model):
            rel = relative

        errors = Model.check()
        expected = [
            Error(
                'Reverse query name for field Model.rel clashes with field Target.model.',
                hint='Rename field Target.model or add/change '
                    'a related_name argument to the definition '
                    'for field Model.rel.',
                obj=Model._meta.get_field('rel'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)


class ExplicitRelatedNameClashTests(IsolatedModelsTestCase):

    def test_fk_to_integer(self):
        self._test_explicit_related_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey('Target', related_name='clash'))

    def test_fk_to_fk(self):
        self._test_explicit_related_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ForeignKey('Target', related_name='clash'))

    def test_fk_to_m2m(self):
        self._test_explicit_related_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ForeignKey('Target', related_name='clash'))

    def test_m2m_to_integer(self):
        self._test_explicit_related_name_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField('Target', related_name='clash'))

    def test_m2m_to_fk(self):
        self._test_explicit_related_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ManyToManyField('Target', related_name='clash'))

    def test_m2m_to_m2m(self):
        self._test_explicit_related_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ManyToManyField('Target', related_name='clash'))

    def _test_explicit_related_name_clash(self, target, relative):
        class Another(models.Model):
            pass

        class Target(models.Model):
            clash = target

        class Model(models.Model):
            rel = relative

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.rel clashes with field Target.clash.',
                hint='Rename field Target.clash or add/change '
                    'a related_name argument to the definition '
                    'for field Model.rel.',
                obj=Model._meta.get_field('rel'),
                id='E014',
            ),
            Error('Reverse query name for field Model.rel clashes with field Target.clash.',
                hint='Rename field Target.clash or add/change '
                    'a related_name argument to the definition '
                    'for field Model.rel.',
                obj=Model._meta.get_field('rel'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)


class ExplicitRelatedQueryNameClashTests(IsolatedModelsTestCase):

    def test_fk_to_integer(self):
        self._test_explicit_related_query_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey('Target',
                related_query_name='clash'))

    def test_fk_to_fk(self):
        self._test_explicit_related_query_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ForeignKey('Target',
                related_query_name='clash'))

    def test_fk_to_m2m(self):
        self._test_explicit_related_query_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ForeignKey('Target',
                related_query_name='clash'))

    def test_m2m_to_integer(self):
        self._test_explicit_related_query_name_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField('Target',
                related_query_name='clash'))

    def test_m2m_to_fk(self):
        self._test_explicit_related_query_name_clash(
            target=models.ForeignKey('Another'),
            relative=models.ManyToManyField('Target',
                related_query_name='clash'))

    def test_m2m_to_m2m(self):
        self._test_explicit_related_query_name_clash(
            target=models.ManyToManyField('Another'),
            relative=models.ManyToManyField('Target',
                related_query_name='clash'))

    def _test_explicit_related_query_name_clash(self, target, relative):
        class Another(models.Model):
            pass

        class Target(models.Model):
            clash = target

        class Model(models.Model):
            rel = relative

        errors = Model.check()
        expected = [
            Error(
                'Reverse query name for field Model.rel clashes with field Target.clash.',
                hint='Rename field Target.clash or add/change a related_name '
                    'argument to the definition for field Model.rel.',
                obj=Model._meta.get_field('rel'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)


class SelfReferentialM2MClashTests(IsolatedModelsTestCase):

    def test_clash_between_accessors(self):
        class Model(models.Model):
            first_m2m = models.ManyToManyField('self', symmetrical=False)
            second_m2m = models.ManyToManyField('self', symmetrical=False)

        errors = Model.check()
        expected = [
            Error(
                'Clash between accessors for Model.first_m2m and Model.second_m2m.',
                hint=u'Add or change a related_name argument to the definition '
                    'for Model.first_m2m or Model.second_m2m.',
                obj=Model._meta.get_field('first_m2m'),
                id='E016',
            ),
            Error(
                'Clash between accessors for Model.second_m2m and Model.first_m2m.',
                hint=u'Add or change a related_name argument to the definition '
                    'for Model.second_m2m or Model.first_m2m.',
                obj=Model._meta.get_field('second_m2m'),
                id='E016',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_accessor_clash(self):
        class Model(models.Model):
            model_set = models.ManyToManyField("self", symmetrical=False)

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.model_set clashes with field Model.model_set.',
                hint='Rename field Model.model_set or add/change '
                    'a related_name argument to the definition '
                    'for field Model.model_set.',
                obj=Model._meta.get_field('model_set'),
                id='E014',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_reverse_query_name_clash(self):
        class Model(models.Model):
            model = models.ManyToManyField("self", symmetrical=False)

        errors = Model.check()
        expected = [
            Error(
                'Reverse query name for field Model.model clashes with field Model.model.',
                hint='Rename field Model.model or add/change a related_name '
                    'argument to the definition for field Model.model.',
                obj=Model._meta.get_field('model'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_clash_under_explicit_related_name(self):
        class Model(models.Model):
            clash = models.IntegerField()
            m2m = models.ManyToManyField("self",
                symmetrical=False, related_name='clash')

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.m2m clashes with field Model.clash.',
                hint='Rename field Model.clash or add/change a related_name '
                    'argument to the definition for field Model.m2m.',
                obj=Model._meta.get_field('m2m'),
                id='E014',
            ),
            Error(
                'Reverse query name for field Model.m2m clashes with field Model.clash.',
                hint='Rename field Model.clash or add/change a related_name '
                    'argument to the definition for field Model.m2m.',
                obj=Model._meta.get_field('m2m'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_valid_model(self):
        class Model(models.Model):
            first = models.ManyToManyField("self",
                symmetrical=False, related_name='first_accessor')
            second = models.ManyToManyField("self",
                symmetrical=False, related_name='second_accessor')

        errors = Model.check()
        self.assertEqual(errors, [])


class SelfReferentialFKClashTests(IsolatedModelsTestCase):

    def test_accessor_clash(self):
        class Model(models.Model):
            model_set = models.ForeignKey("Model")

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.model_set clashes with field Model.model_set.',
                hint='Rename field Model.model_set or add/change '
                    'a related_name argument to the definition '
                    'for field Model.model_set.',
                obj=Model._meta.get_field('model_set'),
                id='E014',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_reverse_query_name_clash(self):
        class Model(models.Model):
            model = models.ForeignKey("Model")

        errors = Model.check()
        expected = [
            Error(
                'Reverse query name for field Model.model clashes with field Model.model.',
                hint='Rename field Model.model or add/change '
                    'a related_name argument to the definition '
                    'for field Model.model.',
                obj=Model._meta.get_field('model'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_clash_under_explicit_related_name(self):
        class Model(models.Model):
            clash = models.CharField(max_length=10)
            foreign = models.ForeignKey("Model", related_name='clash')

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.foreign clashes with field Model.clash.',
                hint='Rename field Model.clash or add/change '
                    'a related_name argument to the definition '
                    'for field Model.foreign.',
                obj=Model._meta.get_field('foreign'),
                id='E014',
            ),
            Error(
                'Reverse query name for field Model.foreign clashes with field Model.clash.',
                hint='Rename field Model.clash or add/change '
                    'a related_name argument to the definition '
                    'for field Model.foreign.',
                obj=Model._meta.get_field('foreign'),
                id='E015',
            ),
        ]
        self.assertEqual(errors, expected)


class ComplexClashTests(IsolatedModelsTestCase):

    # New tests should not be included here, because this is a single,
    # self-contained sanity check, not a test of everything.
    def test_complex_clash(self):
        class Target(models.Model):
            tgt_safe = models.CharField(max_length=10)
            clash = models.CharField(max_length=10)
            model = models.CharField(max_length=10)

            clash1_set = models.CharField(max_length=10)

        class Model(models.Model):
            src_safe = models.CharField(max_length=10)

            foreign_1 = models.ForeignKey(Target, related_name='id')
            foreign_2 = models.ForeignKey(Target, related_name='src_safe')

            m2m_1 = models.ManyToManyField(Target, related_name='id')
            m2m_2 = models.ManyToManyField(Target, related_name='src_safe')

        errors = Model.check()
        expected = [
            Error(
                'Accessor for field Model.foreign_1 clashes with field Target.id.',
                hint='Rename field Target.id or add/change a related_name '
                    'argument to the definition for field Model.foreign_1.',
                obj=Model._meta.get_field('foreign_1'),
                id='E014',
            ),
            Error(
                'Reverse query name for field Model.foreign_1 clashes with field Target.id.',
                hint='Rename field Target.id or add/change a related_name '
                    'argument to the definition for field Model.foreign_1.',
                obj=Model._meta.get_field('foreign_1'),
                id='E015',
            ),
            Error(
                'Clash between accessors for Model.foreign_1 and Model.m2m_1.',
                hint='Add or change a related_name argument to '
                    'the definition for Model.foreign_1 or Model.m2m_1.',
                obj=Model._meta.get_field('foreign_1'),
                id='E016',
            ),
            Error(
                'Clash between reverse query names for Model.foreign_1 and Model.m2m_1.',
                hint='Add or change a related_name argument to '
                    'the definition for Model.foreign_1 or Model.m2m_1.',
                obj=Model._meta.get_field('foreign_1'),
                id='E017',
            ),

            Error(
                'Clash between accessors for Model.foreign_2 and Model.m2m_2.',
                hint='Add or change a related_name argument '
                    'to the definition for Model.foreign_2 or Model.m2m_2.',
                obj=Model._meta.get_field('foreign_2'),
                id='E016',
            ),
            Error(
                'Clash between reverse query names for Model.foreign_2 and Model.m2m_2.',
                hint='Add or change a related_name argument to '
                    'the definition for Model.foreign_2 or Model.m2m_2.',
                obj=Model._meta.get_field('foreign_2'),
                id='E017',
            ),

            Error(
                'Accessor for field Model.m2m_1 clashes with field Target.id.',
                hint='Rename field Target.id or add/change a related_name '
                    'argument to the definition for field Model.m2m_1.',
                obj=Model._meta.get_field('m2m_1'),
                id='E014',
            ),
            Error(
                'Reverse query name for field Model.m2m_1 clashes with field Target.id.',
                hint='Rename field Target.id or add/change a related_name '
                    'argument to the definition for field Model.m2m_1.',
                obj=Model._meta.get_field('m2m_1'),
                id='E015',
            ),
            Error(
                'Clash between accessors for Model.m2m_1 and Model.foreign_1.',
                hint='Add or change a related_name argument to the definition '
                    'for Model.m2m_1 or Model.foreign_1.',
                obj=Model._meta.get_field('m2m_1'),
                id='E016',
            ),
            Error(
                'Clash between reverse query names for Model.m2m_1 and Model.foreign_1.',
                hint='Add or change a related_name argument to '
                    'the definition for Model.m2m_1 or Model.foreign_1.',
                obj=Model._meta.get_field('m2m_1'),
                id='E017',
            ),

            Error(
                'Clash between accessors for Model.m2m_2 and Model.foreign_2.',
                hint='Add or change a related_name argument to the definition '
                    'for Model.m2m_2 or Model.foreign_2.',
                obj=Model._meta.get_field('m2m_2'),
                id='E016',
            ),
            Error(
                'Clash between reverse query names for Model.m2m_2 and Model.foreign_2.',
                hint='Add or change a related_name argument to the definition '
                    'for Model.m2m_2 or Model.foreign_2.',
                obj=Model._meta.get_field('m2m_2'),
                id='E017',
            ),
        ]
        self.assertEqual(errors, expected)


class IndexTogetherTests(IsolatedModelsTestCase):

    def test_non_iterable(self):
        class Model(models.Model):
            class Meta:
                index_together = 'not-a-list'

        errors = Model.check()
        expected = [
            Error(
                '"index_together" must be a list or tuple.',
                hint=None,
                obj=Model,
                id='E006',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_list_containing_non_iterable(self):
        class Model(models.Model):
            class Meta:
                index_together = [
                    'non-iterable',
                    'second-non-iterable',
                ]

        errors = Model.check()
        expected = [
            Error(
                'All "index_together" elements must be lists or tuples.',
                hint=None,
                obj=Model,
                id='E007',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_pointing_to_missing_field(self):
        class Model(models.Model):
            class Meta:
                index_together = [
                    ["missing_field"],
                ]

        errors = Model.check()
        expected = [
            Error(
                '"index_together" points to a missing field named "missing_field".',
                hint='Ensure that you did not misspell the field name.',
                obj=Model,
                id='E010',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_pointing_to_m2m_field(self):
        class Model(models.Model):
            m2m = models.ManyToManyField('self')

            class Meta:
                index_together = [
                    ["m2m"],
                ]

        errors = Model.check()
        expected = [
            Error(
                '"index_together" refers to a m2m "m2m" field, but '
                    'ManyToManyFields are not supported in "index_together".',
                hint=None,
                obj=Model,
                id='E011',
            ),
        ]
        self.assertEqual(errors, expected)


# unique_together tests are very similar to index_together tests.
class UniqueTogetherTests(IsolatedModelsTestCase):

    def test_non_iterable(self):
        class Model(models.Model):
            class Meta:
                unique_together = 'not-a-list'

        errors = Model.check()
        expected = [
            Error(
                '"unique_together" must be a list or tuple.',
                hint=None,
                obj=Model,
                id='E008',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_list_containing_non_iterable(self):
        class Model(models.Model):
            one = models.IntegerField()
            two = models.IntegerField()

            class Meta:
                unique_together = [('a', 'b'), 'not-a-list']

        errors = Model.check()
        expected = [
            Error(
                'All "unique_together" elements must be lists or tuples.',
                hint=None,
                obj=Model,
                id='E009',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_valid_model(self):
        class Model(models.Model):
            one = models.IntegerField()
            two = models.IntegerField()

            class Meta:
                # unique_together can be a simple tuple
                unique_together = ('one', 'two')

        errors = Model.check()
        self.assertEqual(errors, [])

    def test_pointing_to_missing_field(self):
        class Model(models.Model):
            class Meta:
                unique_together = [
                    ["missing_field"],
                ]

        errors = Model.check()
        expected = [
            Error(
                '"unique_together" points to a missing field named "missing_field".',
                hint='Ensure that you did not misspell the field name.',
                obj=Model,
                id='E010',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_pointing_to_m2m(self):
        class Model(models.Model):
            m2m = models.ManyToManyField('self')

            class Meta:
                unique_together = [
                    ["m2m"],
                ]

        errors = Model.check()
        expected = [
            Error(
                '"unique_together" refers to a m2m "m2m" field, but '
                'ManyToManyFields are not supported in "unique_together".',
                hint=None,
                obj=Model,
                id='E011',
            ),
        ]
        self.assertEqual(errors, expected)


class OtherModelTests(IsolatedModelsTestCase):

    def test_unique_primary_key(self):
        class Model(models.Model):
            id = models.IntegerField(primary_key=False)

        errors = Model.check()
        expected = [
            Error(
                'You cannot use "id" as a field name, because each model '
                    'automatically gets an "id" field if none of the fields '
                    'have primary_key=True.',
                hint='Remove or rename "id" field or '
                    'add primary_key=True to a field.',
                obj=Model,
                id='E005',
            )
        ]
        self.assertEqual(errors, expected)

    def test_field_names_ending_with_underscore(self):
        class Model(models.Model):
            field_ = models.CharField(max_length=10)
            m2m_ = models.ManyToManyField('self')

        errors = Model.check()
        expected = [
            Error(
                'Field names must not end with underscores.',
                hint=None,
                obj=Model._meta.get_field('field_'),
                id='E001',
            ),
            Error(
                'Field names must not end with underscores.',
                hint=None,
                obj=Model._meta.get_field('m2m_'),
                id='E001',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_ordering_non_iterable(self):
        class Model(models.Model):
            class Meta:
                ordering = "missing_field"

        errors = Model.check()
        expected = [
            Error(
                '"ordering" must be a tuple or list '
                    '(even if you want to order by only one field).',
                hint=None,
                obj=Model,
                id='E012',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_ordering_pointing_to_missing_field(self):
        class Model(models.Model):
            class Meta:
                ordering = ("missing_field",)

        errors = Model.check()
        expected = [
            Error(
                '"ordering" pointing to a missing "missing_field" field.',
                hint='Ensure that you did not misspell the field name.',
                obj=Model,
                id='E013',
            )
        ]
        self.assertEqual(errors, expected)

    @override_settings(TEST_SWAPPED_MODEL_BAD_VALUE='not-a-model')
    def test_swappable_missing_app_name(self):
        class Model(models.Model):
            class Meta:
                swappable = 'TEST_SWAPPED_MODEL_BAD_VALUE'

        errors = Model.check()
        expected = [
            Error(
                '"TEST_SWAPPED_MODEL_BAD_VALUE" is not of the form "app_label.app_name".',
                hint=None,
                obj=Model,
                id='E002',
            ),
        ]
        self.assertEqual(errors, expected)

    @override_settings(TEST_SWAPPED_MODEL_BAD_MODEL='not_an_app.Target')
    def test_swappable_missing_app(self):
        class Model(models.Model):
            class Meta:
                swappable = 'TEST_SWAPPED_MODEL_BAD_MODEL'

        errors = Model.check()
        expected = [
            Error(
                'The model has been swapped out for not_an_app.Target '
                    'which has not been installed or is abstract.',
                hint='Ensure that you did not misspell the model name and '
                    'the app name as well as the model is not abstract. Does '
                    'your INSTALLED_APPS setting contain the "not_an_app" app?',
                obj=Model,
                id='E003',
            ),
        ]
        self.assertEqual(errors, expected)

    def test_two_m2m_through_same_relationship(self):
        class Person(models.Model):
            pass

        class Group(models.Model):
            primary = models.ManyToManyField(Person,
                through="Membership", related_name="primary")
            secondary = models.ManyToManyField(Person, through="Membership",
                related_name="secondary")

        class Membership(models.Model):
            person = models.ForeignKey(Person)
            group = models.ForeignKey(Group)

        errors = Group.check()
        expected = [
            Error(
                'The model has two many-to-many relations through '
                    'the intermediary Membership model, which is not permitted.',
                hint=None,
                obj=Group,
                id='E004',
            )
        ]

    def test_duplicated_column_name(self):
        """ A field (bar) attempts to use a column name which is already
        auto-assigned earlier in the model. This should raise a system check
        error. """

        class Model(models.Model):
            foo = models.IntegerField()
            bar = models.IntegerField(db_column='foo')

            class Meta:
                db_table = 'foobar'

        errors = Model.check()
        expected = [
            Error(
                'Field "bar" has column name "foo" that is already used.',
                hint=None,
                obj=Model,
            )
        ]
        self.assertEqual(errors, expected)

    def test_duplicated_column_name_2(self):
        """ The field "foo" attempts to use a column name which is already
        auto-assigned later in the class. This should raise a system check
        error. """

        class Model(models.Model):
            foo = models.IntegerField(db_column='bar')
            bar = models.IntegerField()

            class Meta:
                db_table = 'foobar'

        errors = Model.check()
        expected = [
            Error(
                'Field "bar" has column name "bar" that is already used.',
                hint=None,
                obj=Model,
            )
        ]
        self.assertEqual(errors, expected)

    def test_duplicated_column_name_3(self):
        """ Two fields attempt to use each others' names. This is not a
        desirable scenario but valid nonetheless. """

        class Model(models.Model):
            foo = models.IntegerField(db_column='bar')
            bar = models.IntegerField(db_column='foo')

            class Meta:
                db_table = 'foobar3'

        errors = Model.check()
        expected = []
        self.assertEqual(errors, expected)

    def test_duplicated_column_name_4(self):
        """ Two fields attempt to use the same db_column value. This should
        raise a system check error. """

        class Model(models.Model):
            foo = models.IntegerField(db_column='baz')
            bar = models.IntegerField(db_column='baz')

            class Meta:
                db_table = 'foobar'

        errors = Model.check()
        expected = [
            Error(
                'Field "bar" has column name "baz" that is already used.',
                hint=None,
                obj=Model,
            )
        ]
        self.assertEqual(errors, expected)
