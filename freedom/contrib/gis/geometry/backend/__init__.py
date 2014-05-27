from importlib import import_module

from freedom.conf import settings
from freedom.core.exceptions import ImproperlyConfigured

geom_backend = getattr(settings, 'GEOMETRY_BACKEND', 'geos')

try:
    module = import_module('freedom.contrib.gis.geometry.backend.%s' % geom_backend)
except ImportError:
    try:
        module = import_module(geom_backend)
    except ImportError:
        raise ImproperlyConfigured('Could not import user-defined GEOMETRY_BACKEND '
                                   '"%s".' % geom_backend)

try:
    Geometry = module.Geometry
    GeometryException = module.GeometryException
except AttributeError:
    raise ImproperlyConfigured('Cannot import Geometry from the "%s" '
                               'geometry backend.' % geom_backend)
