from setuptools import setup

about = {}
with open("polyhost/_version.py") as f:
    exec(f.read(), about)
    
def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='PolyHost',
      version=about["__version__"],
      description='Communication from PolyKybd to the host system',
      long_description=readme(),
      keywords='polykybd host forwarder poly',
      url='https://github.com/thpoll83/PolyKybdHost',
      author='thpoll')