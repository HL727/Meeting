set -e

check() {
    if ! npx --no-install vue-gettext-cli --help > /dev/null
    then
        echo Run npm install --no-save easygettext vue-gettext-cli
        exit 1
    fi
}

PROJECT_ID=343393
READONLY_TOKEN="${POEDITOR_READONLY_TOKEN:-006c0f3bfe52dda4d3e6e76b87422fdd}"
TOKEN="${POEDITOR_TOKEN:-}"

download() {

	URL="$( curl -X POST https://api.poeditor.com/v2/projects/export \
		-d api_token="$READONLY_TOKEN" \
		-d id="$PROJECT_ID" \
		-d language="en" \
		-d type=po | jq -r '.result.url'
	)"


	curl $URL > locale/en_US/LC_MESSAGES/django.po

	URL="$( curl -X POST https://api.poeditor.com/v2/projects/export \
		-d api_token="$READONLY_TOKEN" \
		-d id="$PROJECT_ID" \
		-d language="en" \
		-d tags=frontend \
		-d type=po | jq -r '.result.url'
	)"

	curl $URL > locale/en_US/LC_MESSAGES/djangojs.po
        if grep '% {' locale/en_US/LC_MESSAGES/djangojs.po -B 1
        then
            echo Invalid interpolation formats. Fixing
            sed -i 's/% {/ %{/g' locale/en_US/LC_MESSAGES/djangojs.po
        fi

	python manage.py compilemessages
}

extract() {
    check
    [ -e build ] && rm -rf build
    if [ -e .git ]
    then
        git clone . build
    else
        cp -a ./ build/
    fi
    rm -rf build/js-ui/deprecated  # jsx-files with .js-extension breaks gettext-extract
    mkdir -p build/locale/en_US/LC_MESSAGES/
    npx vue-gettext-cli extract -s build/js-ui -d build/locale/en_US/LC_MESSAGES/
    sed -i "s~`pwd`/build/~~" build/locale/en_US/LC_MESSAGES/template.pot
    touch build/locale/en_US/LC_MESSAGES/djangojs.po
    msgmerge build/locale/en_US/LC_MESSAGES/djangojs.po build/locale/en_US/LC_MESSAGES/template.pot > locale/en_US/LC_MESSAGES/djangojs.po
    cd build
    python manage.py makemessages -l en_US -i '*/tests/*'
    cd ..
    cp build/locale/en_US/LC_MESSAGES/django.po locale/en_US/LC_MESSAGES/django.po
    rm -rf build

}

upload_django() {
    if [ -z "$TOKEN" ]
    then
        echo '$POEDITOR_TOKEN not set. Cant upload'
        exit
    fi
    curl -X POST https://api.poeditor.com/v2/projects/upload \
     -F api_token="$TOKEN" \
	 -F id="$PROJECT_ID" \
     -F updating="terms" \
     -F file=@"locale/en_US/LC_MESSAGES/django.po"
}

upload_js() {
    if [ -z "$TOKEN" ]
    then
        echo '$POEDITOR_TOKEN not set. Cant upload'
        exit
    fi
    curl -X POST https://api.poeditor.com/v2/projects/upload \
     -F api_token="$TOKEN" \
	 -F id="$PROJECT_ID" \
     -F updating="terms" \
     -F tags="{\"all\":\"frontend\"}" \
     -F file=@"locale/en_US/LC_MESSAGES/djangojs.po"
}


case "$1" in
"upload") extract ; upload_django; sleep 15 ; upload_js ;;
"upload_django") extract ; upload_django ;;
"upload_js") extract ; upload_js ;;
"extract") extract ;;
"download") download ;;
"") download ;;
esac
