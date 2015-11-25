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
from fabric.contrib.console import confirm
from fabric.contrib.project import *
from fabric.contrib.files import exists, upload_template
from fabric.api import env
from fabric.tasks import Task
from .decorators import warning, calc_duration
import tempfile
import datetime
import time
import shutil
import urllib2, ssl
import xmlrpclib
import pip
import os
from itertools import izip_longest

class BaseTask(Task):
    def __init__(self):
        # see whether the tasks class overrides the hostslist
        try:
            self.hosts = self.__class__.hosts
        except AttributeError:
            self.hosts = env.hosts

    def virtualenv(self, command):
        sudo("source %s/bin/activate && %s" % (env.remote_app_path_virtualenv, command))

    def managepy(self, command):
        self.virtualenv('python -u %s/manage.py %s' % (env.remote_path(), command))

    def clear_pycs(self):
        try:
            sudo("find %(remote_app_path)s -name '*.pyc' -print0|xargs -0 rm" % env)
        except:
            pass

    def copy_django_files(self):
        if os.path.exists(env.env_path('settings_local.py')):
            put(env.env_path('settings_local.py'), env.remote_path(env.project_name), use_sudo=True)

        upload_template('manage.py',
                        '{path}/manage.py'.format(path=env.remote_path()),
                        context=env,
                        backup=False,
                        use_jinja=True,
                        use_sudo=True,
                        template_dir=env.global_template_dir)

    def load_site(self, ahost):
        print 'Load %s ...' % ahost
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            f = urllib2.urlopen(ahost, context=ssl_context)
            f.read()
            http_code = f.getcode()
            msg = 'HTTP status code: %s' % http_code
            if http_code != 200:
                print 'ERROR %s' % msg
            else:
                print msg
            return http_code
        except Exception, e:
            print 'EXCEPTION: Could not load site: %s' % (e)

    def get_current_revision(self):
        with settings(warn_only=True):
            cmd = ''
            with hide('everything'):
                if local('git status > /dev/null 2>&1', capture=True).succeeded:
                    cmd = 'git rev-parse HEAD'

                elif local('hg status > /dev/null 2>&1', capture=True).succeeded:
                    cmd = 'hg id -i'
        return local(cmd, capture=True)

    def update_packages(self, pip_filename='requirements.txt'):
        if self.__class__.update_libs:
            self.virtualenv('pip install -r %s --upgrade' %
                env.remote_path(env.project_name, 'requirements', pip_filename))

    def restart_services(self):
        for service in env.services:
            sudo("service %s restart" % service)

class PuppetApply(BaseTask):
    """
    Applies the puppet manifests
    """
    name = 'puppet_apply'

    @calc_duration
    def run(self):
        sudo('rpm -qa | grep puppetlabs || rpm -Uvh https://yum.puppetlabs.com/puppetlabs-release-el-7.noarch.rpm')
        sudo('which git puppet || yum -y install puppet git')
        sudo('test -f /usr/local/bin/librarian-puppet || gem install --verbose librarian-puppet')

        rsync_project(
            remote_dir='/etc/puppet/',
            local_dir=env.puppet_manifests,
            delete=True,
            exclude=['modules/components'],
            extra_opts='--rsync-path="sudo rsync"',
        )

        with cd('/etc/puppet'):
            sudo('/usr/local/bin/librarian-puppet install')
            sudo("FACTER_role_class=%s puppet apply --environment=%s --modulepath=/etc/puppet/modules/components:/etc/puppet/modules/profiles:/etc/puppet/modules/roles /etc/puppet/manifests/default.pp" % (env.project_name,env.puppet_env))

class Deploy(BaseTask):
    """
    Deploy all sources to the target and update libraries
    """
    name = "full_deploy"
    update_libs = True

    def deploy_static(self):
        local('python %(local_src)s/manage.py collectstatic --noinput' % env)
        rsync_project(
            remote_dir=env.remote_path(env.project_name),
            local_dir=env.local_static_root,
            delete=True,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )
        shutil.rmtree(env.local_static_root)
        self.update_packages(pip_filename=env.requirements_file)

    def deploy_log(self, message):
        import getpass
        import dateutil.parser
        import socket

        try:
            username = getpass.getuser() + '@' + socket.gethostname()
        except:
            username = getpass.getuser()

        revision = self.get_current_revision()

        try:
            revision_date = local('git show -s --format="%ci" ' + revision, capture=True)
            revision_date = dateutil.parser.parse(revision_date).strftime("%H:%M %d.%b")
            changelog = local('git status', capture=True).replace("'", "\\'").replace('"', '\\"')
        except:
            revision_date = ''
            changelog = ''

        message = ', '.join([datetime.datetime.now().strftime("%Y-%d-%y %H:%M:%S,%f"),
                             username,
                             revision,
                             revision_date,
                             message])

        sudo("echo '%s' >> %s" % (message, env.remote_path('log', 'deploy.log')))

    @calc_duration
    def run(self, no_input=False, migrate=False):
        # sources & templates
        rsync_project(
            remote_dir=env.remote_app_path,
            local_dir=env.local_app,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )

        self.deploy_static()
        self.copy_django_files()
        self.clear_pycs()
        self.restart_services()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))

        if migrate:
            Migrate().run()


class FastDeploy(Deploy):
    """
    Deploy all sources to the target
    """
    name = "deploy"
    update_libs = False


class FlaskDeploy(Deploy):
    """
    Deploy flask project
    """
    name = "flask_deploy"

    @calc_duration
    def run(self, no_input=False, migrate=False):
        rsync_project(
            remote_dir=env.remote_path(),
            local_dir=env.local_path('pythonsrc'),
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )

        rsync_project(
            remote_dir=env.remote_path(),
            local_dir=env.local_path('dist'),
            delete=True,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )
        self.clear_pycs()
        self.restart_services()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))


class StaticDeploy(Deploy):
    """
    Deploy static project
    """
    name = "static_deploy"

    @calc_duration
    def run(self, no_input=False, migrate=False):
        rsync_project(
            remote_dir=env.remote_path(),
            local_dir=env.local_path('dist'),
            delete=True,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )
        self.restart_services()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))


class RestartServices(BaseTask):
    """
    Restart all services necessary to run this project
    """
    name = "services_restart"

    @calc_duration
    def run(self):
        self.restart_services()


class ManagePy(BaseTask):
    """
    Run djagno manage command Usage: fab <env> manage:<command>
    """
    name = "manage"

    @calc_duration
    def run(self, command_name=''):
        with cd(env.remote_path()):
            self.virtualenv('python -u manage.py %s' % (command_name, ))


class ResetLoad(BaseTask):
    """
    Reset database
    """
    name = "resetload"

    @warning
    @calc_duration
    def run(self, no_input=False):
        with cd(env.remote_path()):
            self.virtualenv('python -u manage.py resetload')


class Migrate(BaseTask):
    """
    South Migration Usage: fab <env> migrate:<appname>
    """
    name = "migrate"

    @calc_duration
    def run(self, args=''):
        with cd(env.remote_path()):
            self.virtualenv('python -u manage.py migrate %s' % args)


class TailLog(BaseTask):
    """
    Show log file
    """
    name = "taillog"

    def run(self, no_input=False):
        sudo('tail -f %s --lines=30' % env.remote_path('log', '%(project_name)s.log' % env))


class CheckForUpdates(BaseTask):
    """
    Check if there are some package updates available (current activated env)
    """
    name = "check_for_updates"

    def compare_version(self, version_local, version_remote):
        status = 0
        for l, r in izip_longest(version_local.split('.'), version_remote.split('.')):
            if l is None:
                status = 1
                break
            elif r is None:
                status = 2
                break

            if l.isdigit() and r.isdigit():
                l = int(l)
                r = int(r)
            if l < r:
                status = 1
                break
            elif l > r:
                status = 2
                break
        if status == 1:
            return '\x1b[0;32m%s available\x1b[0;39m' % version_remote
        elif status == 2:
            return 'ahead (%s >= %s)' % (version_local, version_remote)
        else:
            return 'up to date'

    @calc_duration
    def run(self):
        pypi = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        print 'check for updates (local):\n'
        for dist in pip.get_installed_distributions():
            available = pypi.package_releases(dist.project_name)
            if not available:
                # Try to capitalize pkg name
                available = pypi.package_releases(dist.project_name.capitalize())
            if not available:
                # Try to lower
                available = pypi.package_releases(dist.project_name.lower())

            if not available:
                msg = 'no releases at pypi'
            else:
                msg = self.compare_version(dist.version, available[0])
            pkg_info = '{dist.project_name} {dist.version}'.format(dist=dist)
            print '\t{pkg_info:40} {msg}'.format(pkg_info=pkg_info, msg=msg)


class Delete(BaseTask):
    """
    Delete all files
    """
    name = "delete"

    @warning
    @calc_duration
    def run(self):
        sudo('rm -rf %(remote_app_path)s' % env)
        # now we have to delete all the files created for the services
        # iterate over services and call their cleanup functions
        #for service_klass in env.services:
        #    service = service_klass()


class LoadBackup(BaseTask):
    """
    load backup dump into local db (postgres or mysql only)
    """
    name = "load_backup"

    @calc_duration
    def run(self):
        backup_remote_path = os.path.join(env.backup_remote_path, env.database_backup_name)
        env.backup_local_path = os.path.join(tempfile.gettempdir(), env.database_backup_name)

        use_existing = False
        if os.path.exists(env.backup_local_path):
            use_existing = confirm(
                'Use existing backup (from %s)?' % time.ctime(os.path.getctime(env.backup_local_path)))

        if not use_existing:
            get(backup_remote_path, env.backup_local_path)

        local('python %(local_src)s/manage.py loaddump --dump_path=%(backup_local_path)s' % env)



class CreateRPM(BaseTask):
    """
    Create RPM from deployed application
    """
    name = "rpm"

    @calc_duration
    def run(self):
        pass
        #sudo('fpm %s /tmp/') % env.remote_app_path)
        #get('/tmp/%s.rpm' % env.project_name)
