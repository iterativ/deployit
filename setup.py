# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: DanEEStar <daniel.egger@gmail.com>

import os
from distutils.command.install import INSTALL_SCHEMES
from distutils.core import setup

packages = []
data_files = []
root_dir = 'deployit'


def fullsplit(path, result=None):
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

ch_dir = os.path.dirname(__file__)
if ch_dir != '':
    os.chdir(ch_dir)

for dirpath, dirnames, filenames in os.walk(root_dir):
    # Ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.'): del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

# Tell distutils not to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

setup(
    name='deployit',
    version='16.3.3',
    description="Iterativ GmbH DeployIt",
    author='Daniel Egger',
    author_email='daniel.egger@iterativ.ch',
    url='iterativ.ch',
    packages=packages,
    data_files=data_files,
    zip_safe=False,
    install_requires=[
        'Fabric3==1.13.1.post1',
        'Jinja2==2.8',
        'python-dateutil==2.5.3',
        'requests==2.18.1'
    ]
)
