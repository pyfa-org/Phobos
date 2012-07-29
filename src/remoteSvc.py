"""Remote service call handling code

Copyright (c) 2012 Diego "Sakari" Duclos <sakari@evefit.org>

This code is free software; you can redistribute it and/or modify
it under the terms of the BSD license (see the file LICENSE.txt
included with the distribution).
"""

import glob
import os.path
from reverence import blue

_join = os.path.join

def _readfile(filename):
	with open(filename, "rb") as f:
		return f.read()

def discover(eve):
	"""
	Discover available remote service calls from cache fails.
	A call being listed here will not necessarily succeed
	"""
	cache = eve.getcachemgr()

	s = set()
	for filename in glob.glob(_join(cache.machocachepath, 'CachedMethodCalls', '*.cache')):
		info, data = blue.marshal.Load(_readfile(filename))
		service, call = info[0:2]
		if isinstance(service, tuple):
			service = service[0]

		s.add((service, call))

	return s