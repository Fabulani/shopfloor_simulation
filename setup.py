from setuptools import setup
import os
import sys

_here = os.path.abspath(os.path.dirname(__file__))

if sys.version_info[0] < 3:
    with open(os.path.join(_here, 'README.md')) as f:
        long_description = f.read()
else:
    with open(os.path.join(_here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

version = {}
with open(os.path.join(_here, 'shopfloor_simulation', 'version.py')) as f:
    exec(f.read(), version)

setup(
    name='shopfloor_simulation',
    version=version['__version__'],
    description=(
        'Simulate shopfloor scenarios with a state machine and MQTT communication.'),
    long_description=long_description,
    author='Fabiano J. M. Manschein',
    author_email='fabianomanschein2@gmail.com',
    url='https://github.com/Fabulani/shopfloor_simulation',
    license='MPL-2.0',
    packages=['shopfloor_simulation'],
    #   no dependencies in this example
    #   install_requires=[
    #       'dependency==1.2.3',
    #   ],
    #   no scripts in this example
    #   scripts=['bin/a-script'],
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3.6'],
)
