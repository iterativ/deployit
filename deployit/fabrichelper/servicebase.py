# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: paweloque <paweloque@gmail.com>

from fabric.api import *
from fabric.contrib.project import *
from fabric.contrib.files import upload_template
import os


class BaseService(object):
    files = []
    deamons = []
    
    def __init__(self):
        for f in self.files:
            dest = f['destination'] % env
            f['destination'] = dest
            if dest.startswith(env.service_dir) and dest not in self.deamons:
                self.deamons.append(dest)

    def _env_to_dict(self, adict):
        for k, v in adict.items():
            adict[k] = v % env 
        return adict        
    
    def get_extra_context(self):
        return {}
    
    def deploy(self):
        context = env.copy()
        context.update(self.get_extra_context())
                
        for f in self.files:
            context_file = context.copy()
            
            if 'extra_context' in f:
                context_file.update(f['extra_context']) 
            
            upload_template(f['filename'], 
                            f['destination'], 
                            context=context_file, 
                            backup=False, 
                            use_jinja=True,
                            use_sudo=True,
                            template_dir=context_file['global_template_dir'])
        for f in self.deamons:
            sudo('chmod +x %s' % f % env)
    
    def restart(self):
        for f in self.deamons:
            sudo('%s restart' % f % env)


class NginxService(BaseService):
    files = [{'filename': 'nginx.conf',
              'destination': '%(nginx_conf)s/%(env_name)s.%(project_name)s.conf'}, ]
    deamons = ['/etc/init.d/nginx']


class NewReclicService(BaseService):
    files = [{'filename': 'newrelic.ini',
              'destination': os.path.join('%(deploy_folder)s/%(project_name)s/%(env_name)s', 'newrelic.ini')}, ]

    def deploy(self):
        super(NewReclicService, self).deploy()
        sudo('wget -O /etc/apt/sources.list.d/newrelic.list http://download.newrelic.com/debian/newrelic.list')
        sudo('apt-key adv --keyserver hkp://subkeys.pgp.net --recv-keys 548C16BF')
        sudo('apt-get update')
        sudo('apt-get install newrelic-sysmond')

    def restart(self):        
        sudo('nrsysmond-config --set license_key=%(newrelic_key)s' % env)
        sudo('/etc/init.d/newrelic-sysmond start')


class UwsgiService(BaseService):
    files = [{'filename': 'uwsgi.yaml',
              'destination': '%(uwsgi_conf)s/%(env_name)s.%(project_name)s.yaml'},
             {'filename': 'uwsgiemperor.conf',
              'destination': '/etc/init/uwsgiemperor.conf'}, ]

    def deploy(self):
        sudo('sudo pip install uWSGI==1.4.5')
        sudo('mkdir /etc/uwsgi/apps-enabled -p')
        super(UwsgiService, self).deploy()

    def restart(self):
        #sudo('sudo stop uwsgiemperor')
        sudo('initctl start uwsgiemperor || initctl restart uwsgiemperor')


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
    deamons = ['/etc/init.d/nginx', '/etc/init.d/php5-fpm']
