=================================
 NoseST - Nose for System Testing
=================================

:Version: 2.1
:Web: https://github.com/jonozzz/nosest-src
:Download: https://github.com/jonozzz/nosest-src/repository/archive.zip?ref=master
:Source: https://github.com/jonozzz/nosest-src
:Keywords: test nose em bigiq bigip bvt

--

Description
===========

If you like Nose for unit testing, but would like to use it at a larger scale,
then this might be interesting to you. At its core it's comprised of a few base
building blocks:

- Interfaces: API wrappers for REST, SSH, UI/Selenium, SOAP;
- Commands: procedural blocks containing API calls for one interface;
- Macros: "mini-apps" built on top of interfaces and commands.

Documentation
=============

https://github.com/jonozzz/nosest-src
 
VirtualEnv Installation (Ubuntu)
================================
::

  sudo apt-get install curl ansible
  ansible-pull -Ke venv_name=ansible-test -e first_time=true -U git@github.com:jonozzz/nosest-src.git \
  contrib/ansible/bootstrap_py2.yaml

Dependencies
============

- For deployment: git, make, docker
- For testing: python-requests
- If you need access to CM images in /build you'll have mount that prior to runnint any tests.

For Ubuntu::

  See https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-16-04
  sudo usermod -aG docker <username>
  sudo apt-get install git make python-requests
  sudo mkdir -p /mnt/store1/testruns
  sudo chmod 777 /mnt/store1/testruns

For Centos::

  See https://docs.docker.com/engine/installation/linux/centos/
  sudo yum install docker docker-common container-selinux docker-selinux docker-engine
  sudo yum install git make python-requests
  sudo usermod -aG docker <username>
  sudo service docker start
  sudo mkdir -p /path/to/testruns
  sudo chmod 777 /path/to/testruns

Docker Installation
===================
::

  git clone -c http.sslVerify=false https://github.com/jonozzz/nosest-tests.git tests
  git clone -c http.sslVerify=false https://github.com/jonozzz/nosest-src.git src
  mkdir -p config/users
  git clone -c http.sslVerify=false https://.../<user>/nosest-config.git config/users/<user>
  make -C src/ INSTANCE=shiraz-1 PORT=8888 shiraz

Test the web server
===================
::

  python src/f5test/web/client_sample.py http://localhost:8888/bvt_test

To enter the running container::

  make -C src/ INSTANCE=shiraz-1 shell

License
=======

NoseST is distributed under the terms of the Apache
License, Version 2.0.  See docs/COPYING for more information.

Credits
=======

NoseST has been created with the help of:

- various testers and developers
