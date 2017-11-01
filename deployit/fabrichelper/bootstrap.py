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
from fabric.tasks import Task
from fabric.operations import sudo
from fabric.contrib.files import exists
import os
from fabric.api import env
from .decorators import calc_duration, warning


class PuppetBaseTask(Task):

    def base_install(self):
        # set locale
        sudo('locale-gen --purge en_US.UTF-8')

        # set UTF-8 locale for future connections
        sudo('rm -f /etc/default/locale')
        sudo('echo -e "LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8\nLC_CTYPE=en_US.UTF-8\nLANGUAGE=en_US.UTF-8" >> /etc/default/locale')

        sudo('apt-get -y install git')
        sudo('apt-get -y install puppet-common')

        # get rid of missing hiera file warning
        if not exists('/etc/puppet/hiera.yaml'):
            sudo('touch /etc/puppet/hiera.yaml')

        sudo('puppet module install puppetlabs-stdlib --version 4.12.0 --force')
        sudo('puppet module install puppetlabs-vcsrepo --version 1.3.2 --force')
        sudo('puppet module install puppetlabs-concat --version 2.2.0 --force')
        sudo('puppet module install puppetlabs-apt --version 2.2.2 --force')
        sudo('puppet module install puppetlabs-firewall --version 1.8.1 --force')
        sudo('puppet module install attachmentgenie-ufw --version 1.4.9 --force')
        sudo('puppet module install puppetlabs-ntp --version 4.2.0 --force')
        sudo('puppet module install saz-timezone --version 3.3.0 --force')
        sudo('puppet module install puppetlabs-postgresql --version 4.8.0 --force')
        sudo('puppet module install puppetlabs-mysql --version 3.10.0 --force')
        sudo('puppet module install puppetlabs-inifile --version 1.5.0 --force')

        sudo('puppet module install puppetlabs-rabbitmq --version 5.6.0 --force')
        sudo('puppet module install puppetlabs-mongodb --version 0.14.0 --force')
        sudo('puppet module install puppetlabs-haproxy --version 1.5.0 --force')
        sudo('puppet module install puppetlabs-ruby --version 0.5.0 --force')
        sudo('puppet module install puppet-nodejs --version 2.0.1 --force')

        sudo('puppet module install jamtur01-httpauth --version 0.0.3 --force')
        sudo('puppet module install thias-postfix --version 0.3.4 --force')
        sudo('puppet module install puppetlabs-apache --version 1.10.0 --force')

        sudo('puppet module install petems-swap_file --version 3.0.2 --force')
        sudo('puppet module install tmont-rethinkdb --version 0.1.0 --force')

        sudo('puppet module install elastic-elasticsearch --version 5.3.1')
        # sudo('puppet module install elasticsearch-elasticsearch --version 0.10.3 --force')
        # sudo('puppet module install jfryman-nginx --version 0.0.10 --force')

    def clone_modules(self):
        # the hg clone uses the ssh method which requires a correct certificate
        if exists(env.puppet_temp_dir):
            sudo('rm -rf %s' % env.puppet_temp_dir)
        sudo('git clone git://github.com/iterativ/puppet-modules.git {0}'.format(env.puppet_temp_dir))
        self.update_modules()

    def update_modules(self):
        with cd(env.puppet_temp_dir):
            sudo('git pull; git checkout %s' % env.puppet_branch_name)
        self.copy_modules()

    def create_dir_when_not_exists(self, path):
        if not exists(path):
            sudo('mkdir -p %s' % path)

    def copy_modules(self):
        sudo('cp -r %s/modules/iterativ/* /etc/puppet/modules' % env.puppet_temp_dir)

        self.create_dir_when_not_exists(env.puppet_dir)

    def puppet_project_apply(self):
        project_dir = os.path.join(env.puppet_dir, env.project_name)
        self.create_dir_when_not_exists(project_dir)
        put(env.project_manifest, project_dir, use_sudo=True)

        with cd(project_dir):
            sudo('puppet apply %s' % env.project_manifest)

    def puppet_env_apply(self):
        env_dir = os.path.join(env.puppet_dir, env.project_name, env.env_name)
        self.create_dir_when_not_exists(env_dir)
        env_puppet_file = os.path.join(env.env_name, env.environment_manifest)
        put(env_puppet_file, env_dir, use_sudo=True)

        with cd(env_dir):
            sudo('puppet apply %s' % env.environment_manifest)

    def update_upgrade(self):
        sudo('apt-get update -y')
        # do not update grup as it requires manual intervention
        with settings(warn_only=True):
            sudo('apt-mark hold grub2-common grub-pc grub-pc-bin -qq')
        sudo('apt-get full-upgrade -y')
        sudo('apt-get autoremove')


class PuppetBaseInstall(PuppetBaseTask):
    """
    Installs all puppet prerequisites and sets new Ubuntu repository locations for some package backports
    """
    name = 'puppet_base_install'

    @calc_duration
    def run(self):
        self.update_upgrade()
        self.base_install()

        self.clone_modules()


class PuppetClone(PuppetBaseTask):
    """
    Clone the git repo with all puppet modules and root manifests
    """
    name = 'puppet_clone'

    @calc_duration
    def run(self):
        self.clone_modules()


class PuppetUpdate(PuppetBaseTask):
    """
    Update puppet modules and root manifests
    """
    name = 'puppet_update'

    @calc_duration
    def run(self):
        self.update_modules()


class PuppetProjectApply(PuppetBaseTask):
    """
    Apply the puppet project manifest
    """
    name = 'puppet_project_apply'

    @calc_duration
    def run(self):
        self.puppet_project_apply()


class PuppetEnvApply(PuppetBaseTask):
    """
    Apply the environment specific manifest
    """
    name = 'puppet_env_apply'

    @calc_duration
    def run(self):
        self.puppet_env_apply()


class UpdateSystem(PuppetBaseTask):
    """
    Installs the newest packes (via update, upgrade). (Does not call sysupgarde)
    """
    name = 'update_system'

    @calc_duration
    def run(self):
        self.update_upgrade()


class RootToAdmin(Task):
    """
    Disable Root Login and create a new custom admin user with his own ssh key

    Run this command as priveleged user as it creates the new admin user (and disables root)
    e.g.: fab cloudsigma roottoguru:root

    Run other commands:
        fab vagrant taillog  -i /Users/user/.ssh/host.pem

    or put in your ~/.ssh/config:
        Host=192.168.33.11
        HostName=192.168.33.11
        User=newadmin #same as in your env python file
        IdentityFile=/Users/user/.ssh/host.pem

    """
    name = "roottoadmin"

    @warning
    @calc_duration
    def run(self, user):
        evn_user_old = env.user
        env.user = user

        path = os.path.expanduser(os.path.join('~/Desktop/', env.env_name))
        keys_path = '/home/%s/.ssh/' % evn_user_old
        authorized_keys = os.path.join(keys_path, 'authorized_keys')
        local_user_pp = env.env_path('user.pp')
        tmp_path = '/home/%s/id_rsa.pup' % evn_user_old
        pem_path = '%s.pem' % path

        if not os.path.exists(local_user_pp):
            print('\nNo {} found. Exit.\n'.format(local_user_pp))
            return 1

        print('Run command as {}...'.format(env.user))

        put(local_user_pp, 'user.pp', use_sudo=True)
        sudo('puppet apply user.pp')

        if os.path.exists(pem_path):
            warn('\x1b[5;31m%s\x1b[0;39m already exists.' % pem_path)
            prompt("Enter 'c' to overwrite", validate=r'c$')

        local('ssh-keygen -t rsa -f %s' % path)
        local('mv %s %s' % (path, pem_path))

        if not exists(keys_path):
            sudo('mkdir -p %s' % keys_path)

        put(path+'.pub', tmp_path, use_sudo=True)

        sudo('cat %s >> %s' % (tmp_path, authorized_keys))
        sudo('rm %s' % tmp_path)

        sudo('chown -R %(user)s:%(user)s %(path)s' % {'user': evn_user_old, 'path': keys_path})
        env.user = evn_user_old
        print('\n\x1b[32mATTENTION: Please backup new private Key {}.pem \x1b[0;39m\n'.format(path))


