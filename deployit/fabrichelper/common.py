# -*- coding: utf-8 -*-
#
# ITerativ GmbH
# http://www.iterativ.ch/
#
# Copyright (c) 2012 ITerativ GmbH. All rights reserved.
#
# Created on Jul 02, 2012
# @author: maersu <me@maersu.ch>
from .taskbase import *
from .bootstrap import *
from fabric.tasks import Task

# checkforupdates = CheckForUpdates()
taillog = TailLog()
full_deploy = Deploy()
deploy = FastDeploy()
vagrant_deploy = VagrantDeploy()
flask_deploy = FlaskDeploy()
static_deploy = StaticDeploy()
deploy_services = DeployServices()
manage_py = ManagePy()
restart_services = RestartServices()
resetload = ResetLoad()
migrate = Migrate()
delete = Delete()

puppet_base_install = PuppetBaseInstall()
puppet_clone = PuppetClone()
puppet_update = PuppetUpdate()
puppet_project_apply = PuppetProjectApply()
puppet_env_apply = PuppetEnvApply()
update_system = UpdateSystem()
roottoadmin = RootToAdmin()
loadbackup = LoadBackup()

letsencrypt_create_certificate = LetsEncryptCreateCertificate()
letsencrypt_renew_certificates = LetsEncryptRenewCertificates()


class BootstrapVagrantTask(Task):
    """
    bootstraps complete vagrant env
    """
    name = 'vagrant_bootstrap'

    @calc_duration
    def run(self):
        puppet_base_install.run()
        puppet_project_apply.run()
        puppet_env_apply.run()
        vagrant_deploy.run()

vagrant_bootstrap = BootstrapVagrantTask()
