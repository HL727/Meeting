#
# Deprecated. Use deploy/docker_tests.sh instead
#

if [ "$1" = "pypy" ]
then
    alias python=pypy3
    alias python3=pypy3
fi

set -e
if [ -e testbuild ]
then
	echo 'dir testbuild already exists. remove? [Yn]'
	read x
	if [ "$x" != "y" ]
	then
		exit 1
	fi
	rm -rf testbuild
fi

git clone . testbuild
[ ! -e conferencecenter/local_settings.py ] || cp conferencecenter/local_settings.py testbuild/conferencecenter
cd testbuild
python3 -m venv venv  || virtualenv --python=python3 venv
pwd
ls
. venv/bin/activate
python3 -mpip install wheel
python3 -mpip install -r requirements.txt tblib unittest-xml-reporting==3.0.4
export SQLITE=1
while true
do
    if python3 manage.py test --settings=conferencecenter.settings_test --parallel
    then
        break
    fi
    echo 'Try again? [Yn]'
    read x
    if [ "$x" = "n" ]
    then
        break
    fi
done

rm -rf testbuild
