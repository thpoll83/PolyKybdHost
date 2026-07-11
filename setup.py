import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, "polyhost/_version.py")) as version_file:
    exec(version_file.read(), about)


def readme():
    with open(os.path.join(here, "README.md"), encoding="utf-8") as readme_file:
        return readme_file.read()


def requirements():
    """Read install requirements from requirements.txt (single source of truth)."""
    reqs = []
    with open(os.path.join(here, "requirements.txt"), encoding="utf-8") as req_file:
        for raw in req_file:
            line = raw.split("#", 1)[0].strip()
            if line and not line.startswith("-"):
                reqs.append(line)
    return reqs


setup(name='PolyHost',
      version=about["__version__"],
      description='Communication from PolyKybd to the host system',
      long_description=readme(),
      long_description_content_type='text/markdown',
      license='GPL-3.0-or-later',
      classifiers=[
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
      ],
      keywords='polykybd host forwarder poly',
      url='https://github.com/thpoll83/PolyKybdHost',
      author='thpoll',
      packages=find_packages(exclude=['tests', 'tests.*']),
      install_requires=requirements(),
      # The font-pack *extend* path (build glyphs from TTF/OTF, fontconvert-parity)
      # needs freetype-py/uharfbuzz/fonttools — now core deps (requirements.txt) so
      # Build works out of the box.  The [fontgen] extra is kept as a no-op alias
      # for back-compat with `pip install .[fontgen]`.
      extras_require={"fontgen": []},
      entry_points={"console_scripts": ["polyctl = polyhost.cli.polyctl:main"]})
