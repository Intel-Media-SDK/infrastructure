# Copyright (c) 2018-2019 Intel Corporation
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

"""
This module deploys infrastructure code on build and test machines
"""

import sys
import argparse
import pathlib
import logging
import shutil
from distutils.dir_util import copy_tree
from importlib import reload
from datetime import datetime

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common import git_worker
from common.mediasdk_directories import MediaSdkDirectories, Proxy
from common.helper import ErrorCode, remove_directory
from common.logger_conf import configure_logger

OPEN_SOURCE_KEY = 'OPEN_SOURCE_INFRA'
CLOSED_SOURCE_KEY = 'CLOSED_SOURCE_INFRA'
PRIVATE_KEY = 'PRIVATE_INFRA'


def exit_script(error_code=None):
    log = logging.getLogger('extract_repo.exit_script')
    log.info('-' * 50)
    if error_code:
        log.info("EXTRACTING FAILED")
        sys.exit(error_code)
    else:
        log.info("EXTRACTING COMPLETED")


@Proxy.with_proxies()
def extract_repo(root_repo_dir, repo_name, branch, commit_id=None, commit_time=None, proxy=False):
    log = logging.getLogger('extract_repo.extract_repo')

    try:
        repo_url = MediaSdkDirectories.get_repo_url_by_name(repo_name)
        if commit_id:
            repo = git_worker.GitRepo(root_repo_dir=root_repo_dir, repo_name=repo_name,
                                      branch=branch, url=repo_url, commit_id=commit_id)
            repo.prepare_repo()
            repo.change_repo_state()

        elif commit_time:
            repo = git_worker.GitRepo(root_repo_dir=root_repo_dir, repo_name=repo_name,
                                      branch='master', url=repo_url)
            repo.prepare_repo()
            if MediaSdkDirectories.is_release_branch(branch):
                if not repo.is_branch_exist(branch):
                    raise git_worker.BranchDoesNotExistException(
                        f'Release branch {branch} does not exist in the repo {repo.repo_name}')

                # repo.branch = branch
                repo.change_repo_state(branch_name=branch,
                                       commit_time=datetime.strptime(commit_time,
                                                                     '%Y-%m-%d %H:%M:%S').timestamp())
            else:
                repo.change_repo_state(
                    commit_time=datetime.strptime(commit_time, '%Y-%m-%d %H:%M:%S').timestamp())
        else:
            log.info('Commit id and timestamp not specified, clone HEAD of repository')
            repo = git_worker.GitRepo(root_repo_dir=root_repo_dir, repo_name=repo_name,
                                      branch='master', url=repo_url)

            repo.prepare_repo()
            if MediaSdkDirectories.is_release_branch(branch):
                if not repo.is_branch_exist(branch):
                    raise git_worker.BranchDoesNotExistException(
                        f'Release branch {branch} does not exist in the repo {repo.repo_name}')

                # repo.branch = branch
                repo.change_repo_state(branch_name=branch)
            else:
                # repo.branch = master
                repo.change_repo_state()

    except Exception:
        log.exception('Exception occurred')
        exit_script(ErrorCode.CRITICAL)


def extract_closed_source_infrastructure(root_dir, branch, commit_id, commit_time):
    log = logging.getLogger('extract_repo.extract_closed_source_infrastructure')

    infrastructure_root_dir = root_dir / 'infrastructure'

    # We save and update repos in temporary folder and create infrastructure package from it
    # So, not needed extracting repo to the beginning each time
    original_repos_dir = root_dir / 'tmp_infrastructure'

    repos = MediaSdkDirectories()
    closed_source_product_configs_repo = repos.closed_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo
    closed_source_infra_repo = repos.closed_source_infrastructure_repo

    # Extract product configs
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_product_configs_repo,
                 branch=branch, commit_id=commit_id, commit_time=commit_time)

    # Get revision of build and test scripts from product configs repo
    configs_dir = original_repos_dir / closed_source_product_configs_repo
    sys.path.append(str(configs_dir))
    import infrastructure_version

    open_source_infra_version = infrastructure_version.OPEN_SOURCE
    closed_source_infra_version = infrastructure_version.CLOSED_SOURCE

    # Extract open source infrastructure
    # Set proxy for access to GitHub
    extract_repo(root_repo_dir=original_repos_dir, repo_name=open_source_infra_repo,
                 branch=open_source_infra_version['branch'],
                 commit_id=open_source_infra_version['commit_id'], proxy=True)

    # Extract closed source part of infrastructure
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_infra_repo,
                 branch=closed_source_infra_version['branch'],
                 commit_id=closed_source_infra_version['commit_id'])

    log.info('-' * 50)
    log.info(f"Create infrastructure package")
    try:
        log.info(f"- Delete existing infrastructure")
        if infrastructure_root_dir.exists():
            remove_directory(str(infrastructure_root_dir))

        log.info(f"- Copy open source infrastructure")
        copy_tree(str(original_repos_dir / open_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Copy closed source infrastructure")
        copy_tree(str(original_repos_dir / closed_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Copy product configs")
        copy_tree(str(original_repos_dir / closed_source_product_configs_repo),
                  str(infrastructure_root_dir / closed_source_product_configs_repo))

        # log.info(f"Copy secrets")
        shutil.copyfile(str(pathlib.Path('msdk_secrets.py').absolute()),
                        str(infrastructure_root_dir / 'common' / 'msdk_secrets.py'))
    except Exception:
        log.exception('Can not create infrastructure package')
        exit_script(ErrorCode.CRITICAL)


def extract_open_source_infrastructure(root_dir, branch, commit_id, commit_time):
    repos = MediaSdkDirectories()
    open_source_product_configs_repo = repos.open_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo

    # Extract product configs
    extract_repo(root_repo_dir=root_dir, repo_name=open_source_product_configs_repo, branch=branch,
                 commit_id=commit_id, commit_time=commit_time)

    # Get revision of infrastructure from product configs repo
    configs_dir = root_dir / open_source_product_configs_repo
    sys.path.append(str(configs_dir))
    import infrastructure_version
    sys.path.remove(str(configs_dir))

    open_source_infra_version = infrastructure_version.OPEN_SOURCE

    # Extract open source infrastructure
    extract_repo(root_repo_dir=root_dir, repo_name=open_source_infra_repo,
                 branch=open_source_infra_version['branch'],
                 commit_id=open_source_infra_version['commit_id'])


def extract_private_infrastructure(root_dir, branch, commit_id, commit_time):
    log = logging.getLogger('extract_repo.extract_private_infrastructure')

    infrastructure_root_dir = root_dir / 'infrastructure'

    # We save and update repos in temporary folder and create infrastructure package from it
    # So, not needed extracting repo to the beginning each time
    original_repos_dir = root_dir / 'tmp_infrastructure'

    repos = MediaSdkDirectories()
    open_source_product_configs_repo = repos.open_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo
    closed_source_product_configs_repo = repos.closed_source_product_configs_repo
    closed_source_infra_repo = repos.closed_source_infrastructure_repo

    # Extract open source infrastructure and product configs
    extract_open_source_infrastructure(original_repos_dir, branch, commit_id, commit_time)

    # Extract closed source product configs
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_product_configs_repo,
                 branch='master', commit_time=commit_time)

    # Get revision of closed source infrastructure from closed source product configs repo
    configs_dir = original_repos_dir / closed_source_product_configs_repo
    sys.path.append(str(configs_dir))
    import infrastructure_version
    infrastructure_version = reload(infrastructure_version)

    closed_source_infra_version = infrastructure_version.CLOSED_SOURCE

    # Extract closed source infrastructure
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_infra_repo,
                 branch=closed_source_infra_version['branch'],
                 commit_id=closed_source_infra_version['commit_id'])

    log.info('-' * 50)
    log.info(f"Create infrastructure package")
    try:
        log.info(f"- Delete existing infrastructure")
        if infrastructure_root_dir.exists():
            remove_directory(str(infrastructure_root_dir))

        log.info(f"- Copy open source infrastructure")
        copy_tree(str(original_repos_dir / open_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Copy closed source infrastructure")
        copy_tree(str(original_repos_dir / closed_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Remove closed source static data")
        (infrastructure_root_dir / 'common' / 'static_closed_data.py').unlink()

        log.info(f"- Copy open source product configs")
        copy_tree(str(original_repos_dir / open_source_product_configs_repo),
                  str(infrastructure_root_dir / open_source_product_configs_repo))

        log.info(f"- Copy closed source product configs")
        copy_tree(str(original_repos_dir / closed_source_product_configs_repo),
                  str(infrastructure_root_dir / open_source_product_configs_repo))

        # log.info(f"Copy secrets")
        shutil.copyfile(str(pathlib.Path('msdk_secrets.py').absolute()),
                        str(infrastructure_root_dir / 'common' / 'msdk_secrets.py'))
    except Exception:
        log.exception('Can not create infrastructure package')
        exit_script(ErrorCode.CRITICAL)


def main():
    """Extract whole infrastructure package or specified repository"""

    parser = argparse.ArgumentParser(prog="extract_repo.py",
                                     epilog=f"If you sepcify --repo-name={PRIVATE_KEY} you must specify commit-time and an optional commit-id. "
                                            f"For all other cases if you specify commit-time and commit-id, only commit-id will be used.",
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("--repo-name", metavar="String", required=True,
                        help=f"""Repository name or "{OPEN_SOURCE_KEY}"/"{CLOSED_SOURCE_KEY}"/"{PRIVATE_KEY}"
{OPEN_SOURCE_KEY} key uses for extracting open source infrastructure package
{CLOSED_SOURCE_KEY} key uses for extracting closed source infrastructure package
{PRIVATE_KEY} key uses for extracting private infrastructure package""")

    parser.add_argument("--root-dir", metavar="PATH", default='.',
                        help=f"Path where repository will be stored, by default it is current directory")
    parser.add_argument("--branch", metavar="String", default='master',
                        help='Branch name, by default "master" branch')
    parser.add_argument("--commit-id", metavar="String",
                        help='SHA of commit')
    parser.add_argument("--commit-time", metavar="String",
                        help='Will switch to the commit before specified time')
    args = parser.parse_args()

    configure_logger()
    log = logging.getLogger('extract_repo.main')

    root_dir = pathlib.Path(args.root_dir).absolute()

    if args.repo_name == OPEN_SOURCE_KEY:
        log.info("EXTRACTING OPEN SOURCE INFRASTRUCTURE")
        extract_open_source_infrastructure(root_dir=root_dir, branch=args.branch,
                                           commit_id=args.commit_id, commit_time=args.commit_time)
    elif args.repo_name == CLOSED_SOURCE_KEY:
        log.info("EXTRACTING CLOSED SOURCE INFRASTRUCTURE")
        extract_closed_source_infrastructure(root_dir=root_dir, branch=args.branch,
                                             commit_id=args.commit_id, commit_time=args.commit_time)
    elif args.repo_name == PRIVATE_KEY:
        log.info("EXTRACTING PRIVATE INFRASTRUCTURE")
        extract_private_infrastructure(root_dir=root_dir, branch=args.branch,
                                       commit_id=args.commit_id, commit_time=args.commit_time)
    else:
        log.info("EXTRACTING")
        extract_repo(root_repo_dir=root_dir, repo_name=args.repo_name,
                     branch=args.branch, commit_id=args.commit_id, commit_time=args.commit_time)
    exit_script()


if __name__ == '__main__':
    main()
