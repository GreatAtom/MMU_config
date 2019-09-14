from setuptools import setup

version = __import__('generator').get_version()

setup(
    name='MMU_config',
    version=version,
    description='The init table generator for RISC-V/mips MMU'
)
