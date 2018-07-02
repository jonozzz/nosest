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
  ansible-pull -Ke venv_name=ansible-test -e first_time=true -U https://<THIS REPO> contrib/ansible/bootstrap_py2.yaml

Quick Start
===========
Create a config:

.. code-block:: yaml

    # content of example.yaml
    devices:
      bigip-1:
        default: true
        kind: tmos:bigip
        address: 10.144.10.196

Create a test:

.. code-block:: python

    # content of hello.py
    def test(context):
        sshifc = context.get_ssh()
        print(sshifc.api.run('echo hello world!').stdout)

Run pytest::

    $ pytest --tc example.yaml hello.py
    ====================== test session starts =======================
    platform linux2 -- Python 2.7.12, pytest-3.5.1.dev114+gdc90c91, py-1.5.3, pluggy-0.6.0
    rootdir: /home/lab/.virtualenvs/ansible-testX, inifile:
    plugins: metadata-1.7.0, json-report-0.7.0, f5-sdk-3.0.14, f5test-1.0.0
    collected 1 item

    hello.py .                                                 [100%]

    ==================== 1 passed in 2.72 seconds ====================

License
=======

NoseST is distributed under the terms of the Apache
License, Version 2.0.  See docs/COPYING for more information.

Credits
=======

NoseST has been created with the help of:

- various testers and developers
