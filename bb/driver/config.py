# Copyright (c) 2019 Intel Corporation
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

from bb.utils import Mode, CIService
from bb import factories

from common import msdk_secrets
from common.helper import Product_type, Build_type
from common.mediasdk_directories import OsType

CI_SERVICE = CIService.DRIVER
CURRENT_MODE = Mode.PRODUCTION_MODE

TRIGGER = 'trigger'
PYTHON_EXECUTABLE = {OsType.linux: r'python3'}

# Give possibility to enable/disable auto deploying infrastructure on workers
DEPLOYING_INFRASTRUCTURE = True

FACTORIES = factories.Factories(CURRENT_MODE, DEPLOYING_INFRASTRUCTURE,
                                PYTHON_EXECUTABLE, CI_SERVICE)

MEDIASDK_ORGANIZATION = "Intel-Media-SDK"
PRODUCT_CONFIGS_REPO = "product-configs"

DRIVER_ORGANIZATION = 'intel'
DRIVER_REPO = 'media-driver'

PRODUCTION_REPOS = [PRODUCT_CONFIGS_REPO, DRIVER_REPO]

"""
Specification of BUILDERS:
"name"              - name of build in Buildbot UI
"product_conf_file" - product_config which should be used
"product_type"      - Product type (all available types can be found in `common/helper.py`)
"build_type"        - type of build (for example: "release")
"api_latest"        - if `True` it will enable product`s `api_latest` feature
"compiler"          - compiler which should be used (env and product_config should support this key)
"compiler_version"  - version of compiler
"worker"            - worker(s) which should be used from `WORKERS`
"triggers"          - list of dicts with following keys:
    "branches"      - function takes one argument (branch)
                      function must return True if builder should be activated, otherwise False
    "repositories"  - list of repositories (str)
    "builders"      - list of builder names (str)
                      builder will be run only if all builds of specified "builders" passed  
"""

# All builders will use Triggerable scheduler by default
# To disable default scheduler add "add_triggerable_sheduler": False in builder dict
BUILDERS = {

    TRIGGER: {"factory": FACTORIES.init_trigger_factory,
              # SingleBranchScheduler will be used for this builder (see master.py), so default
              # Triggerable is not needed
              "add_triggerable_sheduler": False},

    "build-libva": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_libva.py",
        "product_type": Product_type.PUBLIC_LINUX_LIBVA.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'libva',
        # Builder is enabled for all branches
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True}]
    },

    "build-gmmlib": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_gmmlib.py",
        "product_type": Product_type.PUBLIC_LINUX_GMMLIB.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'gmmlib',
        # Builder is enabled for all branches
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True}]
    },

    "build-ffmpeg": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "driver/conf_ffmpeg.py",
        "product_type": Product_type.PUBLIC_LINUX_FFMPEG.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'ffmpeg',
        # Builder is enabled for all branches
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True}]
    },

    "build-metrics-calc": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "driver/conf_metrics_calc.py",
        "product_type": Product_type.PUBLIC_LINUX_METRICS_CALC.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'metrics_calc_lite',
        # Builder is enabled for all branches
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True}]
    },

    "build": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "driver/conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # TODO: create class for triggers
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True,
                      'builders': ['build-libva', 'build-gmmlib']}]
    },

    "test": {
        "factory": FACTORIES.init_driver_test_factory,
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "centos_test",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda x: True,
                      'builders': ['build', 'build-ffmpeg', 'build-metrics-calc']}]
    }
}

FLOW = factories.Flow(BUILDERS, FACTORIES)

WORKER_PASS = msdk_secrets.WORKER_PASS
WORKERS = {
    "centos": {
        "b-1-14": {"os": OsType.linux},
        "b-1-23": {"os": OsType.linux}
    },
    "centos_test": {
        "t-1-17": {"os": OsType.linux}
    }
}


PORT = "6000"
WORKER_PORT = "6100"
BUILDBOT_NET_USAGE_DATA = None # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media Driver"

# Don't decrease the POLL_INTERVAL, because Github rate limit can be reached
# and new api requests will not be performed
POLL_INTERVAL = 60 # Poll Github for new changes (in seconds)

DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD
DATABASE_URL = f"postgresql://buildbot:{DATABASE_PASSWORD}@localhost/driver_buildbot"

REPO_URL = f'https://github.com/{DRIVER_ORGANIZATION}/{DRIVER_REPO}'

GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN

BUILDBOT_URL = "http://mediasdk.intel.com/driver/"
