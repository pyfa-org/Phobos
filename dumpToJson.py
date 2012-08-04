"""Cache dumper script, uses phobos to dump a json dump to disk

Copyright (c) 2012 Diego "Sakari" Duclos <sakari@evefit.org>
Copyright (c) 2012 Romain "Artefact2" Dalmaso <artefact2@gmail.com>

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
	parser.add_argument("-t", "--tables", help="comma-separated list of table names to dump (all tables are dumped by default)")
	args = parser.parse_args()

	# Needed args & helpers
	eve = blue.EVE(args.eve, cachepath=args.cache, server=args.server)
	cfg = eve.getconfigmgr()
	indent = 4 if args.indent else None
	output = args.output

	# Helper function
	def processRowSet(tableName, rowSet):
		print("processing {}".format(tableName))
		header, lines = RowSetProcessor(tableName, rowSet).run()
		JsonWriter(tableName, header, lines, output, 4 if args.indent else None).run()

	# If -t is present, only dump the specified tables
	if(args.tables != None):
		for tableName in args.tables.split(","):
			try:
				t = tableName.split("_", 2)
				if(len(t) == 2):
					rowSet = getattr(eve.RemoteSvc(t[0]), t[1])()
				else:
					rowSet = getattr(cfg, t[0])
				processRowSet(tableName, rowSet)
			except:
				print("failed to process {}".format(tableName))
	else:
		# Process bulkdata tables
		for tableName in cfg.tables:
			try:
				rowSet = getattr(cfg, tableName)
				processRowSet(tableName, rowSet)
			except KeyboardInterrupt:
				raise
			except:
				print("failed to process {}".format(tableName))

		# Process remote service calls
		for service, call in discoverSvc(eve):
			tableName = "{}_{}".format(service, call)
			try:
				rowSet = getattr(eve.RemoteSvc(service), call)()
				processRowSet(tableName, rowSet)
			except KeyboardInterrupt:
				raise
			except:
				print("failed to process {}".format(tableName))

	print("all done")
