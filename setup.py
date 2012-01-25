#!/usr/bin/env python

from distutils.core import setup
from subprocess import call

def convert_readme():
    try:
        call(["pandoc", "-t",  "rst", "-o",  "README.txt", "readme.md"])
    except OSError:
        pass
    return open('README.txt').read()

setup(name='mongoadmin',
    version='0.1.2',
    description="A replacement for django's admin that works with mongodb.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com/projects/mongo-admin/',
    packages=['mongoadmin', 'mongoadmin.templatetags',],
    package_data={
        'mongoadmin': ['templates/admin/*'],
    },
    license='New BSD License',
    long_description=convert_readme(),
)