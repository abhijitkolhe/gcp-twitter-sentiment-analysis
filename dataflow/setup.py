import setuptools

REQUIRED_PACKAGES = [
    'apache-beam[gcp]==2.25.0',
    'tensorflow==2.3.1',
    'tweet-preprocessor==0.6.0'
]

setuptools.setup(
    name='predict',
    version='0.0.1',
    install_requires=REQUIRED_PACKAGES,
    packages=setuptools.find_packages(),
    include_package_data=True,
    description='Twitter sentiment analysis prediction',
)