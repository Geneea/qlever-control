#!/usr/bin/env bash

set -e

VENV=".tc.venv"	     # name of the virtual environment
KEEPENV=0            # do not delete the virtual environment folder on exit
REUSEENV=0           # use existing virtual environment and keep it
UPLOAD=0             # upload project artifacts to pypi.dev.g
PYTHON_VER="3.12"    # python version to use


while [ "${1+defined}" ]
do
case $1 in
    --keep-env)
        KEEPENV=1
    ;;
    --reuse-env)
        REUSEENV=1
        KEEPENV=1
    ;;
    --upload)
        UPLOAD=1
    ;;
    --python-version)
        shift
        PYTHON_VER=$1
    ;;
    --help)
    echo "build.sh [--keep-env | --reuse-env | --upload | --python-version <str> | --help] [dirname]"
    exit 1
    ;;
    *)
        VENV=$1
    ;;
esac
shift
done

echo "VENV: $VENV"
echo "KEEPENV: $KEEPENV"
echo "REUSEENV: $REUSEENV"
echo "UPLOAD: $UPLOAD"
echo "PYTHON_VER: $PYTHON_VER"

# create and activate $VENV virtual environment
function venv_start() {
    if [[ $REUSEENV -eq 0 ]] || [[ ! -d $VENV ]]; then
        rm -Rf $VENV
        uv venv -p ${PYTHON_VER} $VENV
    fi
    source $VENV/bin/activate
    uv pip install -U pytest pytest-cov
}

# deactivate and delete $VENV virtual environment
function venv_stop() {
    deactivate
    if [[ $KEEPENV -eq 0 ]]; then
        rm -Rf $VENV
    fi
}

# activate virtual environment and make sure it is deactivated on EXIT
venv_start
trap venv_stop EXIT

# run clean and remove all build dirs & files
rm -Rf build dist .eggs *.egg-info TEST-*.xml

echo "--------------------------------"
echo "Running build..."
echo "--------------------------------"
uv build --wheel --no-create-gitignore

echo "--------------------------------"
echo "Installing the package and test dependencies..."
echo "--------------------------------"
uv pip install -e .
# pyyaml and argcomplete are needed by upstream tests but not by the updater itself
uv pip install pyyaml argcomplete

echo "--------------------------------"
echo "Running tests..."
echo "--------------------------------"
pytest -v

# upload to pypi.dev.g
if [[ $UPLOAD -gt 0 ]]; then
    echo "--------------------------------"
    echo "Uploading..."
    echo "--------------------------------"
    uv pip install -U twine
    TWINE_USERNAME='' TWINE_PASSWORD='' twine upload --repository-url http://pypi.dev.g dist/*
fi
