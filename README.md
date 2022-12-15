DISCONTINUATION OF PROJECT. 

This project will no longer be maintained by Intel.

This project has been identified as having known security escapes.

Intel has ceased development and contributions including, but not limited to, maintenance, bug fixes, new releases, or updates, to this project.  

Intel no longer accepts patches to this project.
# Infrastructure of Intel® Media SDK
Repository has all things needed for deploying public infrastructure of Intel® Media SDK.  
  
Repository contains:  
- Buildbot configuration
- Build scripts
- Small set of smoke tests (called "ted")
- Test adapter (called "ted_adapter")


# How to deploy
### Deploy master Buildbot
Dependencies:
- CentOS v7.3
- Python v3.6.x
- postgresql
- git

```bash
sudo pip3 install buildbot==1.8.0 buildbot-console-view==1.8.0 buildbot-www==1.8.0
```
Hint:  
It can work with default DB (sqlite) for that it needs to change next value in `bb/master/config.py`:
```python
DATABASE_URL = "sqlite:///state.sqlite"
```

Deploy:
```bash
git clone https://github.com/Intel-Media-SDK/infrastructure.git
cd ./infrastructure/bb/

buildbot upgrade-master master

#Configure Github`s webhook in your repository in settings-webhooks and create Github`s token after that do:
cd ../common
cp ./msdk_secrets.py.example ./msdk_secrets.py
nano msdk_secrets.py #add your real values

#Start Master Buildbot
buildbot start bb/master
```
### Deploy build box Worker Buildbot
Prerequisites:
- CentOS v6.9 / v7.3
- Python v3.6.x

To set up environment for MediaSDK and install all dependencies do:
- [Build Media SDK on CentOS](https://github.com/Intel-Media-SDK/MediaSDK/wiki/Build-Media-SDK-on-CentOS)
- [Build Media SDK on Ubuntu](https://github.com/Intel-Media-SDK/MediaSDK/wiki/Build-Media-SDK-on-Ubuntu)

Install packages for Buildbot:
```bash
sudo pip3 install buildbot-worker==1.8.0
sudo pip3 install gitpython==2.1.5 tenacity==4.5.0 txrequests txgithub service_identity
```
If you want the environment with X11, install:
```bash
sudo yum install libX11 libXext libXfixes libGL libGL-devel libX11-devel 
```
**Read more about the packages [here](docs/packages.md).**

Deploy:
```bash
git clone https://github.com/Intel-Media-SDK/infrastructure.git

buildbot-worker create-worker --umask=0o2 "worker" "<buildbot_master_IP>:9000" "<your_worker_name>" "pass"

cp infrastructure/common worker/common -R

#Start Worker Buildbot
buildbot-worker start worker
```

### Deploy test box Worker Buildbot
Dependencies:
- CentOS v7.3
- python v3.6.x
- git
- Change permissions on: `cd /opt/intel/ && chown <user_who_will_start_the_infrastructure_scripts>:<user_who_will_start_the_infrastructure_scripts> .` This change needs for auto-copy of build artifacts to the mediasdk folder (mediasdk folder will be deleted and created again).

```bash
# Install git lfs:
# For CentOS do:
sudo yum install curl epel-release
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.rpm.sh | sudo bash
sudo yum install git-lfs
git lfs install

# For Ubuntu do:
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
sudo apt-get install git-lfs

#After that do the same things as described in section "build box Worker"
```

Deploy:
```bash
git clone https://github.com/Intel-Media-SDK/infrastructure.git

buildbot-worker create-worker --umask=0o2 "worker" "<buildbot_master_IP>:9000" "<your_worker_name>" "pass"

cp infrastructure/common worker/common -R

#Start Worker Buildbot
buildbot-worker start worker
```
>Hint:  
>To use graphical driver (from Media Server Studio) with tests as not root user do: 
>```bash
>usermod -a -G video <mediasdk_user>
>#And restart session!
>```

### Set up shares
```
ln -s /nfs/import_dir/ci/tests/ /media/tests
ln -s /nfs/import_dir/ci/builds/ /media/builds
```

### Hints
- You can update all configurations by simple executing `git pull` command!
- Do not forget to add the line with `umask = 0o2` to the `buildbot.tac` file on all your masters and workers for the correct file permissions!
- To have additional information about your worker in Buildbot\`s worker list add **ip-address** to the `worker/info/host` file.
- Our configuration of Buildbot uses `GitPoller` so in case of private repos you need to execute `git config --global credential.helper store` and login once with your infrastructure credentials (otherwise polling will NOT work).

# Used versions of packages in CI
- LibVA: https://github.com/intel/libva/releases/tag/2.2.0
- Driver: https://github.com/intel/media-driver/releases/tag/intel-media-18.2.0

- Additional:
```bash
# on (CentOS 7.3)
libpciaccess-0.14-1.el7.x86_64
libpciaccess-devel-0.14-1.el7.x86_64
gtest-1.6.0-2.el7.x86_64
gtest-devel-1.6.0-2.el7.x86_64
ocl-icd-2.2.12-1.el7.x86_64
ocl-icd-devel-2.2.12-1.el7.x86_64
opencl-headers-2.2-1.20180306gite986688.el7.noarch
```



# How to reproduce build manually 
Our infrastructure was built on the principle of total reproducibility. You can reproduce certain `build step` from our Buildbot CI on your local machine. For that you have to:  
- Install all necessary packages on your OS (see packages above if you want to reproduce open source linux build)
- Clone repositories:
```
git clone https://github.com/Intel-Media-SDK/infrastructure.git
git clone https://github.com/Intel-Media-SDK/product-configs.git
cd infrastructure/build_scripts
```
- You can copy the build string from Buildbot ([example](http://mediasdk.intel.com/buildbot/#/builders/3/builds/122/steps/3/logs/stdio)) or write with your own and execute it. Note to change parameters: 
    - `build-config` - how to build product (you can specify your own config)
    - `root-dir` - where should be stored binaries after the build and logs
    - `manifest` - path to `manifest.yml` file where specified revisions of media components ([example](https://github.com/Intel-Media-SDK/product-configs/blob/master/manifest.yml))
    - `stage` - specifies which stage will be executed now (available stages `clean`, `extract`, `build`, `install`, `test`, `pack`, `copy`)
Example:
```
python3 build_runner.py --build-config /localdisk/bb/worker/build-mediasdk/product-configs/conf_linux_public.py --root-dir /localdisk/bb/worker/build-mediasdk/build_dir --manifest /media/builds/manifest/master/commit/0f3fec8c459eab9d16cbe99a1a76cc236be2226d/manifest.yml --component mediasdk --build-type release --product-type public_linux compiler=gcc compiler_version=6.3.1 compiler=gcc compiler_version=6.3.1 --stage clean
```

# How Buildbot knows about new commits (mechanism of Polling)
Our Buildbot configuration uses `GitPoller` and `GitHubPullrequestPoller` to know about new commits.  
- `GitPoller` - uses simple git. During first run Buildbot creates special directory in the root directory of Buildbot with cache of git. With help of this cache it calculates the *delta* (from which commit should be started CI builds).
- `GitHubPullrequestPoller` - uses Github API. In this case Github "makes a decision" which commits should be built

# License
This project is licensed under MIT license. See [LICENSE](./LICENSE) for details.
