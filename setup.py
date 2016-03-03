#!/usr/bin/env python
# coding=utf-8

from setuptools import setup, find_packages

setup(
    name='calendarsync',
    version='0.1.0',
    packages=find_packages(),
    scripts=['bin/calendarsync'],
    author='Tim Bolender',
    author_email='contact@timbolender.de',
    url='https://github.com/itiboi/cacaluploader',
    license='',
    description='Handy script to synchronise the RWTH Aachen University\'s CampusOffice calendar with your CalDAV'
                'or Exchange calendar.'
)
