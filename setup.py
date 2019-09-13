#!/usr/bin/env python
import os
import setuptools
from setuptools import setup, Command
import unittest

class CleanCommand(Command):
    """Custom clean command to tidy up the project root."""
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')
 
def falx_test_suite():
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('test', pattern='test_*.py')
    return test_suite

setup(name='falx',
      version='0.1',
      description='Visualization By Example',
      author='Chenglong Wang and Yu Feng',
      author_email='',
      url='https://github.com/Mestway/falx',
      packages=setuptools.find_packages(),
      test_suite='setup.falx_test_suite',
      cmdclass={'clean': CleanCommand,})
