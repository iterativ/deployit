# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: maersu <me@maersu.ch>
from fabric.api import *
from fabric.api import env
import time


def warning(f):
    def new_f(*args, **kwargs):
        warn('Executing task \x1b[5;31m%s\x1b[0;39m on \x1b[5;31m%s\x1b[0;39m environment' % (args[0].name, env.env_name))
        prompt("Enter 'c' to continue", validate=r'c$')
        f(*args, **kwargs)
    return new_f


def production(f):
    def new_f(*args, **kwargs):
        warn('\033[31m Executing task on production environment?\x1b[0;39m')
        prompt("Enter 'yes' to continue", validate=r'yes$')
        f(*args, **kwargs)
    return new_f


def calc_duration(f):
    def new_f(*args, **kwargs):
        t1 = time.time()
        f(*args, **kwargs)
        print("Command took \x1b[32m%.2fs\x1b[0;39m" % (time.time() - t1))
    return new_f
