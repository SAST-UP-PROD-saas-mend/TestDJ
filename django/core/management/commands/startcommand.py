import os

from django.apps import apps
from django.core.management.templates import TemplateCommand


class Command(TemplateCommand):
    help = (
        "Creates a Django management command in the management/commands folder "
        "of the specified app."
    )

    missing_args_message = "You must provide an application name, and a command name"

    def handle(self, **options):
        app_name = options.pop('name')
        command_name = options.pop('command')

        app_path = apps.get_app_config(app_name).path

        target = os.path.abspath(os.path.join(app_path, "management", "commands"))

        super().handle('command', command_name, target, **options)
