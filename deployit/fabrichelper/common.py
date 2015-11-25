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
from fabric.tasks import Task

puppet_apply = PuppetApply()

full_deploy = Deploy()
deploy = FastDeploy()
flask_deploy = FlaskDeploy()
static_deploy = StaticDeploy()

manage_py = ManagePy()
restart_services = RestartServices()
resetload = ResetLoad()
migrate = Migrate()
delete = Delete()
loadbackup = LoadBackup()
checkforupdates = CheckForUpdates()
taillog = TailLog()
