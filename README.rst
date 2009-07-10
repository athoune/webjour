WebJour
=======

Webjour is a web interface for bonjour services discovering.

Its main target is VPN connected users, wich loose bonjour broadcasting.

Dependencies
------------

Python 2.6 provides json, but not python 2.5::

  sudo easy-install -U simplejson

Bonjour binding is done with pybonjour_::

  sudo easy-install -U pybonjour

Usage
-----

Webjour use wsgi tools, for now, it's standalone::

  ./webjour.py

The web page is http://localhost:8000

.. _pybonjour: http://code.google.com/p/pybonjour/
