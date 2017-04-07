# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: maersu <me@maersu.ch>

from fabric.api import env
import os
from fabric.tasks import Task


class EnvTask(Task):

    def __init__(self, *args, **kwargs):
        super(EnvTask, self).__init__(*args, **kwargs)
        # monkey patch run task to execute env calculations
        self.__run = self.run
        self.run = self._run_wrapper
        env.use_ssh_config = True
        # set env variables
        env.user = 'root'
        env.rsync_exclude = ['settings_local.py',
                             'settings_local.example.py',
                             '.svn/',
                             '.git/',
                             '.hg/',
                             'runserver.sh',
                             'CACHE/'
                             '.keep',
                             '*.pyc',
                             '*.log',
                             '*.db',
                             '*.dat']
        env.project_name = None
        env.server_names = None
        env.alternative_server_names = []
        env.deploy_folder = '/srv/www'
        env.env_name = None
        env.nginx_port = 80
        env.www_server_uid = 'www-data'
        env.remote_app_base = '%(deploy_folder)s/%(project_name)s/%(env_name)s'
        env.global_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_templates')
        env.nginx_conf = '/etc/nginx/sites-enabled'
        env.nginx_no_follow = False
        env.uwsgi_conf = '/etc/uwsgi/apps-enabled'
        env.hosts = []
        env.services = []
        env.requirements_file = "requirements.txt"
        env.remote_virtualenv_py = 'virtualenv'
        env.python_version = '2.7'
        env.service_dir = '/etc/init.d/'
        env.backup_remote_path = '/var/backups/postgres/pgbackup/'
        env.ssl_email = 'info@iterativ.ch'
        # settings for puppet
        env.puppet_temp_dir = '~/puppettmp/'
        env.puppet_dir = '~/puppet/'
        env.project_manifest = 'project.pp'
        env.environment_manifest = 'env.pp'
        env.not_allowed_tasks = []
        env.debug = False
        env.uwsgi_count = 4

    def dynamic_env(self):
        # helper methods
        env.local_path = lambda *args: os.path.join(os.path.abspath(os.getcwd()), '..', *args)
        env.remote_path = lambda *args: os.path.join(env.remote_app_path, *args)
        env.env_path = lambda *args: os.path.join(os.path.abspath(os.getcwd()), env.env_name, *args)
        # attr path
        env.remote_app_path = env.remote_app_base % {
            'deploy_folder': env.deploy_folder,
            'project_name': env.project_name,
            'env_name': env.env_name
        }
        env.remote_app_path_virtualenv = os.path.join(env.remote_app_path, env.project_name + "-env")
        env.local_app = env.local_path('src', env.project_name)
        env.local_src = env.local_path('src')
        env.local_static_root = env.local_path(env.local_app, 'static')

        if not 'database_backup_name' in env:
            env.database_backup_name = '%s_%s.sql' % (env.project_name, env.env_name)

        if not 'settings_module' in env:
            env.settings_module = env.project_name + ".settings"

    def _run_wrapper(self):
        self.__run()
        self.dynamic_env()
