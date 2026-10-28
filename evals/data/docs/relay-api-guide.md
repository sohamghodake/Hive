# Relay Payments API: Developer Guide

## Authentication

Every request must include an API key in the Authorization header as a bearer token. Live keys begin with the prefix rly_live_ and test keys with rly_test_. Keys must be rotated at least every ninety (90) days; a key older than that is rejected with error code key_expired. Never embed a live key in client-side code.

## Rate Limits

Each API key may make up to 600 requests per minute, with short bursts of up to 100 requests per second. When a key exceeds its limit the API responds with HTTP 429 and a Retry-After header giving the number of seconds to wait. Clients should back off for at least that long before retrying.

## Pagination

List endpoints use cursor-based pagination. Pass the next_cursor value from the previous response as the cursor parameter to fetch the next page. The default page size is 50 items and the maximum page size is 200 items; larger values are rejected.

## Idempotency

POST requests that create payments should include an Idempotency-Key header. If a request with the same key is retried within twenty-four (24) hours, the API returns the original response instead of creating a second payment. After 24 hours the key may be reused.

## Webhooks

Relay sends event notifications to your webhook endpoint as JSON. Each delivery is signed with HMAC-SHA256 using your endpoint secret, and the signature is sent in the Relay-Signature header; reject any delivery whose signature does not verify. If your endpoint does not return a 2xx status, Relay retries with exponential backoff for up to seventy-two (72) hours before marking the delivery as failed.

## Versioning

The API is versioned by release date, for example 2026-04-01, selected with the Relay-Version header. When a version is deprecated it remains supported for twelve (12) months, and deprecation notices are sent to the account's technical contact.

## Service Level Agreement

Relay commits to 99.95% monthly uptime for the payments API. If monthly uptime falls below 99.95%, the account receives a service credit of 10% of that month's platform fee; below 99.0%, the credit is 25%. Credits must be claimed through the support portal within thirty days.

## Data Retention

Request logs, including headers but not card numbers, are retained for thirty (30) days and are visible in the dashboard. Card numbers are tokenised at the edge and never stored in logs.
