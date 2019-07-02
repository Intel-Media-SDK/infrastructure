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

"""
This module deploys infrastructure code on build and test machines
"""

import sys
import yaml
import argparse
import pathlib
import logging
import shutil
from distutils.dir_util import copy_tree
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


@Proxy.with_proxies
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
                                      # TODO: switch branch to 'master' after final deploy
                                      branch='one_ci_dev', url=repo_url)
            repo.prepare_repo()
            if MediaSdkDirectories.is_release_branch(branch):
                if not repo.is_branch_exist(branch):
                    raise git_worker.BranchDoesNotExistException(
                        f'Release branch {branch} does not exist in the repo {repo.repo_name}')

                # repo.branch = branch
                repo.change_repo_state(branch_name=branch,
                                       commit_time=commit_time)
            else:
                repo.change_repo_state(
                    commit_time=commit_time)
        else:
            log.info('Commit id and timestamp not specified, clone HEAD of repository')
            repo = git_worker.GitRepo(root_repo_dir=root_repo_dir, repo_name=repo_name,
                                      # TODO: switch branch to 'master' after final deploy
                                      branch='one_ci_dev', url=repo_url)

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


def extract_closed_source_infrastructure(root_dir, branch, commit_id, commit_time, manifest):
    log = logging.getLogger('extract_repo.extract_closed_source_infrastructure')

    infrastructure_root_dir = root_dir / 'infrastructure'
    configs_root_dir = root_dir / 'product-configs'

    # We save and update repos in temporary folder and create infrastructure package from it
    # So, not needed extracting repo to the beginning each time
    original_repos_dir = root_dir / 'tmp_infrastructure'

    repos = MediaSdkDirectories()
    closed_source_product_configs_repo = repos.closed_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo
    closed_source_infra_repo = repos.closed_source_infrastructure_repo

    # Extract product configs
    if not manifest:
        extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_product_configs_repo,
                     branch=branch, commit_id=commit_id, commit_time=commit_time)
        conf_manifest = original_repos_dir / closed_source_product_configs_repo / 'manifest.yml'
        manifest_data = yaml.load(conf_manifest.open(), Loader=yaml.FullLoader)
    else:
        conf_manifest = manifest
        manifest_data = yaml.load(conf_manifest.open(), Loader=yaml.FullLoader)
        product_conf = manifest_data['components']['infra']['repository'][closed_source_product_configs_repo]
        extract_repo(root_repo_dir=root_dir, repo_name=product_conf['name'],
                     branch=product_conf['branch'],
                     commit_id=product_conf['revision'], commit_time=commit_time)

    open_source_infra = manifest_data['components']['infra']['repository'][open_source_infra_repo]
    closed_source_infra = manifest_data['components']['infra']['repository'][closed_source_infra_repo]

    # Extract open source infrastructure
    # Set proxy for access to GitHub
    extract_repo(root_repo_dir=original_repos_dir, repo_name=open_source_infra['name'],
                 branch=open_source_infra['branch'],
                 commit_id=open_source_infra['revision'], proxy=True)

    # Extract closed source part of infrastructure
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_infra['name'],
                 branch=closed_source_infra['branch'],
                 commit_id=closed_source_infra['revision'])

    log.info('-' * 50)
    log.info(f"Create infrastructure package")
    try:
        log.info(f"- Delete existing infrastructure")
        if infrastructure_root_dir.exists():
            remove_directory(str(infrastructure_root_dir))
        if configs_root_dir.exists():
            remove_directory(str(configs_root_dir))

        log.info(f"- Copy open source infrastructure")
        copy_tree(str(original_repos_dir / open_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Copy closed source infrastructure")
        copy_tree(str(original_repos_dir / closed_source_infra_repo),
                  str(infrastructure_root_dir))

        log.info(f"- Copy product configs")
        copy_tree(str(original_repos_dir / closed_source_product_configs_repo),
                  str(configs_root_dir))

        # log.info(f"Copy secrets")
        shutil.copyfile(str(pathlib.Path('msdk_secrets.py').absolute()),
                        str(infrastructure_root_dir / 'common' / 'msdk_secrets.py'))
    except Exception:
        log.exception('Can not create infrastructure package')
        exit_script(ErrorCode.CRITICAL)


def extract_open_source_infrastructure(root_dir, branch, commit_id, commit_time, manifest):
    repos = MediaSdkDirectories()
    open_source_product_configs_repo = repos.open_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo

    # Extract product configs
    if not manifest:
        extract_repo(root_repo_dir=root_dir, repo_name=open_source_product_configs_repo, branch=branch,
                     commit_id=commit_id, commit_time=commit_time)
        conf_manifest = root_dir / open_source_product_configs_repo / 'manifest.yml'
        manifest_data = yaml.load(conf_manifest.open(), Loader=yaml.FullLoader)
    else:
        conf_manifest = manifest
        manifest_data = yaml.load(conf_manifest.open(), Loader=yaml.FullLoader)
        product_conf = manifest_data['components']['infra']['repository'][open_source_product_configs_repo]
        extract_repo(root_repo_dir=root_dir, repo_name=product_conf['name'],
                     branch=product_conf['branch'],
                     commit_id=product_conf['revision'], commit_time=commit_time)

    open_source_infra = manifest_data['components']['infra']['repository'][open_source_infra_repo]

    # Extract open source infrastructure
    extract_repo(root_repo_dir=root_dir, repo_name=open_source_infra['name'],
                 branch=open_source_infra['branch'],
                 commit_id=open_source_infra['revision'])


def extract_private_infrastructure(root_dir, branch, commit_id, commit_time, manifest):
    log = logging.getLogger('extract_repo.extract_private_infrastructure')

    infrastructure_root_dir = root_dir / 'infrastructure'
    configs_root_dir = root_dir / 'product-configs'

    # We save and update repos in temporary folder and create infrastructure package from it
    # So, not needed extracting repo to the beginning each time
    original_repos_dir = root_dir / 'tmp_infrastructure'

    repos = MediaSdkDirectories()
    open_source_product_configs_repo = repos.open_source_product_configs_repo
    open_source_infra_repo = repos.open_source_infrastructure_repo
    closed_source_product_configs_repo = repos.closed_source_product_configs_repo
    closed_source_infra_repo = repos.closed_source_infrastructure_repo

    # Extract open source infrastructure and product configs
    extract_open_source_infrastructure(original_repos_dir, branch, commit_id, commit_time, manifest)

    # Extract closed source product configs
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_product_configs_repo,
                 branch='master', commit_time=commit_time)
    conf_manifest = original_repos_dir / closed_source_product_configs_repo / 'manifest.yml'
    manifest_data = yaml.load(conf_manifest.open(), Loader=yaml.FullLoader)

    closed_source_infra = manifest_data['components']['infra']['repository'][closed_source_infra_repo]
    # Extract closed source infrastructure
    extract_repo(root_repo_dir=original_repos_dir, repo_name=closed_source_infra['name'],
                 branch=closed_source_infra['branch'],
                 commit_id=closed_source_infra['revision'])

    log.info('-' * 50)
    log.info(f"Create infrastructure package")
    try:
        log.info(f"- Delete existing infrastructure")
        if infrastructure_root_dir.exists():
            remove_directory(str(infrastructure_root_dir))
        if configs_root_dir.exists():
            remove_directory(str(configs_root_dir))

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
                  str(configs_root_dir))

        log.info(f"- Copy closed source product configs")
        copy_tree(str(original_repos_dir / closed_source_product_configs_repo),
                  str(configs_root_dir))

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

    parser.add_argument("--infra-type", metavar="String", required=True,
                        choices=[OPEN_SOURCE_KEY, CLOSED_SOURCE_KEY, PRIVATE_KEY],
                        help=f"""Type of infrastructure "{OPEN_SOURCE_KEY}"/"{CLOSED_SOURCE_KEY}"/"{PRIVATE_KEY}" 
{OPEN_SOURCE_KEY} key uses for extracting open source infrastructure package
{CLOSED_SOURCE_KEY} key uses for extracting closed source infrastructure package
{PRIVATE_KEY} key uses for extracting private infrastructure package""")
    parser.add_argument("--manifest-path", metavar="PATH",
                        help=f"Path to a manifest file")
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

    if args.commit_time:
        args.commit_time = datetime.strptime(args.commit_time, '%Y-%m-%d %H:%M:%S').timestamp()

    if args.manifest_path:
        args.manifest_path = pathlib.Path(args.manifest_path)

    if args.infra_type == OPEN_SOURCE_KEY:
        log.info("EXTRACTING OPEN SOURCE INFRASTRUCTURE")
        extract_open_source_infrastructure(root_dir=root_dir, branch=args.branch,
                                           commit_id=args.commit_id, commit_time=args.commit_time,
                                           manifest=args.manifest_path)
    elif args.infra_type == CLOSED_SOURCE_KEY:
        log.info("EXTRACTING CLOSED SOURCE INFRASTRUCTURE")
        extract_closed_source_infrastructure(root_dir=root_dir, branch=args.branch,
                                             commit_id=args.commit_id, commit_time=args.commit_time,
                                             manifest=args.manifest_path)
    elif args.infra_type == PRIVATE_KEY:
        log.info("EXTRACTING PRIVATE INFRASTRUCTURE")
        extract_private_infrastructure(root_dir=root_dir, branch=args.branch,
                                       commit_id=args.commit_id, commit_time=args.commit_time,
                                       manifest=args.manifest_path)
    exit_script()


if __name__ == '__main__':
    main()
