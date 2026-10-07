#!/bin/sh
gcloud run deploy example --image "$IMAGE" --set-env-vars "EXAMPLE_KEY=example-value-not-to-be-printed"
