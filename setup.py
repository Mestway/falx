#!/usr/bin/env python
import os
from setuptools import setup, Command

class CleanCommand(Command):
    """Custom clean command to tidy up the project root."""
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')
 
setup(name='falx',
      version='0.1',
      description='Visualization By Example',
      author='Chenglong Wang and Yu Feng',
      author_email='',
      url='https://github.com/Mestway/falx',
      packages=['falx'],
      cmdclass={'clean': CleanCommand,})
