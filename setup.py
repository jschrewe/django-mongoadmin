#!/usr/bin/env python

from distutils.core import setup

setup(name='mongoadmin',
    version='0.1c',
    description="A replacement for django's admin that works with mongodb.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com',
    packages=['mongoadmin', 'mongoadmin.templatetags',],
    package_data={
        'mongoadmin': ['templates/admin/*'],
    },
)