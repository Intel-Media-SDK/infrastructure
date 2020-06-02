# Copyright (c) 2020 Intel Corporation
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
import re

from bb import factories
from bb.utils import Mode, CIService, GithubCommitFilter, PACKAGES

from common import msdk_secrets
from common.helper import Product_type, Build_type
from common.mediasdk_directories import MediaSdkDirectories, OsType

# TODO: use this variable in notifications and other services
CI_SERVICE = CIService.MEDIASDK
CURRENT_MODE = Mode.PRODUCTION_MODE
# CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    MEDIASDK_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.TEST_MODE:
    MEDIASDK_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit(f"Mode {CURRENT_MODE} is not defined")

MEDIASDK_ORGANIZATION = "Intel-Media-SDK"
INFRASTRUCTURE_REPO = "infrastructure"
PRODUCT_CONFIGS_REPO = "product-configs"

INTEL_ORGANIZATION = 'intel'
DRIVER_REPO = 'media-driver'
LIBVA_REPO = 'libva'
GMMLIB_REPO = 'gmmlib'

# We haven't CI for these repositories, but we update its revisions in manifest automatically.
# This feature should work for master branch only.

AUTO_UPDATED_REPOSITORIES = [GMMLIB_REPO]

PRODUCTION_REPOS = [PRODUCT_CONFIGS_REPO, MEDIASDK_REPO, DRIVER_REPO]

PYTHON_EXECUTABLE = {OsType.linux: r'python3',
                     OsType.windows: r'py'}
TRIGGER = 'trigger'

# Give possibility to enable/disable auto deploying infrastructure on workers
DEPLOYING_INFRASTRUCTURE = True

FACTORIES = factories.Factories(CURRENT_MODE, DEPLOYING_INFRASTRUCTURE,
                                PYTHON_EXECUTABLE, CI_SERVICE, AUTO_UPDATED_REPOSITORIES)

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

    "libva": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_libva.py",
        "product_type": Product_type.PUBLIC_LINUX_LIBVA.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # TODO: rename to component_name
        "dependency_name": 'libva',
        # Builder is enabled for all branches
        # TODO: remove gmmlib as dependency
        # This is workaround to mitigate the problem with build chains scheduling, when some build
        # may not be triggered if they have 2 or more dependent builds which finished together.
        'triggers': [{'builders': ["gmmlib"],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)},
                     {'filter': GithubCommitFilter([LIBVA_REPO],
                                                   lambda branch, target_branch: True)}]
    },

    'update-manifest': {
        "factory": FACTORIES.auto_update_manifest_factory,
        "worker": "centos",
        "triggers": [{'filter': GithubCommitFilter(AUTO_UPDATED_REPOSITORIES + [LIBVA_REPO],
                                                   lambda branch, target_branch: branch == 'master')}]
    },

    "libva-utils": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_libva_utils.py",
        "product_type": Product_type.PUBLIC_LINUX_LIBVA_UTILS.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # TODO: rename to component_name
        "dependency_name": 'libva-utils',
        # Builder is enabled for all branches
        'triggers': [{'builders': ["libva"],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "gmmlib": {
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
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "igc": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_igc.py",
        "product_type": Product_type.PUBLIC_LINUX_IGC.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'intel-graphics-compiler',
        # Builder is enabled for master and intel-mediasdk-19.1
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "opencl": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_opencl.py",
        "product_type": Product_type.PUBLIC_LINUX_OPENCL_RUNTIME.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'opencl_runtime',
        # Builder is enabled for master and intel-mediasdk-19.1, see igc
        'triggers': [{'builders': ['igc', 'gmmlib'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "ffmpeg": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_ffmpeg.py",
        "product_type": Product_type.PUBLIC_LINUX_FFMPEG.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'ffmpeg',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "metrics-calc": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_metrics_calc.py",
        "product_type": Product_type.PUBLIC_LINUX_METRICS_CALC.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'metrics_calc_lite',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "driver": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "driver-gcc-10": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "10",
        "worker": "ubuntu",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "driver-clang-10.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_CLANG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "clang",
        "compiler_version": "10",
        "worker": "ubuntu",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    # TODO: enable for 20.1+ branches
    "driver-kernels-off": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_KERNELS_OFF.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) == 'master')}]
    },

    # TODO: enable for 20.1+ branches
    "driver-nonfree-kernels-off": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_NONFREE_KERNELS_OFF.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) == 'master')}]
    },

    "driver-debug": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.DEBUG.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # TODO: create class for triggers
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "driver-release-internal": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE_INTERNAL.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # TODO: create class for triggers
        'triggers': [{'builders': ['libva', 'gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "mediasdk": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'mediasdk',
        # Builder is enabled for all branches
        # TODO: create class for triggers
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "mediasdk-api-next": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'mediasdk',
        # Builder is enabled for not release branches
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "mediasdk-gcc-10": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "10",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        # Enabled for all non release branches and for release branches staring from intel-mediasdk-20.*
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch) or re.match('^intel-media(sdk)?-2\d+\.\w', (target_branch or branch)))}]
    },

    "mediasdk-clang-10.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_CLANG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "clang",
        "compiler_version": "10",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        # Enabled for all non release branches and for release branches staring from intel-mediasdk-20.*
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch) or re.match('^intel-media(sdk)?-2\d+\.\w', (target_branch or branch)))}]
    },

    # Fastboot is a special configuration of MediaSDK, when we 
    # build MediaSDK in small scope but it can load very fast
    # (needed by embedded systems)
    # see method of building it in product-config

    "mediasdk-fastboot-gcc-10": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_FASTBOOT_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": True,
        "compiler": "gcc",
        "compiler_version": "10",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "mediasdk-api-next-defconfig": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT_DEFCONFIG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos_defconfig",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "mediasdk-windows": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_windows_public.py",
        "product_type": Product_type.PUBLIC_WINDOWS.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "windows",
        "dependency_name": 'mediasdk',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: (target_branch or branch) == 'master')}]
    },

    "test": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "product_conf_file": "conf_media_test.py",
        "custom_types": f"mediasdk:{Product_type.PUBLIC_LINUX.value}",
        "worker": "centos_test",
        # opencl is dependecy only for master and intel-mediasdk-19.1 branches,
        # because for other branches that build doesn't run
        'triggers': [{'builders': ['mediasdk', 'driver'],
                      'filter': GithubCommitFilter(
            PRODUCTION_REPOS,
            lambda branch, target_branch: (target_branch or branch) in ['mss2018_r2'])},
                     
                     {'builders': ['mediasdk', 'driver', 'opencl', 'libva-utils'],
                      'filter': GithubCommitFilter(
            PRODUCTION_REPOS,
            lambda branch, target_branch: MediaSdkDirectories.is_release_branch(
                              target_branch or branch) or ((target_branch or branch) == 'master'))}]
    },

    "test-api-next": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "product_conf_file": "conf_media_test.py",
        "custom_types": f"mediasdk:{Product_type.PUBLIC_LINUX_API_NEXT.value}",
        "worker": "centos_test",
        'triggers': [{'builders': ['mediasdk-api-next', 'driver', 'opencl', 'libva-utils'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS, 
                                                   lambda branch, target_branch: True)}]},

    PACKAGES: {
        "factory": FACTORIES.init_package_factory,
        "worker": "ubuntu",
        'triggers': [{'builders': ['test-api-next', 'test'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) == 'master')},
                     {'builders': ['test'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]}
}

FLOW = factories.Flow(BUILDERS, FACTORIES)

WORKERS = {
    "windows": {
        'b-1-26': {"os": OsType.windows},
        'b-1-27': {"os": OsType.windows},
    },

    "centos": {
        "CentOS-7_4-bbx-1": {"os": OsType.linux},
        "CentOS-7_4-bbx-2": {"os": OsType.linux},
        "CentOS-7_4-bbx-3": {"os": OsType.linux},
    },
    "centos_defconfig": {
        # Workaroud for running 'trigger' builder in parallel with build
        "CentOS-7_4-defconfig-bbx": {"os": OsType.linux, 'max_builds': 2},
    },
    "ubuntu": {
        "Ubuntu-18_04-bbx-1": {"os": OsType.linux},
        "Ubuntu-18_04-bbx-2": {"os": OsType.linux},
        "Ubuntu-18_04-bbx-3": {"os": OsType.linux},

    },
    "centos_test": {
        "t-1-17": {"os": OsType.linux},
        "t-1-16": {"os": OsType.linux}
    },
}

PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None  # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None  # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media CI"

# Don't decrease the POLL_INTERVAL, because Github rate limit can be reached
# and new api requests will not be performed
POLL_INTERVAL = 120  # Poll Github for new changes (in seconds)

WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_URL = f"postgresql://buildbot:{msdk_secrets.DATABASE_PASSWORD}@localhost/buildbot"
GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN

TRIGGER = 'trigger'

REPO_URL = f"https://github.com/{MEDIASDK_ORGANIZATION}/{MEDIASDK_REPO}"
