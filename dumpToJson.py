"""Cache dumper script, uses phobos to dump a json dump to disk

Copyright (c) 2012 Diego "Sakari" Duclos <sakari@evefit.org>

This code is free software; you can redistribute it and/or modify
it under the terms of the BSD license (see the file LICENSE.txt
included with the distribution).
"""
import argparse
import sys

from reverence import blue

from phobos.writer.jsonWriter import JsonWriter
from phobos.remoteSvc import discover as discoverSvc
from phobos.rowSetProcessor import RowSetProcessor

if __name__ == "__main__":
	try:
		major = sys.version_info.major
		minor = sys.version_info.minor
	except AttributeError:
		major = sys.version_info[0]
		minor = sys.version_info[1]
	if major != 2 or minor < 7:
		sys.stderr.write("This application requires Python 2.7 to run, but {0}.{1} was used\n".format(major, minor))
		sys.exit()

	parser = argparse.ArgumentParser(description="This scripts dumps effects from an sqlite cache dump to mongo")
	parser.add_argument("-e", "--eve", help="path to eve folder", required=True)
	parser.add_argument("-c", "--cache", help="path to eve cache folder", required=True)
	parser.add_argument("-d", "--dump", help="path to SQLite dump file, including file name")
	parser.add_argument("-s", "--server", default='tranquility', help="If we're dealing with a singularity cache")
	parser.add_argument("-o", "--output", help="Output folder for the json files", required=True)
	parser.add_argument("-i", "--indent", action="store_true", help="Use pretty indentation for json files", default=False)
	args = parser.parse_args()

	# Initialize reverence object, get tables and write them out to json
	eve = blue.EVE(args.eve, cachepath=args.cache, server=args.server)
	cfg = eve.getconfigmgr()

	# Process bulkdata tables
	for tableName in cfg.tables:
		print("processing {}".format(tableName))
		try:
			rowSet = getattr(cfg, tableName)
			header, lines = RowSetProcessor(tableName, rowSet).run()
		except IOError:
			print("failed to read {}".format(tableName))
		else:
			JsonWriter(tableName, header, lines, args.output).run()

	# Process remote service calls
	for service, call in discoverSvc(eve):
		tableName = "{}_{}".format(service, call)
		print("processing {}".format(tableName))
		try:
			rowSet = getattr(eve.RemoteSvc(service), call)()
			header, lines = RowSetProcessor(tableName, rowSet).run()
		except IOError:
			print("Failed to read {}".format(tableName))
		else:
			JsonWriter(tableName, header, lines, args.output, indent=4 if args.indent else None).run()

	"""
	#Debug code
	from reverence import blue
	from eve2sql.processor.rowSetProcessor import RowSetProcessor
	eve = blue.EVE(args.eve, cachepath=args.cache, server=args.server)
	rowSet = getattr(eve.RemoteSvc("agentMgr"), "GetAgentsInSpace")()
	RowSetProcessor("agentMgr_GetAgentsInSpace", rowSet).run()
	"""