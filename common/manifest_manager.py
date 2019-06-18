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

"""
Manifest file manager
"""

import pathlib
import platform
from urllib.parse import urljoin

import yaml
try:
    import common.static_closed_data as static_data
except Exception:
    try:
        import common.static_private_data as static_data
    except Exception:
        import common.static_public_data as static_data


class ManifestException(Exception):
    pass


class ManifestDoesNotExist(ManifestException):
    pass


class ManifestSavingError(ManifestException):
    pass


class WrongComponentFormatError(ManifestException):
    pass


class WrongRepositoryFormatError(ManifestException):
    pass


class Manifest:
    """
    Manifest wrapper
    """

    def __init__(self, manifest_path=None):
        """
        :param manifest_path: Path to a manifest file
        :type manifest_path: String
        """

        self._manifest_file = pathlib.Path(manifest_path if manifest_path else 'manifest.yml')
        self._version = '0'  # gets from manifest
        self._event_component = None  # gets from manifest
        self._event_repo = None  # gets from manifest
        self._components = {}  # gets from manifest

        if manifest_path is not None:
            self._prepare_manifest()

    def __repr__(self):
        return str(self._manifest_file)

    def _prepare_manifest(self):
        """
        Read manifest file and convert it's data to objects

        :return: None | Exception
        :rtype: None | ManifestException
        """

        if self._manifest_file.is_file():
            with self._manifest_file.open('r') as manifest:
                manifest_info = yaml.load(manifest, Loader=yaml.FullLoader)

            self._version = manifest_info.get('version', '0')
            self._event_component = manifest_info['event']['component']
            self._event_repo = manifest_info['event']['repository']

            for name, info in manifest_info['components'].items():
                self._components[name] = Component.from_dict({
                    'name': name,
                    'version': info['version'],
                    'repository': info['repository'],
                    'build_info': info['build_info']})
        else:
            raise ManifestDoesNotExist(f'Can not find manifest "{self._manifest_file}"')

    @property
    def version(self):
        """
        get manifest version
        """

        return self._version

    @property
    def components(self):
        """
        get components list
        """

        return list(self._components.values())

    @property
    def event_component(self):
        """
        get event component
        """

        return self.get_component(self._event_component)

    @property
    def event_repo(self):
        """
        get event repository
        """

        return self.event_component.get_repository(self._event_repo)

    def set_event_component(self, component):
        """
        setter for event component

        :param component: Component name
        """

        self._event_component = component

    def set_event_repo(self, repo):
        """
        setter for event repo

        :param repo: Repository name
        """

        self._event_repo = repo

    def get_component(self, component_name):
        """
        get component by name

        :param component_name: Name of a component
        :type component_name: String

        :return: Component object | None
        :rtype: Component | None
        """

        return self._components.get(component_name, None)

    def add_component(self, component, replace=False):
        """
        add component to manifest

        :param component: Component object
        :type component: Component

        :param replace: Replace component with the same name
        :type replace: Boolean

        :return: Boolean
        :rtype: Boolean
        """

        if not replace and component.name in self._components:
            return False

        self._components[component.name] = component
        return True

    def delete_component(self, component_name):
        """
        delete component to another

        :param component_name: Name of a component
        :type component_name: String

        :return: Boolean
        :rtype: Boolean
        """

        try:
            del self._components[component_name]
        except KeyError:
            return False
        return True

    def save_manifest(self, save_to):
        """
        save manifest to a file

        :param save_to: path to a new manifest file
        :type save_to: String

        :return: None | Exception
        :rtype: None | ManifestException
        """

        path_to_save = pathlib.Path(save_to)
        path_to_save.parent.mkdir(parents=True, exist_ok=True)

        manifest_data = {'components': {},
                         'event': {
                             'component': self._event_component,
                             'repository': self._event_repo
                         },
                         'version': self._version}

        for comp_name, comp_data in self._components.items():
            comp = dict(comp_data)
            manifest_data['components'][comp_name] = {
                'repository': comp['repositories'],
                'build_info': comp['build_info'],
                'version': comp['version']
            }

        try:
            with path_to_save.open('w') as manifest:
                yaml.dump(manifest_data, stream=manifest,
                          default_flow_style=False, sort_keys=False)
        except Exception as ex:
            raise ManifestSavingError(ex)


class Component:
    """
    Component wrapper
    """

    def __init__(self, name, version, repositories, build_info):
        """
        :param name: Name of component
        :type name: String

        :param version: Version of component
        :type version: String

        :param repositories: List of Repository objects
        :type repositories: List

        :param build_info: Dict of build info. It must contain:
                           trigger (Name of triggered repo for component),
                           product_type (Type of product, ex. public_linux),
                           build_type (Type of build, ex. release),
                           build_event (Event of build, ex. commit)
        :type build_info: Dict
        """

        self._name = name
        self._version = version
        self._build_info = BuildInfo(**build_info)
        self._repositories = {}

        self._prepare_repositories(repositories)

    def __iter__(self):
        yield 'name', self._name
        yield 'version', self._version
        yield 'build_info', dict(self._build_info)
        yield 'repositories', {repo: dict(data) for repo, data in self._repositories.items()}

    def _prepare_repositories(self, repositories):
        for repo in repositories.values():
            if isinstance(repo, Repository):
                self._repositories[repo.name] = repo
            else:
                self._repositories[repo['name']] = Repository.from_dict(repo)

    @staticmethod
    def from_dict(comp_data):
        """
        Method for converting dictionary to object

        :param comp_data: Component data
        :type comp_data: Dictionary

        :return: Component obj | Exception
        :rtype: Component | ManifestException
        """

        try:
            component = Component(comp_data['name'],
                                  comp_data['version'],
                                  comp_data['repository'],
                                  comp_data['build_info'])
        except ManifestException:
            raise
        except Exception as ex:
            raise WrongComponentFormatError(ex)
        return component

    @property
    def name(self):
        """
        get component name

        :return: Component name
        :rtype: String
        """

        return self._name

    @property
    def version(self):
        """
        get component version

        :return: Version of component
        :rtype: String
        """

        return self._version

    @property
    def build_info(self):
        """
        get build information

        :return: BuildInfo object
        :rtype: BuildInfo
        """

        return self._build_info

    @property
    def repositories(self):
        """
        get repositories list

        :return: List of Repository objects
        :rtype: List
        """

        return list(self._repositories.values())

    @property
    def trigger_repository(self):
        """
        get triggered repository

        :return: Repository object | None
        :rtype: Repository | None
        """

        return self._repositories[self._build_info.trigger]

    def get_repository(self, repository_name):
        """
        get repository by name

        :param repository_name: Name of repository
        :type repository_name: String

        :return: Repository object | None
        :rtype: Repository | None
        """

        return self._repositories.get(repository_name, None)

    def add_repository(self, repository, replace=False):
        """
        add repository to component

        :param repository: Repository object
        :type repository: Repository

        :param replace: Replace repository with the same name
        :type replace: Boolean

        :return: Boolean
        :rtype: Boolean
        """

        if not replace and repository.name in self._repositories:
            return False

        self._repositories[repository.name] = repository
        return True

    def delete_repository(self, repository_name):
        """
        delete repository to another

        :param repository_name: Repository name
        :type repository_name: String

        :return: Boolean
        :rtype: Boolean
        """

        try:
            del self._repositories[repository_name]
        except KeyError:
            return False
        return True


class Repository:
    """
    Container for repository information
    """

    def __init__(self, name, url, branch='master', target_branch=None,
                 revision='HEAD', commit_time=None, source_type='git'):
        self._name = name
        self._url = url
        self._branch = branch
        self._target_branch = target_branch
        self._revision = revision
        self._commit_time = commit_time
        self._type = source_type

    def __iter__(self):
        yield 'name', self._name
        yield 'url', self._url
        yield 'branch', self._branch
        if self._target_branch:
            yield 'target_branch', self._target_branch
        yield 'revision', self._revision
        yield 'commit_time', self._commit_time
        yield 'type', self._type

    @staticmethod
    def from_dict(repo_data):
        """
        Method for converting dictionary to object

        :param repo_data: Repository data
        :type repo_data: Dictionary

        :return: Repository obj | Exception
        :rtype: Repository | ManifestException
        """

        try:
            repo = Repository(repo_data['name'],
                              repo_data['url'],
                              repo_data['branch'],
                              repo_data.get('target_branch'),
                              repo_data['revision'],
                              repo_data.get('commit_time'),
                              repo_data['type']
                              )
        except Exception as ex:
            raise WrongRepositoryFormatError(ex)
        return repo

    @property
    def name(self):
        """
        get name of repo

        :return: Name of repository
        :rtype: String
        """

        return self._name

    @property
    def url(self):
        """
        get url of repo

        :return: URL of repository
        :rtype: String
        """

        return self._url

    @property
    def branch(self):
        """
        get branch of repo

        :return: Branch name
        :rtype: String
        """

        return self._branch

    @property
    def target_branch(self):
        """
        get target_branch of repo

        :return: Branch name
        :rtype: String
        """

        return self._target_branch

    @property
    def revision(self):
        """
        get revision of repo

        :return: Revision of repository
        :rtype: String
        """

        return self._revision

    @property
    def commit_time(self):
        """
        get commit time

        :return: commit time
        :rtype: String
        """

        return self._commit_time

    @property
    def type(self):
        """
        get type of repository

        :return: type of repository
        :rtype: String
        """

        return self._type


class BuildInfo:
    """
    Container for information about build
    """

    def __init__(self, trigger, product_type, build_type, build_event):
        self._trigger = trigger
        self._product_type = product_type
        self._build_type = build_type
        self._build_event = build_event

    def __iter__(self):
        yield 'trigger', self._trigger
        yield 'product_type', self._product_type
        yield 'build_type', self._build_type
        yield 'build_event', self._build_event

    @property
    def trigger(self):
        """
        get triggered repository name

        :return: Repository object | None
        :rtype: Repository | None
        """

        return self._trigger

    @property
    def product_type(self):
        """
        get product type

        :return: Product type
        :rtype: String
        """

        return self._product_type

    @property
    def build_type(self):
        """
        get build type

        :return: Build type
        :rtype: String
        """

        return self._build_type

    @property
    def build_event(self):
        """
        get build event

        :return: Build event
        :rtype: String
        """

        return self._build_event

    def set_trigger(self, trigger):
        """
        Trigger setter

        :param trigger: Repository name
        :type trigger: String
        """

        self._trigger = trigger

    def set_product_type(self, product_type):
        """
        Product type setter

        :param product_type: Product type
        :type product_type: String
        """

        self._product_type = product_type

    def set_build_type(self, build_type):
        """
        Build type setter

        :param build_type: Build type
        :type build_type: String
        """

        self._build_type = build_type

    def set_build_event(self, build_event):
        """
        Build event setter

        :param build_event: Build event
        :type build_event: String
        """

        self._build_event = build_event


def _get_layout_parts(manifest, component, link_type=None):
    """
    Get parts of layout

    :param manifest: Manifest object
    :type manifest: Manifest

    :param component: Component name
    :type component: String

    :param default_rev: Flag for preparing revision
    :type default_rev: Boolean

    :return: Parts of layout
    :rtype: Dict
    """

    comp = manifest.get_component(component)
    repo = comp.trigger_repository

    if link_type == 'manifest':
        revision = repo.revision
    else:
        infra = manifest.get_component('infra')
        conf = infra.trigger_repository
        revision = f'{repo.revision}_conf_{conf.revision[0:8]}'

    parts = {
        'branch': repo.target_branch or repo.branch,
        'build_event': comp.build_info.build_event,
        'revision': revision,
        'product_type': comp.build_info.product_type,
        'build_type': comp.build_info.build_type
    }
    return parts


def _get_root_dir(os_type=None, dir_type='build'):
    """
    Get root directory

    :param os_type: Type of os (Windows|Linux)
    :type os_type: String

    :param dir_type: Type of root dir (build|test)
    :type dir_type: String

    :return: Root directory
    :rtype: pathlib.Path
    """

    if os_type is None:
        if platform.system() == 'Windows':
            return pathlib.Path(static_data.SHARE_PATHS[f'{dir_type}_windows'])
        elif platform.system() == 'Linux':
            return pathlib.Path(static_data.SHARE_PATHS[f'{dir_type}_linux'])
    elif os_type == 'Windows':
        return pathlib.PureWindowsPath(static_data.SHARE_PATHS[f'{dir_type}_windows'])
    elif os_type == 'Linux':
        return pathlib.PurePosixPath(static_data.SHARE_PATHS[f'{dir_type}_linux'])
    raise OSError('Unknown os type %s' % os_type)


def _get_root_url(product_type, url_type='build'):
    """
    Get root url

    :param product_type: Type of product
    :type product_type: String

    :param url_type: Type of root dir (build|test)
    :type url_type: String

    :return: Root url
    :rtype: String
    """

    if product_type.startswith('public_'):
        root_url = r'http://mediasdk.intel.com'
    else:
        root_url = r'http://bb.msdk.intel.com'

    if product_type.startswith("private_linux_next_gen"):
        build_root_dir = f'next_gen_{url_type}s'
    elif product_type.startswith("private_"):
        build_root_dir = f'private_{url_type}s'
    elif product_type.startswith("public_"):
        build_root_dir = f'{url_type}s'
    else:
        build_root_dir = f'closed_{url_type}s'

    return urljoin(root_url, build_root_dir)


def get_build_dir(manifest, component, os_type=None, link_type='build'):
    """
    Get build directory

    :param manifest: Manifest object
    :type manifest: Manifest

    :param component: Component name
    :type component: String

    :param os_type: Type of os (Windows|Linux)
    :type os_type: String

    :param link_type: Type of link to return (root|commit|build|manifest)
    :type link_type: String

    :param default_rev: Flag for preparing revision
    :type default_rev: Boolean

    :return: Build directory
    :rtype: pathlib.Path
    """

    parts = _get_layout_parts(manifest, component, link_type)
    result_path = _get_root_dir(os_type=os_type)

    if link_type in ['commit', 'build']:
        result_path = result_path / component / parts['branch'] / parts['build_event'] / parts['revision']
    elif link_type == 'manifest':
        result_path = result_path / 'manifest' / parts['branch'] / parts['build_event'] / parts['revision']
    if link_type == 'build':
        result_path = result_path / f'{parts["product_type"]}_{parts["build_type"]}'

    return result_path


def get_test_dir(manifest, component, test_platform=None, os_type=None, link_type='build'):
    """
    Get test directory

    :param manifest: Manifest object
    :type manifest: Manifest

    :param component: Component name
    :type component: String

    :param test_platform: Acronym of test platform (w10rs3_skl_64_d3d11|c7.3_skl_64_server)
    :type test_platform: String

    :param os_type: Type of os (Windows|Linux)
    :type os_type: String

    :param link_type: Type of link to return (root|commit|build)
    :type link_type: String

    :return: Test directory
    :rtype: pathlib.Path
    """

    parts = _get_layout_parts(manifest, component)
    result_path = _get_root_dir(os_type=os_type, dir_type='test')

    if link_type in ['commit', 'build']:
        result_path = result_path / component / parts['branch'] / parts['build_event'] / parts['revision']
    if link_type == 'build':
        if test_platform:
            result_path = result_path / parts['build_type'] / test_platform
        else:
            result_path = result_path / f'{parts["product_type"]}_{parts["build_type"]}'

    return result_path


def get_build_url(manifest, component, link_type='build'):
    """
    Get build url

    :param manifest: Manifest object
    :type manifest: Manifest

    :param component: Component name
    :type component: String

    :param link_type: Type of link to return (root|commit|build)
    :type link_type: String

    :param default_rev: Flag for preparing revision
    :type default_rev: Boolean

    :return: Build url
    :rtype: String
    """

    parts = _get_layout_parts(manifest, component, link_type)
    result_link = _get_root_url(parts['product_type'])

    if link_type in ['commit', 'build']:
        result_link = '/'.join((result_link, component, parts['branch'], parts['build_event'], parts['revision']))
    elif link_type == 'manifest':
        result_link = '/'.join((result_link, 'manifest', parts['branch'], parts['build_event'], parts['revision']))
    if link_type == 'build':
        result_link = '/'.join((result_link, f'{parts["product_type"]}_{parts["build_type"]}'))
    return result_link


def get_test_url(manifest, component, test_platform=None, link_type='build'):
    """
    Get test url

    :param manifest: Manifest object
    :type manifest: Manifest

    :param component: Component name
    :type component: String

    :param test_platform: Acronym of test platform (w10rs3_skl_64_d3d11|c7.3_skl_64_server)
    :type test_platform: String

    :param link_type: Type of link to return (root|commit|build)
    :type link_type: String

    :return: Test url
    :rtype: String
    """

    parts = _get_layout_parts(manifest, component)
    result_link = _get_root_url(parts['product_type'], url_type='test')

    if link_type in ['commit', 'build']:
        result_link = '/'.join((result_link, component, parts['branch'], parts['build_event'], parts['revision']))
    if link_type == 'build':
        if test_platform:
            result_link = '/'.join((result_link, parts['build_type'], test_platform))
        else:
            result_link = '/'.join((result_link, f'{parts["product_type"]}_{parts["build_type"]}'))
    return result_link
