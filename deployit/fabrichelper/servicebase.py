# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: paweloque <paweloque@gmail.com>
import os
from datetime import datetime
from fabric.api import *
from fabric.contrib.project import *
from fabric.contrib.files import upload_template
from fabric.contrib.project import *
from fabric.contrib.files import exists, sed


class BaseService(object):
    files = []
    daemons = []

    def __init__(self):
        for f in self.files:
            dest = f['destination'] % env
            f['destination'] = dest
            if dest.startswith(env.service_dir) and dest not in self.daemons:
                self.daemons.append(dest)

    def _env_to_dict(self, adict):
        for k, v in adict.items():
            adict[k] = v % env
        return adict

    def get_extra_context(self):
        return {}

    def virtualenv(self, command):
        sudo("source %s/bin/activate && %s" % (env.remote_app_path_virtualenv, command))

    def deploy(self):
        context = env.copy()
        context.update(self.get_extra_context())

        for f in self.files:
            context_file = context.copy()

            if 'extra_context' in f:
                context_file.update(f['extra_context'])

            template_dir = context_file['global_template_dir']
            if f.get('template_dir'):
                template_dir = f['template_dir']

            upload_template(f['filename'],
                            f['destination'],
                            context=context_file,
                            backup=False,
                            use_jinja=True,
                            use_sudo=True,
                            template_dir=template_dir)
        for f in self.daemons:
            sudo('chmod +x %s' % f % env)

    def restart(self):
        for f in self.daemons:
            sudo('%s restart' % f % env)


class NginxService(BaseService):
    files = [{'filename': 'nginx.conf',
              'destination': '%(nginx_conf)s/%(env_name)s.%(project_name)s.conf'}, ]
    daemons = ['/lib/systemd/system/nginx.service']


class EnvStatusService(BaseService):
    files = [{'filename': 'envstatus.json',
              'destination': '%(deploy_folder)s/%(project_name)s/%(env_name)s/%(project_name)s/static/envstatus.json'}, ]

    def deploy(self):
        # TODO: this will only work with git.
        env.envStatusLastDeployment = datetime.now().__str__()
        env.envStatusGitBranch = local("git rev-parse --abbrev-ref HEAD", capture=True)
        env.envStatusGitChecksum = local('git rev-parse HEAD', capture=True)
        env.envStatusLastCommitDate = local('git log -1 --format=%cd', capture=True)
        super(EnvStatusService, self).deploy()


class NewReclicService(BaseService):
    newrelic_ini = os.path.join('%(deploy_folder)s/%(project_name)s/%(env_name)s/newrelic.ini')
    newrelic_list = "/etc/apt/sources.list.d/newrelic.list"

    def deploy(self):
        super(NewReclicService, self).deploy()

        sudo('echo deb http://apt.newrelic.com/debian/ newrelic non-free >> %s' % self.newrelic_list)
        sudo('wget -O- https://download.newrelic.com/548C16BF.gpg | apt-key add -')
        sudo('apt-get update')
        sudo('apt-get install newrelic-sysmond')

        local_ini_path = self.newrelic_ini % env
        env['local_ini_path'] = local_ini_path
        self.virtualenv('newrelic-admin generate-config %(newrelic_key)s %(local_ini_path)s' % env)
        sed(local_ini_path, "Python Application", "%(project_name)s-%(env_name)s" % env, use_sudo=True)

    def restart(self):
        sudo('nrsysmond-config --set license_key=%(newrelic_key)s' % env)
        sudo('/etc/init.d/newrelic-sysmond restart')


class UwsgiService(BaseService):
    files = [{
        'filename': 'uwsgi.yaml',
        'destination': '%(uwsgi_conf)s/%(env_name)s.%(project_name)s.yaml'
    },
        {'filename': 'uwsgi.service.conf',
         'destination': '/etc/systemd/system/uwsgi.service'}, ]

    daemons = ['/etc/systemd/system/uwsgi.service']

    def deploy(self):
        if env.python_version.startswith('3'):
            sudo('sudo pip3 install uWSGI==2.0.15')
        else:
            sudo('sudo pip install uWSGI==2.0.15')
        sudo('mkdir /etc/uwsgi/sites -p')
        logfile = "%(deploy_folder)s/%(project_name)s/%(env_name)s/log/uwsgi_%(project_name)s_%(env_name)s.log" % env
        sudo('mkdir %(deploy_folder)s/%(project_name)s/%(env_name)s/log/ -p' % env)
        sudo('touch {}'.format(logfile))
        sudo('chmod 666 {}'.format(logfile))
        super(UwsgiService, self).deploy()

    def restart(self):
        sudo('systemctl restart uwsgi.service')
        sudo('systemctl status uwsgi.service')

class CeleryService(BaseService):
    celeryd_init_script_file_name = 'celeryd_%(project_name)s_%(env_name)s'
    celeryd_init_script_file_path = '%(service_dir)s' + celeryd_init_script_file_name
    files = [{'filename': 'celeryd_default',
              'destination': '/etc/default/celeryd_%(project_name)s_%(env_name)s'},
             {'filename': 'celeryd_initd',
              'destination': celeryd_init_script_file_path}, ]

    def deploy(self):
        super(CeleryService, self).deploy()

        command = 'update-rc.d %s defaults' % self.celeryd_init_script_file_name % env
        sudo(command)


class PhpNginxService(BaseService):
    files = [{'filename': 'php_nginx.conf',
              'destination': '%(nginx_conf)s/%(env_name)s.%(project_name)s.conf'}, ]
    daemons = ['/etc/init.d/nginx', '/etc/init.d/php5-fpm']


class FlaskUwsgiService(UwsgiService):
    files = [{'filename': 'flask_uwsgi.yaml',
              'destination': '%(uwsgi_conf)s/%(env_name)s.%(project_name)s.yaml'},
             {'filename': 'uwsgi.service.conf',
              'destination': '/etc/systemd/system/uwsgi.service'}, ]


class FlaskNginxService(NginxService):
    files = [{'filename': 'flask_nginx.conf',
              'destination': '%(nginx_conf)s/%(env_name)s.%(project_name)s.conf'}, ]
    daemons = ['/etc/init.d/nginx']


class StaticNginxService(NginxService):
    files = [{'filename': 'static_nginx.conf',
              'destination': '%(nginx_conf)s/%(env_name)s.%(project_name)s.conf'}, ]
    daemons = ['/etc/init.d/nginx']
