=================================
 NoseST - Nose for System Testing
=================================

:Version: 2.1
:Web: https://github.com/jonozzz/nosest
:Download: https://github.com/jonozzz/nosest/repository/archive.zip?ref=master
:Source: https://github.com/jonozzz/nosest
:Keywords: test nose system test framework

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

https://github.com/jonozzz/nosest
 
VirtualEnv Installation (Ubuntu)
================================
::

  sudo apt-get install curl ansible
  ansible-playbook -Ke venv_name=ansible-test -e first_time=true bootstrap_py2.yaml

License
=======

NoseST is distributed under the terms of the Apache
License, Version 2.0.  See docs/COPYING for more information.

Credits
=======

NoseST has been created with the help of:

- various testers and developers
