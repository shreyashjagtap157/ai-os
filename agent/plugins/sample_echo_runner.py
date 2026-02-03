"""Subprocess-runner for sample_echo plugin (sandboxed execution).

This module is invoked as `python -m agent.plugins.sample_echo_runner arg1 arg2...`
"""
import sys

def main(argv):
    # simply print args as plugin would
    print('[plugin-sandbox] ' + ' '.join(argv))


if __name__ == '__main__':
    main(sys.argv[1:])
