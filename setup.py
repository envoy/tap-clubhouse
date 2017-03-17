#!/usr/bin/env python

from setuptools import setup

setup(name='tap-clubhouse',
      version='0.1.0',
      description='Singer.io tap for extracting data from the Clubhouse API',
      author='Kamal Mahyuddin',
      author_email='kamal@envoy.com',
      url='http://singer.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_clubhouse'],
      install_requires=[
          'singer-python>=0.2.1',
          'requests==2.12.4',
      ],
      entry_points='''
          [console_scripts]
          tap-clubhouse=tap_clubhouse:main
      ''',
      packages=['tap_clubhouse'],
      package_data = {
          'tap_clubhouse/schemas': [
              'stories.json',
          ],
      },
      include_package_data=True,
      download_url='https://github.com/envoy/tap-clubhouse/archive/0.1.0.tar.gz'
)
