[ -e /tmp/.env ] && . /tmp/.env
DEFAULT_URL="http://web:8000/email/book/"
curl -s --request POST --include --header "X-Mividas-Token: ${EXTENDED_API_KEY:-empty}" --header 'Content-Type: application/json' --data-binary @- --no-buffer "${WEB_URL:-$DEFAULT_URL}"
