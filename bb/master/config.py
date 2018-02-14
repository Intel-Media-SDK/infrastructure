# Copyright (c) 2018 Intel Corporation
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
BUILD_API_LATEST = "build-api-latest"

TEST = "test"
TEST_API_LATEST = "test-api-latest"

RUN_COMMAND = "python3.6"
WORKERS = {BUILD: {"b-1-10": {},
                  "b-1-14": {}},
           TEST: {"t-1-17": {},
                  "t-1-16": {}}}

BUILD_TYPE = "release"

PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media SDK"

POLL_INTERVAL = 10 # Poll Github for new changes (in seconds)

WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD
DATABASE_URL = f"postgresql://buildbot:{DATABASE_PASSWORD}@localhost/buildbot"
GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN
GITHUB_WEBHOOK_SECRET = msdk_secrets.GITHUB_WEBHOOK_SECRET
GITHUB_OWNER = "Intel-Media-SDK"

CURRENT_MODE = Mode.PRODUCTION_MODE
#CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    GITHUB_OWNERS_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.TEST_MODE:
    DATABASE_URL = "sqlite:///state.sqlite" # Only for test mode
    GITHUB_OWNERS_REPO = "flow_test"
    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit(f"Mode {CURRENT_MODE} is not defined")

GITHUB_REPOSITORY = f"{GITHUB_OWNER}/{GITHUB_OWNERS_REPO}"
REPO_URL = f"https://github.com/{GITHUB_REPOSITORY}"
REPO_INFO = f"{GITHUB_OWNERS_REPO}:%(prop:branch)s:%(prop:revision)s"
