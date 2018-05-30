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
sudo pip3 install buildbot==1.1.2 buildbot-console-view==1.1.2 buildbot-www==1.1.2
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

buildbot create-master master

cp ./tmp_master/* ./master/
rm -rf ./tmp_master/

#Configure Github`s webhook in your repository in settings-webhooks and create Github`s token after that do:
cd master
cp ./msdk_secrets.py.example ./msdk_secrets.py
nano msdk_secrets.py #add your real values

nano buildbot.tac #edit `umask` with the value `umask=0o2`

#Start Master Buildbot
buildbot start .
```
### Deploy build box Worker Buildbot
Prerequisites:
- CentOS v7.3
- Python v3.6.x

Needed packages (dependencies):
```bash
sudo yum install libpciaccess libpciaccess-devel opencl-headers

#Enable epel repository
sudo yum install gtest gtest-devel ocl-icd ocl-icd-devel

#Compile OpenCL from these cources: https://github.com/intel/compute-runtime/releases/tag/2018ww18-010782
#By using these instructions: https://github.com/intel/compute-runtime/blob/master/documentation/BUILD_Centos.md
sudo rpm -ihv intel-opencl-1.0-0.x86_64-igdrcl.rpm
```
Current package versions used in Media SDK CI:
```bash
libpciaccess-0.14-1.el7.x86_64
libpciaccess-devel-0.14-1.el7.x86_64

gtest-1.6.0-2.el7.x86_64
gtest-devel-1.6.0-2.el7.x86_64

ocl-icd-2.2.12-1.el7.x86_64
ocl-icd-devel-2.2.12-1.el7.x86_64

opencl-headers-2.2-1.20180306gite986688.el7.noarch
```

```bash
sudo pip3 install buildbot-worker==1.1.2
sudo pip3 install gitpython==2.1.5 tenacity==4.5.0 txrequests txgithub service_identity

#Install devtoolset-6 for gcc 6.3.1
sudo yum install centos-release-scl
sudo yum install devtoolset-6

#Recommended list of packages
sudo yum groupinstall "Development Tools"
sudo yum install cmake git
sudo yum install libX11 libXext libXfixes libGL libGL-devel libX11-devel 
```
**Read more about the packages [here](docs/packages.md).**

Deploy:
```bash
buildbot-worker create-worker --umask=0o2 "worker" "<buildbot_master_IP>:9000" "<your_worker_name>" "pass"

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
