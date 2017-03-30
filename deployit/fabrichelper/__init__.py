# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: maersu <me@maersu.ch>
from functools import reduce
from fabric.api import env
from fabric.tasks import _execute as _execute_ori
from fabric.utils import abort
import fabric
import fabric.main
import sys


##########################################################
# Monkey patch the _execute method to exclude specific tasks
###
def _execute_wrapper(*args, **kwargs):
    from fabric.main import parse_options, parse_arguments
    parser, options, arguments = parse_options()
    arguments = parser.largs
    # build a list intersection
    not_allowed_tasks = list(set([a[0] for a in parse_arguments(arguments)]) & set(env.not_allowed_tasks))
    
    if len(not_allowed_tasks):
        abort('Task execution not allowed: %s' % ', '.join(not_allowed_tasks))
        sys.exit(1)
    _execute_ori(*args, **kwargs)

fabric.tasks._execute = _execute_wrapper


#############################################
# Monkey patch the fab help. 
# Distinguish between tasks and environments.
###
def _normal_list_pp(docstrings=True):

    from fabric.main import _print_docstring, indent, _task_names
    from .environments import EnvTask
    from fabric import state

    result = []

    def _pp(names):
        # Want separator between name, description to be straight col
        max_len = reduce(lambda a, b: max(a, len(b)), names, 0)
        sep = '  '
        trail = '...'
        for name in names:
            output = None
            docstring = _print_docstring(docstrings, name)
            if docstring:
                lines = filter(None, docstring.splitlines())
                first_line = lines[0].strip()
                # Truncate it if it's longer than N chars
                size = 75 - (max_len + len(sep) + len(trail))
                if len(first_line) > size:
                    first_line = first_line[:size] + trail
                output = name.ljust(max_len) + sep + first_line
            # Or nothing (so just the name)
            else:
                output = name
            result.append(indent(output))

    env_task = {}
    commands = {}

    for c, instance in state.commands.items():
        if issubclass(instance.__class__, EnvTask):
            env_task[c] = instance
        else:
            commands[c] = instance

    if len(env_task) > 0:
        SECTION = '\033[92m%s\033[0m'
        result.append(SECTION % '[Environments]')
        _pp(_task_names(env_task))
        result.append(SECTION % '\n[Tasks]')
    _pp(_task_names(commands))

    return result

fabric.main._normal_list = _normal_list_pp
