"""
Setup script for flask_filters.
"""
from setuptools import setup

if __name__ == '__main__':
    setup(name='flask_viewunit',
          py_modules=['flask_viewunit', 'tests'],
          install_requires=['flask', 'html5lib', 'mock', 'nose'],
          version='1.0',
          description='Unit testing for Flask views',
          url='https://github.com/wingu/flask_viewunit',
          classifiers=['Development Status :: 5 - Production/Stable',
                       'License :: OSI Approved :: BSD License',
                       'Programming Language :: Python :: 2'])
