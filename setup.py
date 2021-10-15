import setuptools

with open('README.md') as readme:
    long_desc = readme.read()

setuptools.setup(
    name='pymap-copy',
    version='1.0.2',
    python_requires='>=3.6',
    scripts=['pymap-copy.py'],
    author='Lukas Schulte-Tickmann',
    author_email='github@das-it-gesicht.de',
    description='Copy and transfer IMAP mailboxes',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    url='https://github.com/Schluggi/pymap-copy',
    project_urls={
        'Source': 'https://github.com/Schluggi/pymap-copy',
        'Tracker': 'https://github.com/Schluggi/pymap-copy/issues',
        'Funding': 'https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=KPG2MY37LCC24&source=url'
    },
    packages=setuptools.find_packages(),
    py_modules=['imapidle', 'utils'],
    install_requires=[
        'chardet',
        'IMAPClient',
        'six'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Communications :: Email :: Post-Office :: IMAP',
        'Topic :: Utilities'
    ]
)