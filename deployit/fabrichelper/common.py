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
#from .dnstasks import *
from fabric.tasks import Task

checkforupdates = CheckForUpdates()
taillog = TailLog()
full_deploy = Deploy()
deploy = FastDeploy()
vagrant_deploy = VagrantDeploy()
deploy_services = DeployServices()
deploy_ssl_certs = DeploySSLCerts()
restart_services = RestartServices()
resetload = ResetLoad()
delete = Delete()

puppet_base_install = PuppetBaseInstall()
puppet_clone = PuppetClone()
puppet_update = PuppetUpdate()
puppet_project_apply = PuppetProjectApply()
puppet_env_apply = PuppetEnvApply()
update_system = UpdateSystem()
roottoadmin = RootToAdmin()
loadbackup = LoadBackup()

# dns_create_standard_domain = DNSCreateNewStandardDomain()
# dns_add_cname_subdomain = DNSAddCNAMESubdomain()
# dns_migrate_domain_to_new_ip_address = DNSMigrateDomainToNewIPAddress()
# dns_delete_record_from_domain = DNSDeleteRecordFromDomain()
# dns_add_record_subdomain = DNSAddRecordSubdomain()


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