
setup_args = dict(name='df2',
                  version='0.1',
                  url='https://bitbucket.org/scope/dragonfly-stp-1/',
                  author='Christian Krebs',
                  author_email='chrisk@opera.com',
                  description='Tools for Opera Dragonfly development.',
                  data_files=[('df2', ['df2/DEFAULTS',
                                       'df2/CONFIGDOC'])],
                  packages=['df2'],
                  zip_safe=False)

try:
    from setuptools import setup
    setup_args['entry_points'] = dict(console_scripts=['df2=df2.df2:main'])

except ImportError:
    from distutils.core import setup

setup(**setup_args)
