import build
import jssort
import os
import cleanrepo

def normws(args):
    cleanrepo.normws(src=".")

def setup_subparser(subparsers, config):
    subp = subparsers.add_parser("normws", help="""Runs normws.
                                                      Must be run in the root of a
                                                      Dragonfly repo""")
    subp.set_defaults(func=normws)
