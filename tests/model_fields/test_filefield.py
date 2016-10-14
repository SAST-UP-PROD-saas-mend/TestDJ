import os
import sys
import unittest

from django.core.files import temp
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import TestCase, override_settings

from .models import Document


class FileFieldTests(TestCase):

    def test_clearable(self):
        """
        FileField.save_form_data() will clear its instance attribute value if
        passed False.
        """
        d = Document(myfile='something.txt')
        self.assertEqual(d.myfile, 'something.txt')
        field = d._meta.get_field('myfile')
        field.save_form_data(d, False)
        self.assertEqual(d.myfile, '')

    def test_unchanged(self):
        """
        FileField.save_form_data() considers None to mean "no change" rather
        than "clear".
        """
        d = Document(myfile='something.txt')
        self.assertEqual(d.myfile, 'something.txt')
        field = d._meta.get_field('myfile')
        field.save_form_data(d, None)
        self.assertEqual(d.myfile, 'something.txt')

    def test_changed(self):
        """
        FileField.save_form_data(), if passed a truthy value, updates its
        instance attribute.
        """
        d = Document(myfile='something.txt')
        self.assertEqual(d.myfile, 'something.txt')
        field = d._meta.get_field('myfile')
        field.save_form_data(d, 'else.txt')
        self.assertEqual(d.myfile, 'else.txt')

    def test_delete_when_file_unset(self):
        """
        Calling delete on an unset FileField should not call the file deletion
        process, but fail silently (#20660).
        """
        d = Document()
        d.myfile.delete()

    def test_refresh_from_db(self):
        d = Document.objects.create(myfile='something.txt')
        d.refresh_from_db()
        self.assertIs(d.myfile.instance, d)

    def test_defer(self):
        Document.objects.create(myfile='something.txt')
        self.assertEqual(Document.objects.defer('myfile')[0].myfile, 'something.txt')

    @unittest.skipIf(sys.platform.startswith('win'), "Windows doesn't support moving open files.")
    # Ensure that source and destination of move are on same filesystem,
    # and prevent writing to tests directory
    @override_settings(MEDIA_ROOT=temp.gettempdir())
    def test_move_temporary_file(self):
        """
        Check that a temporary uploaded file is moved
        to upload destination rather than copied (#27334)
        """
        with TemporaryUploadedFile('something.txt', 'text/plain', 0, 'UTF-8') as tmp_file:
            tmp_file_path = tmp_file.temporary_file_path()
            Document.objects.create(myfile=tmp_file)
            still_exists = os.path.exists(tmp_file_path)
            self.assertFalse(still_exists, 'Temporary file still exists')
