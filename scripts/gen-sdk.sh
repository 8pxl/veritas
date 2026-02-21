#!/usr/bin/env sh

SERVER_URL="$1"

if [ -z "$SERVER_URL" ]; then
  echo "Usage: ./generate.sh <openapi_url>"
  exit 1
fi

bun x @hey-api/openapi-ts -i "$SERVER_URL" -o frontend/lib/client
