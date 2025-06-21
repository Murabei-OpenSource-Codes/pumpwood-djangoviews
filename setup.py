"""setup."""
import os
import setuptools

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()


# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setuptools.setup(
    name='pumpwood-djangoviews',
    version='dev-1.4.3',
    include_package_data=True,
    license='BSD-3-Clause License',
    description='Assist creating views for Django using Pumpwood pattern.',
    long_description=README,
    long_description_content_type="text/markdown",
    url='https://github.com/Murabei-OpenSource-Codes/pumpwood-djangoviews',
    author='Murabei Data Science',
    author_email='a.baceti@murabei.com',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    install_requires=[
        'requests',
        'simplejson',
        'pandas',
        'djangorestframework>=3.13',
        'Django>=5.0.0',
        'Shapely>=1.7.0',
        'geopandas>=0.8.1',
        'pumpwood-i8n>=0.1',
    ],
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
)
