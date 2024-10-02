import pytest

import django
from packaging import version

def skip_unless_django_5(func):
    return pytest.mark.skipif(
        version.parse(django.get_version()) < version.parse("5.0"),
        reason="Skipping test: Django version 5 is required."
    )(func)
