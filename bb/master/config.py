# Copyright (c) 2017 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import os
from enum import Enum

import msdk_secrets

class Mode(Enum):
    PRODUCTION_MODE = "production_mode"
    TEST_MODE = "test_mode"

BUILD = "build"
BUILD_MASTER = "build-master-branch"
BUILD_NOT_MASTER = "build-other-branches"
TEST = "test"
WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD

RUN_COMMAND = "python3.6"
WORKERS = {BUILD: {"worker-build": {},
                  "b-1-14": {}},
           TEST: {"worker-test": {},
                  "t-1-16": {}}}

BUILD_TYPE = "release"

PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media SDK"

GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN
GITHUB_WEBHOOK_SECRET = msdk_secrets.GITHUB_WEBHOOK_SECRET

CURRENT_MODE = Mode.PRODUCTION_MODE
#CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    DATABASE_URL = "postgresql://buildbot:%s@localhost/buildbot" % DATABASE_PASSWORD
    GITHUB_REPOSITORY = "Intel-Media-SDK/MediaSDK"
    BUILDBOT_TITLE_URL = "https://github.com/Intel-Media-SDK/MediaSDK"
    REPO_INFO = r"MediaSDK:%(prop:branch)s:%(prop:revision)s"

    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.TEST_MODE:
    DATABASE_URL = "postgresql://buildbot:%s@localhost/buildbot" % DATABASE_PASSWORD
    GITHUB_REPOSITORY = "Intel-Media-SDK/flow_test"
    BUILDBOT_TITLE_URL = "https://github.com/Intel-Media-SDK/flow_test"
    REPO_INFO = r"flow_test:%(prop:branch)s:%(prop:revision)s"

    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit("Mode %s is not defined" % CURRENT_MODE)
