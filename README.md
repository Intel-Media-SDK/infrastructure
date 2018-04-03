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
- python v3.6.x
- postgresql
- git

```bash
sudo pip3 install buildbot==0.9.15.post1 buildbot-console-view==0.9.15.post1 buildbot-www==0.9.15.post1
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
mv ./master ./tmp_master

buildbot create-master --umask=0o2 master

cp ./tmp_master/* ./master/
rm -rf ./tmp_master/

#Configure Github`s webhook in your repository in settings-webhooks and create Github`s token after that do:
cd master
cp ./msdk_secrets.py.example ./msdk_secrets.py
nano msdk_secrets.py #add your real values

#Start Master Buildbot
cd ..
buildbot start master

```
### Deploy build box Worker Buildbot
Dependencies:
- CentOS v7.3
- python v3.6.x
- git
- Intel® Media Server Studio 2017 R3
  - Minimal needed rpms from MSS:
      ```bash
      intel-opencl-xxx-xxx.x86_64.rpm
      intel-opencl-cpu-xxx-.x86_64.rpm
      intel-opencl-devel-xxx-xxx.x86_64.rpm
      libdrm-xxx-xxx.el7.centos.x86_64.rpm
      libdrm-devel-xxx-xxx.el7.centos.x86_64.rpm
      libva-xxx-xxx.el7.centos.x86_64.rpm
      libva-devel-xxx-xxx.el7.centos.x86_64.rpm
      ```
>Hint:  
>```bash
>#To install packages use
>sudo yum install -ihv intel-opencl-*
>sudo yum install -ihv drm-*
>sudo yum install -ihv libva-*
>
>#To remove previous installed packages
>sudo yum install -e intel-opencl-*
>```


```bash
sudo pip3 install buildbot-worker==0.9.15.post1
sudo pip3 install gitpython==2.1.5 tenacity==4.5.0 txrequests txgithub service_identity

#Recommended list of packages
sudo yum groupinstall "Development Tools"
sudo yum install cmake git
sudo yum install libX11 libXext libXfixes libGL libGL-devel libX11-devel 
```
**Read more about the packages [here](docs/packages.md).**

Deploy:
```bash
buildbot-worker create-worker --umask=0o2 "worker" "<your_IP>:9000" "<your_worker_name>" "pass"

git clone https://github.com/Intel-Media-SDK/infrastructure.git ./worker/infrastructure
git clone https://github.com/Intel-Media-SDK/product-configs.git ./worker/product-configs

#Start Worker Buildbot
buildbot-worker start worker
```

### Deploy test box Worker Buildbot
Dependencies:
- CentOS v7.3
- python v3.6.x
- git
- Intel® Media Server Studio 2017 R3
  - Minimal needed rpms:
      ```bash
      intel-linux-media-xxx-xxx.el7.centos.x86_64.rpm  # Will install iHD_drv_video.so etc
      ```

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
buildbot-worker create-worker --umask=0o2 "worker" "<your_IP>:9000" "<your_worker_name>" "pass"

git clone https://github.com/Intel-Media-SDK/infrastructure.git ./worker/infrastructure

#Start Worker Buildbot
buildbot-worker start worker
```
>Hint:  
>To use graphical driver (from Media Server Studio) with tests as not root user do: 
>```bash
>usermod -a -G video <mediasdk_user>
>#And restart session!
>```

### Hints
- You can update all configurations by simple executing `git pull` command!
- Do not forget to add the line with `umask = 0o2` to the `buildbot.tac` file on all your masters and workers for the correct file permissions!
- To have additional information about your worker in Buildbot\`s worker list add **ip-address** to the `worker/info/host` file.
- Our configuration of Buildbot uses `GitPoller` so in case of private repos you need to execute `git config --global credential.helper store` and login once with your infrastructure credentials (otherwise polling will NOT work).

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
    - `stage` - specifies which stage will be executed now (available stages `clean`, `extract`, `build`, `install`, `pack`, `copy`)
Example:
```
python3.6 build_runner.py --build-config /localdisk/bb/worker/build-master-branch/../product-configs/conf_open_source.py --root-dir /localdisk/bb/worker/build-master-branch/build_dir --changed-repo MediaSDK:master:3b368450b49cde7be325988275ea8684d159df61 --build-type release --build-event commit --product-type linux --repo-url https://github.com/Intel-Media-SDK/MediaSDK.git --stage install
```

# How Buildbot knows about new commits (mechanism of Polling)
Our Buildbot configuration uses `GitPoller` and `GitHubPullrequestPoller` to know about new commits.  
- `GitPoller` - uses simple git. During first run Buildbot creates special directory in the root directory of Buildbot with cache of git. With help of this cache it calculates the *delta* (from which commit should be started CI builds).
- `GitHubPullrequestPoller` - uses Github API. In this case Github "makes a decision" which commits should be built

# License
This project is licensed under MIT license. See [LICENSE](./LICENSE) for details.
