from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="voxflow",
    version="0.1.0",
    author="VoxFlow",
    description="Local-first voice dictation, an open-source alternative to WhisperFlow",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    package_data={"voxflow": ["assets/*"]},
    install_requires=requirements,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "voxflow=voxflow.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],
)
