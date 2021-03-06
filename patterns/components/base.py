import imp
import inspect
import os
import yaml
from functools import partial

from django.conf import settings
from django.template import Node, Template, TemplateDoesNotExist
from django.template import Context
from patterns.components.utils import camel_to_snake, snake_to_camel

registry = {}


def register_class(target_class):
    registry[target_class.__name__] = target_class


class Meta(type):
    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        register_class(cls)
        return cls


class BaseComponent(Node):
    __metaclass__ = Meta

    def __init__(self, context, **kwargs):
        self.context = context
        self.dirname = self.get_dirname()
        self.config = self.get_config()
        self.data = self.get_data()

    def name(self):
        return camel_to_snake(self.__class__.__name__)

    def get_dirname(self):
        path = inspect.getfile(self.__class__)
        dirname = os.path.dirname(path)
        return dirname

    def get_config(self):
        try:
            with open(os.path.join(self.dirname, 'config.yaml'), 'r') as stream:
                config = yaml.load(stream)
        except IOError:
            config = {}

        return config

    def readme(self):
        try:
            with open(os.path.join(self.dirname, 'README.md'), 'r') as stream:
                self.readme = stream.read()
        except IOError:
            self.readme = ""

        return self.readme

    def set_data(self, data):
        self.data = data

    def get_data(self):

        data = {}

        if hasattr(self, 'config'):
            data.update(self.config)

        if hasattr(self, 'data'):
            data.update(self.data)

        return data

    def get_template_path(self):
        name = camel_to_snake(self.__class__.__name__)
        return '{name}/{name}.html'.format(name=name)

    def get_template(self, context):
        if self.__class__.__name__ == 'BaseComponent':
            return Template('')

        template_path = self.get_template_path()
        template = self.context.template.engine.get_template(template_path)
        return template

    def render(self, context, **kwargs):
        return self.get_template(context).render(context)


class MissingComponent(BaseComponent):
    """
    Returns a warning about missing component templates if the app is in debug mode.
    Otherwise, returns an empty string as the template for production environments.
    """
    def __init__(self, context, component_name=None):

        super(MissingComponent, self).__init__(context)
        self.component_name = component_name

    def get_template(self, context):

        text = '<strong>Missing Component: {0}</strong>'.format(self.component_name) if settings.DEBUG else ''
        template = Template(text)

        return template


def get_class(component_name):
    class_name = snake_to_camel(component_name)
    _class = None

    try:
        _class = registry[class_name]
    except KeyError:
        try:
            possible_paths = [
                os.path.join(app, 'components', component_name)
                for app in settings.INSTALLED_APPS
                if not app.startswith('django.')
            ]

            module_info = imp.find_module(component_name, possible_paths)
            module = imp.load_module(component_name, *module_info)
            print module
            _class = getattr(module, class_name)
        except (AttributeError, ImportError):
            _class = partial(MissingComponent, component_name=component_name)

    return _class
