from setuptools import setup, find_packages

exec(open('./src/screenshare/_version.py').read())

setup(
    name='screenshare',

    version=__version__,

    description='Simple Screensharing',

    package_dir={'': 'src'}, 

    packages=find_packages(where='src'),

    python_requires='>=3.6, <4',

    install_requires=['pynput', 'opencv-python', 'numpy', 'mss'],
    entry_points={
        'console_scripts': [
            'screenshare=screenshare:main',
        ],
    },
    
    project_urls={
        'Source': 'https://github.com/matthias95/screenshare'
    }
)