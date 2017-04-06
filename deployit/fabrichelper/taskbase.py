# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: paweloque <paweloque@gmail.com>
import shutil
import tempfile
import time
import urllib
import xmlrpclib
from itertools import izip_longest

import pip
from fabric.contrib.console import confirm
from fabric.tasks import Task

from .decorators import warning, calc_duration
from .servicebase import *


class BaseTask(Task):
    def __init__(self):
        # see whether the tasks class overrides the hostslist
        try:
            self.hosts = self.__class__.hosts
        except AttributeError:
            self.hosts = env.hosts

    def ensure_virtualenv(self):
        if not exists(env.remote_app_path_virtualenv):
            sudo(
                "%(remote_virtualenv_py)s --no-site-packages --python=python%(python_version)s %(remote_app_path_virtualenv)s" % env)

    def virtualenv(self, command):
        sudo("source %s/bin/activate && %s" % (env.remote_app_path_virtualenv, command))

    def managepy(self, command):
        self.virtualenv('python -u %s/manage.py %s' % (env.remote_path(), command))

    def adjust_rights(self, user=None):
        if user is None:
            user=env.www_server_uid
        sudo("chown -R {user}:{user} {remote_app_path}".format(user=user, remote_app_path=env.remote_app_path))

    def clear_pycs(self):
        try:
            sudo("find %(remote_app_path)s -name '*.pyc' -print0|xargs -0 rm" % env)
        except:
            pass

    def load_site(self, ahost):
        print 'Load %s ...' % ahost
        try:
            f = urllib.urlopen(ahost)
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

    def update_packages(self, pip_filename='requirements.txt'):
        self.adjust_rights('root')
        self.virtualenv('pip install -r %s/%s --upgrade' % (env.remote_app_path, pip_filename))
        self.adjust_rights()

    def deploy_services(self):
        for service_klass in env.services:
            service = service_klass()
            service.deploy()
        self.adjust_rights()

    def restart_services(self):
        for service_klass in env.services:
            s = service_klass()
            s.restart()


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
        self.adjust_rights()

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

        message = ', '.join([datetime.now().strftime("%Y-%d-%y %H:%M:%S,%f"),
                             username,
                             revision,
                             revision_date,
                             message])

        sudo("echo '%s' >> %s" % (message, env.remote_path('log', 'deploy.log')))

        # newrelic support
        if env.has_key('newrelic_application_id') and env.has_key('newrelic_x_api_key'):
            context = {'application_id': env.newrelic_application_id,
                       'description': message,
                       'revision': revision_date or revision,
                       'user': username,
                       'changelog': changelog,
                       'x-api-key': env.newrelic_x_api_key}

            local(
                'curl --silent -H "x-api-key:%(x-api-key)s" -d "deployment[application_id]=%(application_id)s" '
                '-d "deployment[description]=%(description)s" -d "deployment[revision]=%(revision)s" '
                '-d "deployment[changelog]=%(changelog)s" '
                '-d "deployment[user]=%(user)s" https://rpm.newrelic.com/deployments.xml > /dev/null' % context)

    def get_current_revision(self):
        with settings(warn_only=True):
            cmd = ''
            with hide('everything'):
                if local('git status > /dev/null 2>&1', capture=True).succeeded:
                    cmd = 'git rev-parse HEAD'

                elif local('hg status > /dev/null 2>&1', capture=True).succeeded:
                    cmd = 'hg id -i'
        return local(cmd, capture=True)

    def initialize_virtualenv(self):
        self.ensure_virtualenv()
        # dependency management

        put(env.local_path(os.path.join('env', 'requirements')), env.remote_path(), use_sudo=True)
        if self.__class__.update_libs:
            self.update_packages(pip_filename=env.requirements_file)

    def create_project_directories(self):
        sudo('mkdir -p %s' % env.remote_path())
        sudo('mkdir -p %s' % env.remote_path('db'))
        sudo('mkdir -p %s' % env.remote_path('log'))

    def copy_settings_files(self):
        if os.path.exists(env.env_path('settings_local.py')):
            put(env.env_path('settings_local.py'), env.remote_path(env.project_name), use_sudo=True)
        self.copy_django_manage_file()

    def copy_django_manage_file(self):
        upload_template('manage.py',
                        '{path}/manage.py'.format(path=env.remote_path()),
                        context=env,
                        backup=False,
                        use_jinja=True,
                        use_sudo=True,
                        template_dir=env.global_template_dir)

    @calc_duration
    def run(self, no_input=False, migrate=False):

        self.create_project_directories()

        self.initialize_virtualenv()

        # sources & templates
        rsync_project(
            remote_dir=env.remote_app_path,
            local_dir=env.local_app,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )

        self.deploy_static()
        self.copy_settings_files()
        self.clear_pycs()
        self.adjust_rights()

        if self.update_libs:
            self.deploy_services()
        self.restart_services()
        self.adjust_rights()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))

        if migrate:
            Migrate().run()


class FlaskDeploy(Deploy):
    """
    Deploy flask project
    """
    name = "flask_deploy"

    @calc_duration
    def run(self, no_input=False, migrate=False):

        self.create_project_directories()

        self.initialize_virtualenv()

        # python sources
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
        self.adjust_rights()

        self.deploy_services()
        self.restart_services()
        #self.adjust_rights()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))


class StaticDeploy(Deploy):
    """
    Deploy flask project
    """
    name = "static_deploy"

    @calc_duration
    def run(self, no_input=False, migrate=False):

        self.create_project_directories()

        rsync_project(
            remote_dir=env.remote_path(),
            local_dir=env.local_path('dist'),
            delete=True,
            exclude=env.rsync_exclude,
            extra_opts='--rsync-path="sudo rsync"',
        )
        self.adjust_rights()
        self.deploy_services()
        self.restart_services()
        #self.adjust_rights()

        status_code = self.load_site("http://%s" % env.server_names[0])
        self.deploy_log(message='%s %s: HTTP status code: %s' % (env.env_name, self.__class__.name, status_code))


class FastDeploy(Deploy):
    """
    Deploy all sources to the target
    """
    name = "deploy"
    update_libs = False


class VagrantDeploy(Deploy):
    """
    Creates and updates virtualenv on vagrant but does not copy the files
    """
    name = "vagrant_deploy"
    update_libs = True

    @calc_duration
    def run(self, no_input=False):
        self.create_project_directories()
        self.initialize_virtualenv()
        self.copy_django_manage_file()

        self.deploy_services()
        self.restart_services()

        self.adjust_rights()


class DeployServices(BaseTask):
    """
    Deploy all services necessary to run this project
    """
    name = "services_deploy"

    @calc_duration
    def run(self):
        self.deploy_services()


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
        self.adjust_rights()


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
            backup_remote_tar_filepath = backup_remote_path + '.tar.gz'
            backup_local_tar_filepath = env.backup_local_path + '.tar.gz'

            if not exists(backup_remote_tar_filepath, use_sudo=True):
                backup_remote_dir, backup_remote_file_basename = os.path.split(backup_remote_path)
                tar_command = 'tar -C {} -czf {} {}'.format(backup_remote_dir, backup_remote_tar_filepath, backup_remote_file_basename)
                sudo(tar_command)

            get(backup_remote_tar_filepath, backup_local_tar_filepath)
            local('tar -xf {} -C {}'.format(backup_local_tar_filepath, os.path.dirname(backup_local_tar_filepath)))

        local('python %(local_src)s/manage.py loaddump --dump_path=%(backup_local_path)s' % env)


class LetsEncryptCreateCertificate(BaseTask):
    name = 'letsencrypt_create_certificate'

    @calc_duration
    def run(self, webroot=True):

        sudo('/etc/init.d/nginx stop')
        all_names = env.server_names + env.alternative_server_names
        if webroot:
            certbot_cmd = 'letsencrypt certonly --email={} --agree-tos -a webroot --webroot-path=/tmp/letsencrypt-auto -d '.format(env.ssl_email) + ' -d '.join(all_names)
        else:
            certbot_cmd = 'letsencrypt certonly --email={} --agree-tos -d '.format(env.ssl_email) + ' -d '.join(all_names)
        sudo(certbot_cmd)
        sudo('/etc/init.d/nginx start')


class LetsEncryptRenewCertificates(BaseTask):
    name = 'letsencrypt_renew_certificates'

    @calc_duration
    def run(self, force=False):
        command = 'letsencrypt renew'

        if force:
            command += ' --force'

        sudo(command)
