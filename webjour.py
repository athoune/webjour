#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

from wsgiref.simple_server import make_server
from wsgiref.util import setup_testing_defaults
import threading

import select
import socket
import sys
import pybonjour

regtypes = ["_http._tcp.", "_https._tcp.", "_daap._tcp.", "_rfb._tcp.", "_afpoverctp._tcp.", "_ssh._tcp.", "_ipp._tcp.", "_webdav._tcp.", "_webdavs._tcp."]#sys.argv[1]
timeout = 5
resolved = []
queried = []
services = {}
ips = {}

class Page(object):
	def __init__(self):
		self.step = 0
		self.header = """
<html><head></head><body>
<ul>
"""
		self.footer = """
		</ul>
		</body></html>
"""
	def __iter__(self):
		global services
		global ips
		if self.step == 0:
			self.step += 1
			yield self.header
		if self.step == 1:
			for key, value in services.iteritems():
				print ips
				if value['hosttarget'].endswith('.local.') and value['hosttarget'] in ips:
					host = ips[value['hosttarget']]
				else:
					host = value['hosttarget']
				service = value['fullname'].split('.')[-4][1:]
				yield ('<li> [%s] <a href="%s://%s:%i">%s</a></li>' % (service, service, host, value['port'], value['hosttarget'])).encode('utf8')
		if self.step == 2:
			self.step += 1
			yield self.footer
		

class WebJour(threading.Thread):
	def __init__(self, name="Webjour"):
		self._stopevent = threading.Event()
		threading.Thread.__init__(self, name = name)
	def web(self, environ, start_response):
		setup_testing_defaults(environ)

		status = '200 OK'
		headers = [('Content-type', 'text/html')]

		start_response(status, headers)

		#ret = ["%s: %s\n" % (key, value)
	  #         for key, value in environ.iteritems()]
		global services
		
		#return [("%s => %s:%i\n" % (key, value['hosttarget'], value['port'])).encode('utf8')
	    #       for key, value in services.iteritems()]
		return Page()
	def run(self):
		httpd = make_server('', 8000, self.web)
		print "Serving on port 8000..."
		while not self._stopevent.isSet():
			httpd.handle_request()
	def join(self, timeout=None):
		self._stopevent.set()
		threading.Thread.join(self,timeout)

web = WebJour()
web.start()

def query_record_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
						  rrtype, rrclass, rdata, ttl):
	if errorCode == pybonjour.kDNSServiceErr_NoError:
		print '	 IP			=', socket.inet_ntoa(rdata)
		global ips
		ips[fullname] = socket.inet_ntoa(rdata)
		queried.append(True)

def resolve_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
					 hosttarget, port, txtRecord):
	if errorCode != pybonjour.kDNSServiceErr_NoError:
		return
	print 'Resolved service:'
	print '	 fullname	=', fullname
	print '	 hosttarget =', hosttarget
	print '	 port		=', port
	global services
	services[fullname] = {"fullname":fullname, "hosttarget":hosttarget, "port":port, "txtRecord":txtRecord}
	query_sdRef = pybonjour.DNSServiceQueryRecord(
		interfaceIndex = interfaceIndex,
		fullname = hosttarget,
		rrtype = pybonjour.kDNSServiceType_A,
		callBack = query_record_callback)
	try:
		while not queried:
			ready = select.select([query_sdRef], [], [], timeout)
			if query_sdRef not in ready[0]:
				print 'Query record timed out'
				break
			pybonjour.DNSServiceProcessResult(query_sdRef)
		else:
			queried.pop()
	finally:
		query_sdRef.close()
	resolved.append(True)

def browse_callback(sdRef, flags, interfaceIndex, errorCode, serviceName,
					regtype, replyDomain):
	if errorCode != pybonjour.kDNSServiceErr_NoError:
		return
	if not (flags & pybonjour.kDNSServiceFlagsAdd):
		print 'Service removed %' % serviceName
		return
	print 'Service added; resolving'
	resolve_sdRef = pybonjour.DNSServiceResolve(
		0,
		interfaceIndex,
		serviceName,
		regtype,
		replyDomain,
		resolve_callback)
	try:
		while not resolved:
			ready = select.select([resolve_sdRef], [], [], timeout)
			if resolve_sdRef not in ready[0]:
				print 'Resolve timed out'
				break
			pybonjour.DNSServiceProcessResult(resolve_sdRef)
		else:
			resolved.pop()
	finally:
		resolve_sdRef.close()

browse_sdRefs = []
for regtype in regtypes:
 browse_sdRefs.append(pybonjour.DNSServiceBrowse(
	regtype = regtype,
	callBack = browse_callback))

try:
	try:
		while True:
			for browse_sdRef in browse_sdRefs:
				ready = select.select([browse_sdRef], [], [])
				if browse_sdRef in ready[0]:
					pybonjour.DNSServiceProcessResult(browse_sdRef)
	except KeyboardInterrupt:
		print "Stop!"
		web.join()
finally:
	browse_sdRef.close()
